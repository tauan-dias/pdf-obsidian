"""Fluxos QML reais, somente PDFs/vaults sintéticos e documentos duráveis."""
from pathlib import Path
from queue import Queue
from types import SimpleNamespace
import threading
import time

import pytest
from PySide6.QtCore import QEvent, QObject, QUrl, Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QFileDialog

from pdf_obsidian.application import ApplicationController
from pdf_obsidian.converter import convert
from pdf_obsidian.quick import QuickController, create_engine
from pdf_obsidian.models import ConversionResult, Page


class Runtime:
    def __init__(self, root):
        self.root = root
        root.mkdir()
        self.commands, self.events = Queue(), Queue()
        self.cancel_event = threading.Event()
        self.alive = True
        self.worker = SimpleNamespace(is_alive=lambda: self.alive)
        self.workspaces = []

    def allocate_workspace(self):
        import tempfile
        result = Path(tempfile.mkdtemp(dir=self.root))
        self.workspaces.append(result)
        return result

    def close(self):
        self.alive = False


@pytest.fixture
def quick(app, tmp_path):
    application = ApplicationController(runtime=Runtime(tmp_path / 'runtime'))
    controller = QuickController(application=application)
    engine = create_engine(controller)
    warnings = engine.load_warnings
    engine.warnings.connect(lambda items: warnings.extend(i.toString() for i in items))
    window = engine.rootObjects()[0]
    app.processEvents()
    yield controller, window, application.runtime
    controller.render_timer.stop()
    controller.preview_timer.stop()
    application.shutdown()
    window.setProperty('closingApproved', True)
    window.close()
    engine.deleteLater()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()
    assert not warnings


def document(root, name='A', text=None):
    return ConversionResult(root / (name + '.pdf'), 'synthetic', name,
        text or '<!-- Página 1 -->\n\n# ' + name + '\n\nTexto para revisão.', root,
        [Page(1, 595, 842), Page(2, 595, 842)], [])


def test_quick_plain_source_unicode_format_history_and_session_swap(quick, tmp_path, app):
    c, w, runtime = quick
    a = c.create_session(document(tmp_path, text='ação 💡 texto'))
    c.activate(a.id)
    app.processEvents()
    assert c.editor.property('text') == 'ação 💡 texto'
    c.selectionRequested.emit(7, 0)  # reverse Unicode selection includes surrogate pair
    c.format('bold', None)
    assert a.document.toPlainText() == '**ação 💡** texto'
    assert c.editor.property('cursorPosition') < c.editor.property('selectionEnd')
    w.setProperty('pdfVisible', False)
    w.setProperty('tab', 1)
    w.setProperty('follow', True)
    c._page, c._zoom, c._zoom_mode = 2, 175, 'manual'
    b = c.create_session(document(tmp_path, 'B', '<p style="text-align: center;">literal</p>'))
    c.activate(b.id)
    assert c.editor.property('text') == b.document.toPlainText()
    c.activate(a.id)
    assert c.page == 2 and c.zoom == 175 and c.zoomMode == 'manual'
    assert w.property('pdfVisible') is False and w.property('tab') == 1
    c.undo()
    assert a.document.toPlainText() == 'ação 💡 texto'
    c.redo()
    assert a.document.toPlainText() == '**ação 💡** texto'
    assert a.document.parent() is c


def test_native_edit_and_keyboard_shortcuts_use_same_document(quick, tmp_path, app):
    c, w, _ = quick
    c.receive(document(tmp_path, text='texto'))
    w.requestActivate()
    c.editor.forceActiveFocus()
    c.selectionRequested.emit(0, 5)
    QTest.keyClick(w, Qt.Key_B, Qt.ControlModifier)
    app.processEvents()
    assert c.active.document.toPlainText() == '**texto**'
    QTest.keyClick(w, Qt.Key_Z, Qt.ControlModifier)
    assert c.active.document.toPlainText() == 'texto'
    for key in (Qt.Key_N, Qt.Key_O, Qt.Key_V, Qt.Key_O):
        QTest.keyClick(w, key)
    assert 'novo' in c.active.document.toPlainText()


def test_preview_alignment_and_manual_image_removal_recovery(quick, manual_source, tmp_path, app):
    c, w, _ = quick
    result = convert(manual_source, tmp_path / 'converted')
    c.receive(result)
    app.processEvents()
    c.refresh_preview()
    assert c._images
    c.setSelectionMode(True)
    before = c.active.document.toPlainText()
    position = next(iter(c._images))
    asset, occurrence = c._images[position]
    path = result.workspace / asset
    c.toggleImage(position)
    assert c.selectedImages == 1
    c.removeImages()
    assert c.active.document.toPlainText() != before
    assert path.is_file()  # temporary originals survive removal
    assert len(c.active.removals) == 1
    c.undo()
    assert c.active.document.toPlainText() == before
    c.refresh_preview()
    assert c.previewReady
    w.setProperty('tab', 1)
    app.processEvents()
    assert c._preview_doc.toPlainText()


def test_filtered_restore_one_undo_preserves_selection(quick, decorative_source, tmp_path, app):
    c, _, _ = quick
    result = convert(decorative_source, tmp_path / 'converted')
    c.receive(result)
    c.openFiltered()
    assert c.filteredCount > 0
    before = c.active.document.toPlainText()
    c.selectionRequested.emit(12, 3)
    c.restoreImage(0)
    assert result.filtered_images[0].asset in c.active.document.toPlainText()
    assert c.selection() == (12, 3)
    assert c.filtered.rows[0]['restorable'] is False
    c.undo()
    assert c.active.document.toPlainText() == before
    c.refresh_preview()
    from pdf_obsidian.restoration import restoration_edit
    restoration_edit(result, c.active.document.toPlainText(), result.filtered_images[0])
    assert c.filtered.rows[0]['restorable'] is False  # revalidation is pending, not enabled speculatively


def test_export_snapshot_busy_stale_response_and_success(quick, tmp_path):
    c, _, r = quick
    c.receive(document(tmp_path))
    vault = tmp_path / 'vault'
    vault.mkdir()
    assert c.start_export(vault)
    command = r.commands.get_nowait()
    assert command[0] == 'session_export'
    assert command[5] == c.active.result and command[6] == c.active.document.toPlainText()
    assert not c.editable
    before = c.active.document.toPlainText()
    c.format('bold', None)
    assert c.active.document.toPlainText() == before
    c.export_finished(['obsolete', *command[2:4], True, 'hash', 'wrong', False])
    assert c.application.busy
    target = vault / 'Importados' / 'aula'
    r.events.put(('session_export', *command[1:4], True, 'signature', str(target), False))
    c.application.poll()
    assert c.editable and not c.modified
    assert c.active.exports[str(vault.resolve())].target == target


def test_export_failure_keeps_dirty_document(quick, tmp_path):
    c, _, r = quick
    c.receive(document(tmp_path))
    assert c.start_export(tmp_path)
    command = r.commands.get_nowait()
    r.events.put(('session_export', *command[1:4], False, 'Falha sintética', '', False))
    c.application.poll()
    assert c.modified and c.editable and not c.active.exports


def test_numeric_fields_commit_once_restore_invalid_and_follow_session(quick, tmp_path, app):
    from PySide6.QtTest import QSignalSpy
    c, w, _ = quick
    c.receive(document(tmp_path))
    app.processEvents()
    page = w.findChild(QQuickItem, 'pageField')
    zoom = w.findChild(QQuickItem, 'zoomField')
    method = page.metaObject().method(page.metaObject().indexOfSignal('committed(int)'))
    commits = QSignalSpy(page, method)

    def enter(field, digits, accept=False):
        field.forceActiveFocus()
        QTest.keyClick(w, Qt.Key_A, Qt.ControlModifier)
        QTest.keyClick(w, Qt.Key_Backspace)
        for digit in digits:
            QTest.keyClick(w, Qt.Key(int(Qt.Key_0) + int(digit)))
        if accept:
            QTest.keyClick(w, Qt.Key_Return)
        c.editor.forceActiveFocus()
        app.processEvents()

    enter(page, '2')
    assert c.page == 2 and page.property('text') == '2' and commits.count() == 1
    enter(page, '1', accept=True)
    assert c.page == 1 and commits.count() == 2
    for invalid in ('', '0', '3'):
        enter(page, invalid)
        assert c.page == 1 and page.property('text') == '1' and commits.count() == 2
    enter(zoom, '125', accept=True)
    assert c.zoom == 125 and c.zoomMode == 'manual'
    for invalid in ('', '24', '301'):
        enter(zoom, invalid)
        assert c.zoom == 125 and zoom.property('text') == '125'
    c.goPage(2)
    c.setZoom(150)
    assert page.property('text') == '2' and zoom.property('text') == '150'
    first = c.active
    second = c.create_session(document(tmp_path, name='B'))
    c.activate(second.id)
    assert page.property('text') == '1'
    c.activate(first.id)
    assert page.property('text') == '2' and zoom.property('text') == '150'
    c.application.set_state(True, 'export')
    assert not page.isEnabled() and not zoom.isEnabled()
    assert c.active.document.isUndoAvailable() is False


def test_zoom_matches_requested_dpi_and_adjusts_from_fitted_scale(quick, tmp_path):
    c, _, _ = quick
    c.receive(document(tmp_path))
    c.viewport(619, 866)
    c.fit('width')
    assert c.zoom == 72
    c.request_render()
    assert c._inflight[-2] == 72
    c.setZoom(c.zoom + 25)
    assert c.zoomMode == 'manual' and c.zoom == 97
    c.request_render()
    assert c._queued[-2] == 97
    c.setZoom(100)
    c.request_render()
    assert c._queued[-2] == 100
    c.viewport(1214, 445)
    assert c.zoom == 100  # manual zoom survives resizing
    c.fit('page')
    assert c.zoom == 36
    c.request_render()
    assert c._queued[-2] == 36
    c.viewport(1214, 866)
    assert c.zoom == 72
    c.fit('width')
    assert c.zoom == 144
    c.viewport(10, 10)
    assert c.zoom == 25
    c.viewport(10000, 10000)
    assert c.zoom == 300


def test_pdf_coalescing_stale_page_result_and_crop_coordinates(quick, tmp_path, app):
    from PySide6.QtGui import QImage, QColor
    c, _, r = quick
    c.receive(document(tmp_path))
    c.render_timer.stop()
    c.request_render()
    first = r.commands.get_nowait()
    c.goPage(2)
    c.render_timer.stop()
    # Old page cannot apply, including the debounce interval.
    image = QImage(500, 700, QImage.Format.Format_RGB32)
    image.fill(QColor('white'))
    image.save(first[-1])
    c.render_finished('rendered', [first[1], 1, first[-1], (10, 20, 605, 862)])
    assert c.pdfImage == ''
    c.request_render()
    second = r.commands.get_nowait()
    assert isinstance(second[-2], int)
    image.save(second[-1])
    c.render_finished('rendered', [second[1], 2, second[-1], (10, 20, 605, 862)])
    app.processEvents()
    assert c.pdfImage.startswith('image://pdf/') and not Path(second[-1]).exists()
    before = c.active.document.toPlainText()
    c.crop(.1, .2, .3, .4)
    crop = r.commands.get_nowait()
    assert crop[0] == 'crop' and crop[-1] == pytest.approx((69.5, 188.4, 248, 525.2))
    assert not c.editable
    r.events.put(('cropped', 'assets/recorte.png'))
    c.application.poll()
    assert c.active.result.assets[-1].origin == 'manual'
    assert 'assets/recorte.png' in c.active.document.toPlainText()
    c.undo()
    assert c.active.document.toPlainText() == before


def test_batch_preparation_dedup_selection_stable_rows_and_outside_session(quick, tmp_path, monkeypatch):
    c, _, r = quick
    c.receive(document(tmp_path, 'Fora'))
    outside = c.active
    p1, p2 = tmp_path / 'one.pdf', tmp_path / 'two.pdf'
    monkeypatch.setattr(QFileDialog, 'getOpenFileNames', lambda *args: ([str(p1), str(p1), str(p2)], ''))
    c.newBatch()
    assert c.pendingCount == 2 and not c.batchRunning
    c.removePending(str(p2))
    c.beginBatch()
    command = r.commands.get_nowait()
    assert command[0] == 'batch_convert' and command[3] == str(p1)
    resets, changes = [], []
    c.documents.modelReset.connect(lambda: resets.append(1))
    c.documents.dataChanged.connect(lambda *args: changes.append(1))
    for n in range(1, 5):
        r.events.put(('batch', command[1], command[2], 'progress', n, 10))
        c.application.poll()
    assert not resets and not changes and c.batchCurrent == 4
    r.events.put(('batch', command[1], command[2], 'converted', document(tmp_path, 'one')))
    c.application.poll()
    assert not c.batchRunning and outside.id in c.sessions
    session = c.batch.items[0].session
    c.include(session.id, False)
    c.activate(session.id)
    assert c.selectedDocuments == 0 and c.active is session
    assert not resets
    assert any(row['key'] == outside.id and row['external'] for row in c.documents.rows)


def test_async_discard_native_cancel_retains_previous_and_close_confirmation(quick, tmp_path, monkeypatch):
    c, _, r = quick
    c.receive(document(tmp_path))
    old = c.active
    asked = []
    c.dialogRequested.connect(lambda *args: asked.append(args))
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *args: ('', ''))
    c.openPdf()
    assert asked[-1][2] == 'confirm'
    c.answer(False)
    assert c.active is old
    c.openPdf()
    c.answer(True)
    assert c.active is old and not c.application.busy
    closed = []
    c.closeApproved.connect(lambda: closed.append(True))
    c.requestClose()
    assert not closed
    c.answer(False)
    assert not closed
    c.requestClose()
    c.answer(True)
    assert closed and not r.alive


def test_link_snapshot_rejects_obsolete_and_keeps_history(quick, tmp_path):
    c, _, _ = quick
    c.receive(document(tmp_path, text='texto 💡'))
    c.selectionRequested.emit(0, 5)
    c.format('link', None)
    c.insertLink('texto', 'assets/figura.png')
    assert c.active.document.toPlainText() == '[texto](<assets/figura.png>) 💡'
    c.undo()
    assert c.active.document.toPlainText() == 'texto 💡'
    c.selectionRequested.emit(0, 5)
    c.format('link', None)
    cursor = QTextCursor(c.active.document)
    cursor.insertText('mudou ')
    before = c.active.document.toPlainText()
    c.insertLink('texto', 'outro')
    assert c.active.document.toPlainText() == before


def test_real_worker_quick_conversion_render_crop_and_export(app, tmp_path, manual_source):
    c = QuickController()
    engine = create_engine(c)
    window = engine.rootObjects()[0]
    warnings = engine.load_warnings
    engine.warnings.connect(lambda items: warnings.extend(i.toString() for i in items))
    c.application.start_polling()
    def wait(predicate):
        deadline = time.monotonic() + 25
        while not predicate():
            app.processEvents()
            QTest.qWait(5)
            assert time.monotonic() < deadline
        app.processEvents()
    try:
        assert c.application.startConversion(QUrl.fromLocalFile(str(manual_source)))
        wait(lambda: c.hasDocument and bool(c.pdfImage))
        assert c.editable and not c._images
        window.setProperty("tab", 1)
        wait(lambda: not c.previewPending)
        assert c._images
        before = c.active.document.toPlainText()
        c.crop(.1, .1, .2, .2)
        wait(lambda: c.editable)
        assert c.active.document.toPlainText() != before
        c.undo()
        assert c.active.document.toPlainText() == before
        c.setStripMarkers(True)
        vault = tmp_path / 'vault'
        vault.mkdir()
        assert c.start_export(vault)
        wait(lambda: c.editable)
        record = c.active.exports[str(vault.resolve())]
        assert (record.target / 'original.pdf').read_bytes() == manual_source.read_bytes()
        note = next(record.target.glob('*.md')).read_text()
        assert '<!-- Página' not in note
        assert not c.modified
        dialogs = []
        c.dialogRequested.connect(lambda *args: dialogs.append(args))
        original_target = record.target
        original_files = {path.relative_to(original_target): path.read_bytes()
                          for path in original_target.rglob('*') if path.is_file()}
        assert c.start_export(vault)
        wait(lambda: c.editable)
        assert c.active.exports[str(vault.resolve())].target == original_target
        assert len(list((vault / 'Importados').iterdir())) == 1
        assert dialogs[-1][0] == 'Documento já salvo'
        assert {path.relative_to(original_target): path.read_bytes()
                for path in original_target.rglob('*') if path.is_file()} == original_files

        c.setStripMarkers(False)
        assert c.start_export(vault)
        wait(lambda: c.editable)
        changed_target = c.active.exports[str(vault.resolve())].target
        assert changed_target != original_target
        assert '<!-- Página' in next(changed_target.glob('*.md')).read_text()
        c.replace(0, 0, 'Texto revisado.\n\n')
        assert c.start_export(vault)
        wait(lambda: c.editable)
        text_target = c.active.exports[str(vault.resolve())].target
        assert text_target not in (original_target, changed_target)
        assert next(text_target.glob('*.md')).read_text().startswith('Texto revisado.')

        other_vault = tmp_path / 'outro-vault'
        other_vault.mkdir()
        assert c.start_export(other_vault)
        wait(lambda: c.editable)
        other_target = c.active.exports[str(other_vault.resolve())].target
        assert other_target.parent == other_vault / 'Importados'
        import shutil
        shutil.rmtree(other_target)
        assert c.start_export(other_vault)
        wait(lambda: c.editable)
        assert other_target.is_dir() and dialogs[-1][0] == 'Nova cópia salva'
        assert (original_target / 'original.pdf').read_bytes() == manual_source.read_bytes()
        import pymupdf
        second = tmp_path / 'segundo.pdf'
        with pymupdf.open() as pdf:
            page = pdf.new_page()
            page.insert_text((50, 100), 'Segundo documento sintetico')
            pdf.save(second)
        outside = c.active
        c.pending_paths = [str(manual_source), str(second)]
        c.beginBatch()
        wait(lambda: not c.batchRunning)
        assert len(c.batch.items) == 2 and all(item.session for item in c.batch.items)
        assert outside.id in c.sessions
        first = c.batch.items[0].session
        c.activate(first.id)
        c.replace(0, 0, 'Edição revisada.\n\n')
        c.batch.export_selected(vault)
        wait(lambda: not c.batchRunning)
        assert all(item.export_status == 'Salvo' for item in c.batch.items)
        targets = [item.target for item in c.batch.items]
        c.batch.export_selected(vault)
        wait(lambda: not c.batchRunning)
        assert all(item.export_status == 'Já salvo' for item in c.batch.items)
        assert [item.target for item in c.batch.items] == targets
        c.activate(c.batch.items[0].session.id)
        assert c.start_export(vault)
        wait(lambda: c.editable)
        assert dialogs[-1][0] == 'Documento já salvo'
        assert c.active.exports[str(vault.resolve())].target == Path(targets[0])
        assert not warnings
    finally:
        c.render_timer.stop()
        c.preview_timer.stop()
        c.application.shutdown()
        window.setProperty('closingApproved', True)
        window.close()
        engine.deleteLater()
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()


def test_image_overlay_mouse_keyboard_and_resize_preserve_selection(quick, manual_source, tmp_path, app):
    from PySide6.QtCore import QPointF
    c, window, _ = quick
    c.receive(convert(manual_source, tmp_path / 'converted'))
    window.setProperty('tab', 1)
    c.setSelectionMode(True)
    app.processEvents()
    c.refresh_preview()
    app.processEvents()
    position = next(iter(c._images))
    overlay = next((item for item in c.preview.childItems() if item.objectName() == 'previewImage-' + str(position)), None)
    assert overlay is not None and overlay.width() > 20 and overlay.height() > 20
    window.requestActivate()
    point = overlay.mapToScene(QPointF(overlay.width() / 2, overlay.height() / 2)).toPoint()
    QTest.mouseClick(window, Qt.LeftButton, pos=point)
    app.processEvents()
    assert c.selectedImages == 1
    assert next(item for item in c.preview.childItems() if item.objectName() == overlay.objectName()) is overlay
    overlay.forceActiveFocus()
    QTest.keyClick(window, Qt.Key_Space)
    app.processEvents()
    assert c.selectedImages == 0
    QTest.keyClick(window, Qt.Key_Space)
    assert c.selectedImages == 1
    before = c.active.document.toPlainText()
    window.setWidth(1024)
    window.setHeight(700)
    QTest.qWait(120)
    app.processEvents()
    assert c.selectedImages == 1 and c.active.document.toPlainText() == before
    assert overlay.width() <= c.preview.width()


def test_native_font_scale_and_small_window_dialogs(quick, tmp_path, app):
    from PySide6.QtCore import QMetaObject
    from PySide6.QtGui import QFont
    c, window, _ = quick
    c.receive(document(tmp_path))
    before = c.active.document.toPlainText()
    window.setWidth(1024)
    window.setHeight(700)
    font = QFont(window.property('font'))
    font.setPointSizeF(font.pointSizeF() * 1.25)
    window.setProperty('font', font)
    app.processEvents()
    assert c.active.document.defaultFont().pixelSize() == round(15 * 1.25)
    assert c.active.document.toPlainText() == before
    for name in ('documents', 'filteredDialog', 'options', 'linkDialog'):
        dialog = window.findChild(QObject, name)
        assert QMetaObject.invokeMethod(dialog, 'open')
        app.processEvents()
        assert dialog.property('width') <= window.width() - 48
        assert dialog.property('height') <= window.height() - 48
        assert not window.grabWindow().isNull()
        QMetaObject.invokeMethod(dialog, 'close')


def test_worker_failure_preserves_document_and_allows_close(quick, tmp_path):
    c, _, runtime = quick
    c.receive(document(tmp_path))
    session = c.active
    runtime.alive = False
    c.application.poll()
    assert c.active is session and c.active.document.toPlainText()
    assert not c.application.workerAvailable
    c.requestClose()
    assert c._pending is not None
    c.answer(True)
    assert c.application._closed


def test_follow_page_does_not_move_selection_or_history(quick, tmp_path, app):
    c, window, _ = quick
    text = '<!-- Página 1 -->\n\n' + 'Primeira linha.\n' * 50 + '\n<!-- Página 2 -->\n\nÚltima.'
    c.receive(document(tmp_path, text=text))
    c.selectionRequested.emit(30, 22)
    before = c.selection()
    window.setProperty('follow', True)
    c._page = 2
    c.follow_page()
    app.processEvents()
    assert c.selection() == before
    assert c.active.document.toPlainText() == text
    assert not c.active.document.isUndoAvailable()
    window.setProperty('tab', 1)
    QTest.qWait(80)
    assert not c.previewPending
    assert c.preview.parentItem().parentItem().property('contentY') > 0
    assert c.selection() == before
    assert window.findChild(QQuickItem, 'markdownEditor') is c.editor


def test_live_view_snapshot_and_pdf_center_survive_switch(quick, tmp_path, app):
    from PySide6.QtGui import QImage, QColor
    c, window, runtime = quick
    c.receive(document(tmp_path, text='<!-- Página 1 -->\n\n' + 'Linha de revisão.\n' * 150))
    first_session = c.active
    app.processEvents()
    def deliver():
        c.render_timer.stop()
        c.request_render()
        command = runtime.commands.get_nowait()
        image = QImage(600, 1600, QImage.Format.Format_RGB32)
        image.fill(QColor('white'))
        image.save(command[-1])
        c.render_finished('rendered', [command[1], 1, command[-1], (0, 0, 595, 842)])
        app.processEvents()
    deliver()
    pdf = window.findChild(QQuickItem, 'pdfScroll')
    pdf.setProperty('contentY', 350)
    editor_scroll = c.editor.parentItem().parentItem()
    editor_scroll.setProperty('contentY', 200)
    center = (pdf.property('contentY') + pdf.height() / 2) / pdf.property('contentHeight')
    window.setProperty('tab', 1)
    second = c.create_session(document(tmp_path, 'B'))
    c.activate(second.id)  # Python-triggered switch also captures the live QML view.
    assert first_session.view['editorY'] == 200
    assert first_session.view['tab'] == 1
    assert first_session.view['pdfCenterY'] == pytest.approx(center)
    c.activate(first_session.id)
    app.processEvents()
    deliver()
    restored = (pdf.property('contentY') + pdf.height() / 2) / pdf.property('contentHeight')
    assert restored == pytest.approx(center, abs=.01)
    assert editor_scroll.property('contentY') == pytest.approx(200)


def test_open_and_edit_markdown_do_not_prepare_hidden_tools(quick, decorative_source, tmp_path, app, monkeypatch):
    from pdf_obsidian import quick as module
    from pdf_obsidian import restoration
    c, window, _ = quick
    result = convert(decorative_source, tmp_path / 'converted')
    builds = []
    original = module.preview_document
    def build(*args, **kwargs):
        builds.append(True)
        return original(*args, **kwargs)
    def unexpected(*args):
        raise AssertionError('Restoration must not be analysed while opening the editor.')
    monkeypatch.setattr(module, 'preview_document', build)
    monkeypatch.setattr(restoration, 'restoration_edit', unexpected)
    c.receive(result)
    QTest.qWait(350)
    assert c.editor.property('text') == result.markdown
    assert builds == [] and c._preview_doc is None and c.filtered.rowCount() == 0
    c.replace(0, 0, 'Revisão\n\n')
    QTest.qWait(350)
    assert builds == [] and not c.preview_timer.isActive()
    window.setProperty('tab', 1)
    QTest.qWait(80)
    app.processEvents()
    assert builds == [True] and not c.previewPending
    window.setProperty('tab', 0)
    window.setProperty('tab', 1)
    QTest.qWait(80)
    assert builds == [True]  # reuse the unchanged preview
    c.undo()
    assert c.active.document.toPlainText() == result.markdown


def test_filtered_review_is_serial_async_and_rejects_old_revisions(quick, decorative_source, tmp_path):
    from pdf_obsidian.restoration import restoration_edit
    c, _, runtime = quick
    result = convert(decorative_source, tmp_path / 'converted')
    c.receive(result)
    c.render_timer.stop()
    c.openFiltered()
    assert all(not row['restorable'] for row in c.filtered.rows)
    c.reviewFiltered(0)
    c.reviewFiltered(1)
    c.dispatch_filtered_review()
    command = runtime.commands.get_nowait()
    assert command[0] == 'review_filtered' and command[4] == 0
    c.dispatch_filtered_review()
    assert runtime.commands.empty()  # only one review enters the worker queue
    restoration_edit(result, command[-1], result.filtered_images[0])
    runtime.events.put(('filtered_checked', *command[1:5], ''))
    c.application.poll()
    assert c.filtered.rows[0]['restorable'] and not c.filtered.rows[1]['restorable']
    c.dispatch_filtered_review()
    second = runtime.commands.get_nowait()
    c.replace(0, 0, 'alteração\n\n')
    assert not c.filtered.rows[0]['restorable']  # invalidate immediately
    runtime.events.put(('filtered_checked', *second[1:5], ''))
    c.application.poll()
    assert not c.filtered.rows[1]['restorable']
    c.closeFiltered()
    assert not c._filtered_queue and not c.filtered_timer.isActive()


def test_toolbar_hover_is_subtle_and_preserves_markdown_selection(quick, tmp_path, app):
    from PySide6.QtCore import QPointF
    c, window, _ = quick
    c.receive(document(tmp_path, text='Texto a formatar'))
    app.processEvents()
    window.requestActivate()
    c.selectionRequested.emit(0, 5)
    button = window.findChild(QQuickItem, 'boldAction')
    assert button.property('compact') and button.property('description') == 'Negrito'
    point = button.mapToScene(QPointF(button.width() / 2, button.height() / 2)).toPoint()
    QTest.mouseMove(window, point)
    deadline = time.monotonic() + 1.5
    while button.property('background').property('color').name() != '#262626':
        QTest.qWait(10)
        assert time.monotonic() < deadline
    assert button.property('hovered')
    QTest.mouseClick(window, Qt.LeftButton, pos=point)
    app.processEvents()
    assert c.active.document.toPlainText() == '**Texto** a formatar'
    assert c.editor.hasActiveFocus()
    c.undo()
    assert c.active.document.toPlainText() == 'Texto a formatar'


def test_filtered_review_runs_in_real_worker_and_rechecks_restoration(app, decorative_source):
    from PySide6.QtCore import QMetaObject
    c = QuickController()
    engine = create_engine(c)
    window = engine.rootObjects()[0]
    c.application.start_polling()
    def wait(predicate):
        deadline = time.monotonic() + 25
        while not predicate():
            app.processEvents()
            QTest.qWait(5)
            assert time.monotonic() < deadline
        app.processEvents()
    try:
        c.application.start_conversion(decorative_source)
        wait(lambda: c.hasDocument and bool(c.pdfImage))
        assert c._preview_doc is None and c.filteredCount > 0
        c.openFiltered()
        dialog = window.findChild(QObject, 'filteredDialog')
        QMetaObject.invokeMethod(dialog, 'open')
        wait(lambda: c.filtered.rows[0]['restorable'])
        before = c.active.document.toPlainText()
        c.restoreImage(0)
        assert c.active.document.toPlainText() != before
        wait(lambda: 'já está incorporada' in c.filtered.rows[0]['issue'])
        assert not c.filtered.rows[0]['restorable']
        c.undo()
        wait(lambda: c.filtered.rows[0]['restorable'])
        assert c.active.document.toPlainText() == before
        QMetaObject.invokeMethod(dialog, 'close')
        assert not engine.load_warnings
    finally:
        c.shutdown()
        window.setProperty('closingApproved', True)
        window.close()
        engine.deleteLater()
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_lazy_preview_restores_reading_position_after_session_swap(quick, tmp_path, app):
    c, window, _ = quick
    text = '<!-- Página 1 -->\n\n' + '\n\n'.join(f'Parágrafo {n}: texto de revisão.' for n in range(150))
    c.receive(document(tmp_path, text=text))
    first = c.active
    window.setProperty('tab', 1)
    QTest.qWait(80)
    assert not c.previewPending
    scroll = c.preview.parentItem().parentItem()
    scroll.setProperty('contentY', 250)
    second = c.create_session(document(tmp_path, 'B'))
    c.activate(second.id)
    c.activate(first.id)
    QTest.qWait(80)
    app.processEvents()
    assert not c.previewPending
    assert scroll.property('contentY') == pytest.approx(250)


def test_grouped_toolbar_keyboard_menus_reverse_unicode_and_layout(quick, tmp_path, app):
    from PySide6.QtCore import QMetaObject
    from PySide6.QtGui import QFont
    c, window, _ = quick
    c.receive(document(tmp_path, text='ação 💡 texto'))
    window.requestActivate()
    app.processEvents()
    c.selectionRequested.emit(7, 0)
    style = window.findChild(QQuickItem, 'styleAction')
    style.forceActiveFocus()
    QTest.keyClick(window, Qt.Key_Space)
    app.processEvents()
    menu = window.findChild(QObject, 'styleMenu')
    assert menu.property('visible')
    assert menu.property('width') >= 180  # menu labels must not collapse to a narrow strip
    assert c.selection() == (7, 0)
    QTest.keyClick(window, Qt.Key_Down)
    QTest.keyClick(window, Qt.Key_Down)
    QTest.keyClick(window, Qt.Key_Return)
    app.processEvents()
    assert c.active.document.toPlainText().startswith('# ação 💡')
    assert c.editor.hasActiveFocus()
    c.undo()
    assert c.active.document.toPlainText() == 'ação 💡 texto'
    c.selectionRequested.emit(7, 0)
    bold = window.findChild(QQuickItem, 'boldAction')
    bold.forceActiveFocus()
    QTest.keyClick(window, Qt.Key_Space)
    assert c.active.document.toPlainText() == '**ação 💡** texto'
    assert c.editor.hasActiveFocus()
    c.undo()
    base_font = QFont(window.property('font'))
    for scale in (1, 1.25):
        font = QFont(base_font)
        font.setPointSizeF(base_font.pointSizeF() * scale)
        window.setProperty('font', font)
        for width, height in ((1300, 850), (1024, 700)):
            window.resize(width, height)
            for visible in (True, False):
                window.setProperty('pdfVisible', visible)
                QTest.qWait(60)
                toolbar = window.findChild(QQuickItem, 'editorToolbar')
                for name in ('style', 'bold', 'italic', 'link', 'bullet', 'ordered', 'quote', 'align'):
                    button = window.findChild(QQuickItem, name + 'Action')
                    assert button.width() >= 30 and button.height() >= 30
                    position = button.mapToItem(toolbar, button.boundingRect().topLeft())
                    assert position.x() >= 0 and position.x() + button.width() <= toolbar.width() + 1
                assert window.grabWindow().save(f'/tmp/toolbar-{width}-{scale}-{visible}.png')
    window.resize(800, 700)
    window.setProperty('pdfVisible', True)
    window.setProperty('pdfFraction', .55)
    QTest.qWait(100)
    paragraph = window.findChild(QQuickItem, 'paragraphTools')
    assert paragraph.y() > 0  # whole paragraph group wraps, including its separator
    assert paragraph.x() == 0
    assert paragraph.property('padding') == 3  # group outline remains complete after wrapping
    style.forceActiveFocus()
    QTest.keyClick(window, Qt.Key_Tab)
    assert bold.hasActiveFocus()
    assert c.start_export(tmp_path)
    assert not bold.isEnabled()
    assert not style.isEnabled()


@pytest.mark.parametrize('width,height', [(800, 600), (1024, 700), (1300, 850)])
@pytest.mark.parametrize('scale', [1, 1.25])
def test_review_controls_fit_supported_windows(quick, tmp_path, app, width, height, scale):
    """Long document names must not push saving or PDF controls off screen."""
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QFont
    c, window, _ = quick
    result = document(tmp_path, name='Guia de estudo com um título muito extenso ' * 5)
    c.receive(result)
    original = c.active.document
    font = QFont(window.property('font'))
    font.setPointSizeF(font.pointSizeF() * scale)
    window.setProperty('font', font)
    window.resize(width, height)
    QTest.qWait(80)
    assert window.width() == width and window.height() == height
    for name in ('saveAction', 'documentTitle', 'documentSaveStatus', 'pageField', 'zoomField', 'cropAction'):
        item = window.findChild(QQuickItem, name)
        point = item.mapToScene(QPointF(0, 0))
        assert item.isVisible() and item.width() > 0
        assert point.x() >= 0 and point.x() + item.width() <= width + 1
        assert point.y() >= 0 and point.y() + item.height() <= height + 1
    toolbar = window.findChild(QQuickItem, 'pdfToolbar')
    for name in ('pageTools', 'zoomTools'):
        group = window.findChild(QQuickItem, name)
        assert group.x() >= 0 and group.x() + group.width() <= toolbar.width() + 1
    assert c.active.document is original
    assert original.toPlainText() == result.markdown
    assert window.findChild(QQuickItem, 'markdownEditor').height() > 100
    save = window.findChild(QQuickItem, 'saveAction')
    before = save.mapToScene(QPointF(0, 0))
    before_width = save.width()
    c.application.set_state(True, 'export')
    app.processEvents()
    assert save.width() == pytest.approx(before_width)
    assert save.mapToScene(QPointF(0, 0)) == before
    c.application.set_state(False, '')


def test_long_confirmation_scrolls_without_hiding_actions_and_restores_focus(quick, tmp_path, app):
    from PySide6.QtCore import QMetaObject, QPointF
    from PySide6.QtGui import QFont
    c, window, _ = quick
    c.receive(document(tmp_path, text='ação 💡 texto'))
    window.resize(800, 600)
    font = QFont(window.property('font'))
    font.setPointSizeF(font.pointSizeF() * 1.25)
    window.setProperty('font', font)
    window.requestActivate()
    save = window.findChild(QQuickItem, 'saveAction')
    save.forceActiveFocus()
    app.processEvents()
    original = c.active.document
    confirmed = []
    c.confirm('Mensagem extensa para testar a rolagem. ' * 150, lambda: confirmed.append(True))
    app.processEvents()
    modal = window.findChild(QObject, 'messageDialog')
    assert modal.property('visible')
    assert modal.property('height') <= window.height() - 48
    message = window.findChild(QQuickItem, 'messageText')
    assert message.height() > modal.property('contentItem').height()
    cancel = window.findChild(QQuickItem, 'messageCancelAction')
    assert cancel.hasActiveFocus()  # opening a destructive dialog starts on its safe action
    for name in ('messageCancelAction', 'discardAction'):
        button = window.findChild(QQuickItem, name)
        point = button.mapToScene(QPointF(0, 0))
        assert 0 <= point.y() < window.height()
        assert point.y() + button.height() <= window.height()
    QTest.keyClick(window, Qt.Key_Escape)
    app.processEvents()
    assert not modal.property('visible') and c._pending is None
    assert not confirmed and save.hasActiveFocus()
    assert c.active.document is original and original.toPlainText() == 'ação 💡 texto'
    # Other dialogs return focus to their invoker as well.
    options = window.findChild(QObject, 'options')
    assert QMetaObject.invokeMethod(options, 'open')
    app.processEvents()
    QTest.keyClick(window, Qt.Key_Escape)
    app.processEvents()
    assert save.hasActiveFocus()


def test_review_tabs_and_comparison_divider_work_with_keyboard(quick, tmp_path, app):
    c, window, _ = quick
    c.receive(document(tmp_path, text='ação 💡 texto'))
    window.requestActivate()
    QTest.qWait(50)
    c.selectionRequested.emit(7, 0)
    c.format('bold', None)
    original = c.active.document
    before = original.toPlainText()
    divider = window.findChild(QQuickItem, 'comparisonDivider')
    panel = window.findChild(QQuickItem, 'pdfPanel')
    divider.forceActiveFocus()
    width = panel.width()
    QTest.keyClick(window, Qt.Key_Left)
    QTest.qWait(30)
    assert panel.width() < width
    QTest.keyClick(window, Qt.Key_Right)
    QTest.qWait(30)
    assert abs(panel.width() - width) <= 1
    markdown = window.findChild(QQuickItem, 'markdownTab')
    preview = window.findChild(QQuickItem, 'previewTab')
    markdown.forceActiveFocus()
    QTest.keyClick(window, Qt.Key_Right)
    app.processEvents()
    assert window.property('tab') == 1 and preview.hasActiveFocus()
    QTest.keyClick(window, Qt.Key_Left)
    app.processEvents()
    assert window.property('tab') == 0 and markdown.hasActiveFocus()
    assert c.active.document is original and original.toPlainText() == before
    c.undo()
    assert original.toPlainText() == 'ação 💡 texto'


def test_opening_long_document_and_restoring_collapsed_cursor(quick, tmp_path, app):
    """A new document starts at its beginning; returning preserves an unselected cursor."""
    c, window, _ = quick
    text = '# Início\n\n' + 'Parágrafo para conferir a posição inicial.\n\n' * 100
    c.receive(document(tmp_path, text=text))
    QTest.qWait(80)
    first = c.active
    assert c.editor.property('cursorPosition') == 0
    assert c.selection() == (0, 0)
    c.editor.setProperty('cursorPosition', 750)
    second = c.create_session(document(tmp_path, name='Outro'))
    c.activate(second.id)
    QTest.qWait(50)
    c.activate(first.id)
    QTest.qWait(80)
    assert c.editor.property('cursorPosition') == 750
    assert c.selection() == (750, 750)
    assert first.document.toPlainText() == text and not first.document.isUndoAvailable()


def test_batch_escape_cancels_from_fixed_footer(quick, tmp_path, app):
    """Moving actions outside the scrolling body must preserve Escape cancellation."""
    from PySide6.QtCore import QMetaObject
    c, window, _ = quick
    assert c.batch.start([tmp_path / 'sintetico.pdf'])
    dialog = window.findChild(QObject, 'documents')
    assert QMetaObject.invokeMethod(dialog, 'open')
    window.requestActivate()
    app.processEvents()
    cancel = window.findChild(QQuickItem, 'batchCancelAction')
    cancel.forceActiveFocus()
    QTest.keyClick(window, Qt.Key_Escape)
    app.processEvents()
    assert c.batch.cancel_requested and c.batchCancelling
    assert dialog.property('visible')  # wait for the running worker to finish safely


def test_general_warning_has_no_fake_page_and_page_warning_navigates(quick, tmp_path, app):
    from PySide6.QtCore import QPointF
    from pdf_obsidian.models import Warning
    c, window, _ = quick
    result = document(tmp_path)
    result.warnings = [Warning(0, 'Conversão heurística: revise o resultado.'), Warning(2, 'Confira a figura.')]
    c.receive(result)
    app.processEvents()
    window.setProperty('warningsExpanded', True)
    window.requestActivate()
    QTest.qWait(60)
    warning_list = window.findChild(QQuickItem, 'warningsList')
    rows = {item.objectName(): item for item in warning_list.property('contentItem').childItems()}
    general = rows.get('warning-0')
    assert general is not None and not general.isEnabled()
    assert general.property('contentItem').property('text').startswith('Geral · ')
    assert c.page == 1
    specific = rows['warning-2']
    assert specific.isEnabled()
    point = specific.mapToScene(QPointF(specific.width() / 2, specific.height() / 2)).toPoint()
    QTest.mouseClick(window, Qt.LeftButton, pos=point)
    app.processEvents()
    assert c.page == 2 and window.property('pdfVisible')


def test_worker_failure_cancels_confirmation_and_close_can_be_requested_again(quick, tmp_path, app):
    c, w, runtime = quick
    c.receive(document(tmp_path))
    actions = []
    c.confirm('Descartar?', lambda: actions.append('discarded'))
    app.processEvents()
    c.worker_failed()
    app.processEvents()
    dialog = w.findChild(QObject, 'messageDialog')
    assert not dialog.property('confirmation') and c._pending is None
    cancel = w.findChild(QQuickItem, 'messageCancelAction')
    QTest.mouseClick(w, Qt.LeftButton, pos=cancel.mapToScene(cancel.boundingRect().center()).toPoint())
    QTest.qWait(150)
    c.requestClose()
    app.processEvents()
    assert dialog.property('confirmation') and c._pending is not None
    c.answer(False)
    assert not actions


def test_info_is_queued_until_confirmation_resolves(quick, tmp_path, app):
    c, w, runtime = quick
    c.receive(document(tmp_path))
    actions = []
    c.confirm('Descartar?', lambda: actions.append('discarded'))
    c.dialogRequested.emit('Informação', 'Resultado', 'info')
    app.processEvents()
    dialog = w.findChild(QObject, 'messageDialog')
    assert dialog.property('confirmation')
    assert w.property('messageQueue').toVariant()[0]['title'] == 'Informação'
    cancel = w.findChild(QQuickItem, 'messageCancelAction')
    QTest.mouseClick(w, Qt.LeftButton, pos=cancel.mapToScene(cancel.boundingRect().center()).toPoint())
    QTest.qWait(200)
    assert dialog.property('visible') and not dialog.property('confirmation')
    assert dialog.property('title') == 'Informação'
    assert c._pending is None and not actions


def test_split_geometry_restores_after_keyboard_resize(quick, tmp_path, app):
    c, w, runtime = quick
    c.receive(document(tmp_path))
    a = c.active
    QTest.qWait(60)
    panel = w.findChild(QQuickItem, 'pdfPanel')
    divider = w.findChild(QQuickItem, 'comparisonDivider')
    w.requestActivate()
    divider.forceActiveFocus()
    QTest.keyClick(w, Qt.Key_Left)
    QTest.qWait(60)
    a_width = panel.width()
    b = c.create_session(document(tmp_path, name='B'))
    c.activate(b.id)
    QTest.qWait(60)
    divider.forceActiveFocus()
    QTest.keyClick(w, Qt.Key_Right)
    QTest.keyClick(w, Qt.Key_Right)
    QTest.qWait(60)
    assert abs(panel.width() - a_width) > 30
    c.activate(a.id)
    QTest.qWait(60)
    assert abs(panel.width() - a_width) < 2


def test_discard_button_resolves_confirmation_once(quick, app):
    c, w, runtime = quick
    calls = []
    c.confirm('Descartar?', lambda: calls.append('accepted'))
    QTest.qWait(100)
    button = w.findChild(QQuickItem, 'discardAction')
    QTest.mouseClick(w, Qt.LeftButton, pos=button.mapToScene(button.boundingRect().center()).toPoint())
    QTest.qWait(150)
    assert calls == ['accepted'] and c._pending is None
    c.answer(True)
    assert calls == ['accepted']


def test_option_dirty_indicator_and_close_after_undo(quick, tmp_path, app):
    c, w, runtime = quick
    c.receive(document(tmp_path))
    session = c.active
    session.record_export(tmp_path, 'signature', tmp_path / 'absent', {})
    c.replace(0, 0, 'Edicao ')
    c.setStripMarkers(True)
    c.undo()
    assert not session.document.isModified() and c.modified
    c.requestClose()
    app.processEvents()
    assert c._pending is not None
    c.answer(False)
    c.setStripMarkers(False)
    assert not c.modified


def test_monochrome_review_reading_column_and_durable_highlighter(quick, tmp_path, app):
    c, window, _ = quick
    assert window.property('color').name() == '#090909'
    a = c.create_session(document(tmp_path, text='# Título\n\n💡 **texto**'))
    c.activate(a.id)
    app.processEvents()
    assert window.property('color').name() == '#090909'
    highlighter = a.document.markdown_highlighter
    c.selectionRequested.emit(12, 3)
    c.replace(0, 0, 'Revisão\n')
    edited = a.document.toPlainText()
    b = c.create_session(document(tmp_path, 'B'))
    c.activate(b.id)
    c.activate(a.id)
    assert a.document.markdown_highlighter is highlighter
    assert highlighter.document() is a.document
    window.setProperty('pdfVisible', False)
    app.processEvents()
    assert c.editor.width() == pytest.approx(760)
    assert c.editor.x() == pytest.approx((c.editor.parentItem().width() - 760) / 2)
    c.undo()
    assert a.document.toPlainText() == '# Título\n\n💡 **texto**'
    c.redo()
    assert a.document.toPlainText() == edited


def test_reduced_motion_is_visual_global_and_preserves_document_history(quick, tmp_path, app):
    from PySide6.QtCore import QMetaObject
    c, window, _ = quick
    settings = c.visualSettings
    old = settings.reducedMotion
    c.receive(document(tmp_path, text='ação 💡 texto'))
    source = c.active.document
    c.replace(0, 0, 'Revisão\n')
    edited = source.toPlainText()
    source.setModified(False)
    try:
        options = window.findChild(QObject, 'options')
        QMetaObject.invokeMethod(options, 'open')
        action = window.findChild(QQuickItem, 'reducedMotionAction')
        action.forceActiveFocus()
        QTest.keyClick(window, Qt.Key_Space)
        app.processEvents()
        assert settings.reducedMotion != old
        assert window.findChild(QObject, 'importPage').property('reducedMotion') == settings.reducedMotion
        assert source.toPlainText() == edited and not c.active.modified
        QMetaObject.invokeMethod(options, 'close')
        other = c.create_session(document(tmp_path, 'Outra'))
        previous = c.active.id
        c.activate(other.id)
        assert settings.reducedMotion != old
        c.activate(previous)
        c.undo()
        assert source.toPlainText() == 'ação 💡 texto'
        c.redo()
        assert source.toPlainText() == edited
    finally:
        settings.setReducedMotion(old)


def test_preview_image_delegates_are_removed_before_replacing_document(quick, manual_source, tmp_path, app):
    from PySide6.QtCore import qInstallMessageHandler
    c, window, _ = quick
    c.receive(convert(manual_source, tmp_path / 'rendered'))
    window.setProperty('tab', 1)
    deadline = time.monotonic() + 2
    while not c.previewReady:
        QTest.qWait(10)
        assert time.monotonic() < deadline
    assert c._images
    messages = []
    previous = qInstallMessageHandler(lambda kind, context, text: messages.append(text))
    try:
        c.receive(document(tmp_path, 'Curto', 'Uma nota curta, sem imagens.'))
        QTest.qWait(80)
        assert not c._images
        assert not any('out of range' in message for message in messages), messages
    finally:
        qInstallMessageHandler(previous)


@pytest.mark.parametrize('tagged', [False, True])
def test_ocr_mode_is_captured_before_conversion_and_stage_is_displayed(quick, tmp_path, app, tagged):
    from pdf_obsidian.recognition import ConversionOptions
    c, window, runtime = quick
    page = window.findChild(QObject, 'importPage')
    action = window.findChild(QQuickItem, 'ocrModeAction')
    action.forceActiveFocus()
    QTest.keyClick(window, Qt.Key_Space)
    app.processEvents()
    assert c.application.ocrMode == 'off' and page.property('ocrMode') == 'off'
    c.application.tagged_operations = tagged
    assert c.application.start_conversion(tmp_path/'synthetic.pdf')
    command = runtime.commands.get_nowait()
    assert command[0] == ('session_convert' if tagged else 'convert') and command[-1] == ConversionOptions('off')
    token = command[1] if tagged else None
    c.application.setOcrMode('auto')
    assert c.application.ocrMode == 'off'  # live jobs cannot be reconfigured
    if tagged:
        runtime.events.put(('session_event','stale','stage','Não deve aparecer'))
    runtime.events.put(('session_event',token,'stage','Página 1 de 2 · reconhecendo texto…') if tagged else ('stage','Página 1 de 2 · reconhecendo texto…'))
    c.application.poll()
    app.processEvents()
    assert page.property('conversionStage') == 'Página 1 de 2 · reconhecendo texto…'
    runtime.events.put(('session_event',token,'cancelled') if tagged else ('cancelled',))
    c.application.poll()
    assert not c.application.conversionStage
    c.application.setOcrMode('auto')
    assert c.application.ocrMode == 'auto'


def test_next_conversion_ocr_option_does_not_modify_current_document(quick,tmp_path,app):
    from PySide6.QtCore import QMetaObject
    c,window,_=quick
    c.receive(document(tmp_path,text='Texto original.'))
    doc=c.active.document
    doc.setModified(False)
    options=window.findChild(QObject,'options');QMetaObject.invokeMethod(options,'open')
    action=window.findChild(QQuickItem,'nextOcrModeAction')
    action.forceActiveFocus();QTest.keyClick(window,Qt.Key_Space);app.processEvents()
    assert c.application.ocrMode=='off'
    assert doc.toPlainText()=='Texto original.' and not c.active.modified
    assert c.active.document is doc and not doc.isUndoAvailable()
    QMetaObject.invokeMethod(options,'close')
