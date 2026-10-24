"""Integração da importação QML com o worker real e recuperação Widgets."""
import hashlib
from queue import Queue
import time

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtQuick import QQuickItem, QQuickWindow
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QFileDialog, QMessageBox

from pdf_obsidian import gui


@pytest.fixture
def imported_ui(app, monkeypatch):
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.Yes)
    monkeypatch.setattr(QMessageBox, 'information', lambda *args: QMessageBox.Ok)
    errors = []
    monkeypatch.setattr(QMessageBox, 'critical', lambda *args: errors.append(args[-1]))
    window = gui.Window()
    window.show()
    window.activateWindow()
    app.processEvents()
    warnings = []
    window.welcome.quick.engine().warnings.connect(lambda items: warnings.extend(item.toString() for item in items))

    def wait(predicate=None):
        predicate = predicate or (lambda: not window.busy and not window.batch.running)
        deadline = time.monotonic() + 20
        while not predicate():
            app.processEvents()
            QTest.qWait(5)
            assert time.monotonic() < deadline, 'A operação não terminou.'
        app.processEvents()

    try:
        yield window, wait, errors
        assert not warnings
        assert not errors
    finally:
        if window.batch_dialog is not None:
            window.batch_dialog.reject()
        if window.batch.running:
            window.batch.cancel()
            wait()
        for session in window.sessions.values():
            session.document.setModified(False)
        window.editor.document().setModified(False)
        window.close()
        app.processEvents()


def action(window, name):
    result = window.welcome.quick.rootObject().findChild(QQuickItem, name)
    assert result is not None
    return result


def click(window, name):
    item = action(window, name)
    point = item.mapToScene(QPointF(item.width() / 2, item.height() / 2)).toPoint()
    QTest.mouseClick(window.welcome.quick, Qt.LeftButton, pos=point)


def test_import_keyboard_has_one_global_shortcut_and_opens_batch(imported_ui, app, monkeypatch):
    window, _, _ = imported_ui
    selected = []
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *args: selected.append(True) or ('', ''))
    assert window.welcome.using_qml
    assert window.content.currentWidget() is window.welcome and window.header.isHidden()
    window.welcome.focus_primary()
    app.processEvents()
    QTest.keyClick(window.welcome.quick, Qt.Key_O, Qt.ControlModifier)
    assert selected == [True]
    window.welcome.focus_primary()
    QTest.keyClick(window.welcome.quick, Qt.Key_Space)
    assert selected == [True, True]
    QTest.keyClick(window.welcome.quick, Qt.Key_Tab)
    assert action(window, 'batchAction').hasActiveFocus()
    QTest.keyClick(window.welcome.quick, Qt.Key_Backtab)
    assert action(window, 'openPdfAction').hasActiveFocus()
    QTest.keyClick(window.welcome.quick, Qt.Key_Tab)
    QTest.keyClick(window.welcome.quick, Qt.Key_Space)
    assert window.batch_dialog is not None and window.batch_dialog.preparing
    assert not window.busy and window.result is None
    assert window.workspaces == []


def test_real_conversion_from_qml_reuses_worker_and_editor(imported_ui, manual_source, monkeypatch):
    window, wait, _ = imported_ui
    controller, worker = window.application, window.worker
    digest = hashlib.sha256(manual_source.read_bytes()).hexdigest()
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *args: (str(manual_source), 'PDF'))
    click(window, 'openPdfAction')
    assert window.welcome.state['converting']
    assert not action(window, 'openPdfAction').isVisible()
    assert action(window, 'cancelAction').isVisible()
    assert window.welcome.state['sourceName'] == manual_source.name
    wait(lambda: window.result is not None and not window.busy)
    assert window.application is controller and window.worker is worker
    assert window.content.currentWidget() is window.workspace
    assert not window.header.isHidden()
    assert window.displayed_page == 1
    assert 'Texto essencial' in window.editor.toPlainText()
    original = window.editor.toPlainText()
    window.editor.moveCursor(QTextCursor.End)
    window.editor.insertPlainText('\n💡 Edição após importar por QML.')
    window.editor.undo()
    assert window.editor.toPlainText() == original
    assert not list(manual_source.parent.rglob('Importados'))
    assert hashlib.sha256(manual_source.read_bytes()).hexdigest() == digest


@pytest.mark.parametrize('terminal', ['cancelled', 'error'])
def test_progress_and_return_keep_document_history(imported_ui, manual_source, monkeypatch, app, terminal):
    window, wait, errors = imported_ui
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *args: (str(manual_source), 'PDF'))
    window.open_pdf()
    wait(lambda: window.result is not None and not window.busy)
    window.follow_page.setChecked(False)
    window.set_manual_zoom(125)
    wait()
    document = window.editor.document()
    source_text = document.toPlainText()
    window.editor.moveCursor(QTextCursor.End)
    window.editor.insertPlainText('\n💡 Revisão conservada.')
    edited = window.editor.toPlainText()
    cursor = window.editor.textCursor()
    cursor.setPosition(document.characterCount() - 1)
    cursor.setPosition(document.characterCount() - 9, QTextCursor.KeepAnchor)
    window.editor.setTextCursor(cursor)
    saved_cursor = (cursor.anchor(), cursor.position())
    result = window.result
    worker = window.worker
    runtime = window.application.runtime
    # Hold only transport delivery to make progress/cancellation deterministic;
    # restore the real channels before teardown and keep the same worker alive.
    with monkeypatch.context() as transport:
        commands, events = Queue(), Queue()
        transport.setattr(runtime, 'commands', commands)
        transport.setattr(runtime, 'events', events)
        window.open_pdf()
        assert commands.get_nowait()[0] == 'convert'
        app.processEvents()
        progress = action(window, 'conversionProgress')
        assert progress.property('indeterminate')
        events.put(('progress', 3, 10))
        window.poll()
        assert not progress.property('indeterminate')
        assert progress.property('value') == 3 and progress.property('to') == 10
        assert not window.welcome.state['canImport']
        if terminal == 'cancelled':
            click(window, 'cancelAction')
            assert window.application.cancellationRequested
            assert window.welcome.state['cancelling']
            assert not action(window, 'cancelAction').isEnabled()
            window.application.cancelConversion()
            events.put(('cancelled',))
        else:
            events.put(('error', 'Falha sintética de importação', ''))
        window.poll()
        app.processEvents()
    if terminal == 'error':
        assert errors.pop() == 'Falha sintética de importação'
    assert window.worker is worker and worker.is_alive()
    assert window.result is result and window.editor.document() is document
    assert window.editor.toPlainText() == edited
    assert (window.editor.textCursor().anchor(), window.editor.textCursor().position()) == saved_cursor
    assert window.zoom_mode == 'manual' and window.zoom_percent == 125
    assert window.content.currentWidget() is window.workspace
    assert not window.application.cancellationRequested
    window.editor.undo()
    assert window.editor.toPlainText() == source_text


def test_initial_failure_returns_to_qml(imported_ui, tmp_path, monkeypatch):
    window, wait, errors = imported_ui
    source = tmp_path / 'invalido.pdf'
    source.write_bytes(b'PDF sintetico invalido')
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *args: (str(source), 'PDF'))
    click(window, 'openPdfAction')
    wait()
    assert errors.pop()
    assert window.result is None and window.content.currentWidget() is window.welcome
    assert window.welcome.state['canImport']
    assert action(window, 'openPdfAction').isVisible()


def test_batch_and_document_access_from_import_header(imported_ui, manual_source, app):
    window, wait, _ = imported_ui
    worker = window.worker
    click(window, 'batchAction')
    dialog = window.batch_dialog
    dialog.paths = [str(manual_source)]
    dialog.refresh()
    dialog.start.click()
    wait()
    assert window.result is None and window.welcome.state['documentCount'] == 1
    assert window.batch.items[0].session is not None
    dialog.close()
    app.processEvents()
    assert window.batch_dialog is None
    assert action(window, 'documentsAction').isVisible()
    click(window, 'documentsAction')
    dialog = window.batch_dialog
    assert dialog is not None and not dialog.preparing
    dialog.review.click()
    wait()
    assert window.content.currentWidget() is window.workspace
    assert window.worker is worker
    assert not list(manual_source.parent.rglob('Importados'))


def test_fallback_load_failure_can_convert(app, monkeypatch, tmp_path, manual_source):
    original = gui.ImportPanel
    monkeypatch.setattr(gui, 'ImportPanel', lambda parent: original(parent, qml_source=tmp_path / 'missing.qml'))
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *args: (str(manual_source), 'PDF'))
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.Yes)
    window = gui.Window()
    try:
        window.show()
        app.processEvents()
        assert not window.welcome.using_qml
        assert window.welcome.fallback is not None
        assert 'Widgets' in window.statusBar().currentMessage()
        worker = window.worker
        window.welcome.fallback.open_button.click()
        deadline = time.monotonic() + 20
        while window.result is None or window.busy:
            app.processEvents()
            QTest.qWait(5)
            assert time.monotonic() < deadline
        assert window.worker is worker
        assert window.content.currentWidget() is window.workspace
        assert 'Texto essencial' in window.editor.toPlainText()
    finally:
        window.editor.document().setModified(False)
        window.close()
        app.processEvents()


def test_scene_error_keeps_progress_and_worker(imported_ui, app):
    window, _, _ = imported_ui
    worker = window.worker
    window.busy, window.operation = True, 'convert'
    window.update_controls()
    window.application.set_conversion_stage('Reconhecendo página 2 de 5…')
    window.welcome.update_state(sourceName='sintetico.pdf', progressCurrent=2, progressTotal=5)
    window.welcome.quick.sceneGraphError.emit(QQuickWindow.SceneGraphError.ContextNotAvailable, 'Falha gráfica sintética')
    assert not window.welcome.using_qml
    assert window.welcome.fallback.source.text() == 'sintetico.pdf'
    assert window.welcome.fallback.progress.value() == 2
    assert window.welcome.fallback.progress.maximum() == 5
    assert window.welcome.fallback.stage.text() == 'Reconhecendo página 2 de 5…'
    app.processEvents()
    assert window.welcome.quick.rootObject() is None
    assert window.worker is worker and worker.is_alive()
    assert 'Widgets' in window.statusBar().currentMessage()
    window.welcome.fallback.cancel.click()
    assert window.application.cancellationRequested
    assert not window.welcome.fallback.cancel.isEnabled()
    assert 'com segurança' in window.welcome.fallback.stage.text()
    window.busy, window.operation = False, None


def test_close_during_conversion_stops_worker(imported_ui, tmp_path, monkeypatch):
    window, _, _ = imported_ui
    runtime = window.application.runtime
    with monkeypatch.context() as transport:
        queue = Queue()
        transport.setattr(runtime, 'commands', queue)
        assert window.application.start_conversion(tmp_path / 'sintetico.pdf')
        window.update_controls()
    root = window.root
    window.close()
    assert not window.worker.is_alive()
    assert not root.exists()
    assert not window.application.poll_timer.isActive()


def test_application_font_change_reaches_qml_under_qss(imported_ui, app):
    window, _, _ = imported_ui
    original = app.font()
    enlarged = app.font()
    enlarged.setPointSizeF(enlarged.pointSizeF() * 1.25)
    before = window.welcome.state['textScale']
    try:
        app.setFont(enlarged)
        app.processEvents()
        assert window.welcome.state['textScale'] == pytest.approx(before * 1.25)
        root = window.welcome.quick.rootObject()
        assert root.property('textScale') == pytest.approx(before * 1.25)
        window.resize(1024, 700)
        app.processEvents()
        assert window.width() == 1024 and window.height() == 700
        assert action(window, 'openPdfAction').isVisible()
        assert action(window, 'batchAction').isVisible()
    finally:
        app.setFont(original)
        app.processEvents()


def test_reopen_veto_and_file_dialog_cancel_keep_edits(imported_ui, manual_source, monkeypatch, app):
    window, wait, _ = imported_ui
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *args: (str(manual_source), 'PDF'))
    click(window, 'openPdfAction')
    wait(lambda: window.result is not None and not window.busy)
    document = window.editor.document()
    window.editor.moveCursor(QTextCursor.End)
    window.editor.insertPlainText('\nRevisão não exportada.')
    edited = window.editor.toPlainText()
    workspaces = window.workspaces.copy()
    selected, prompted = [], []
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *args: selected.append(True) or ('', ''))
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: prompted.append(True) or QMessageBox.No)
    window.editor.setFocus()
    app.processEvents()
    wait(lambda: not window.busy and not window.render_timer.isActive() and window.open_button.isEnabled())
    QTest.keyClick(window.editor, Qt.Key_O, Qt.ControlModifier)
    assert prompted == [True] and selected == []
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.Yes)
    QTest.keyClick(window.editor, Qt.Key_O, Qt.ControlModifier)
    assert selected == [True]
    assert window.content.currentWidget() is window.workspace
    assert window.editor.document() is document
    assert window.editor.toPlainText() == edited
    assert window.workspaces == workspaces
    assert document.isModified()
