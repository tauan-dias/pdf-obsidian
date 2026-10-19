"""Lotes e sessões Qt usando exclusivamente PDFs e vaults sintéticos."""
from pathlib import Path
from queue import Queue
import shutil
import threading
import time

import pymupdf
import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtTest import QTest, QSignalSpy
from PySide6.QtWidgets import QFileDialog, QMessageBox, QHeaderView

from pdf_obsidian.converter import convert, file_hash
from pdf_obsidian.exporter import export_document, export_signature
from pdf_obsidian.gui import Window
from pdf_obsidian.worker import run


@pytest.fixture
def sources(tmp_path):
    paths = []
    for index in range(3):
        source = tmp_path / f'estudo-{index}.pdf'
        with pymupdf.open() as doc:
            for number in range(2):
                page = doc.new_page(width=595 + index * 30, height=842)
                page.insert_text((48, 90), f'Estudo {index}, capitulo {number+1}', fontsize=20)
                for line in range(7):
                    page.insert_text((48, 140 + line * 17), f'Paragrafo {line}: conteudo sintetico para revisar.', fontsize=12)
                page.draw_rect(pymupdf.Rect(70, 280, 230, 340), color=(.2, .4, .6), fill=(.7, .8, .9))
                for line in range(20):
                    page.insert_text((48, 380 + line * 17), f'Texto complementar {line} para conferir a leitura.', fontsize=12)
            doc.save(source)
        paths.append(source)
    return paths


@pytest.fixture
def loaded_window(app, monkeypatch):
    monkeypatch.setattr(QMessageBox, 'question', lambda *a: QMessageBox.Yes)
    monkeypatch.setattr(QMessageBox, 'information', lambda *a: QMessageBox.Ok)
    errors = []
    monkeypatch.setattr(QMessageBox, 'critical', lambda *a: errors.append(a[-1]))
    window = Window()
    window.show()
    window.activateWindow()
    app.processEvents()
    def wait(predicate=None):
        if predicate is None:
            predicate = lambda: not window.busy and not window.batch.running
        deadline = time.monotonic() + 20
        while not predicate():
            app.processEvents()
            QTest.qWait(5)
            assert time.monotonic() < deadline, 'Operação não terminou.'
        app.processEvents()
    try:
        yield window, wait, errors
        assert not errors
    finally:
        if window.batch_dialog:
            window.batch_dialog.reject()
        if window.batch.running:
            window.batch.cancel()
            wait(lambda: not window.batch.running)
        for session in window.sessions.values():
            session.document.setModified(False)
        window.editor.document().setModified(False)
        window.close()
        app.processEvents()


def batch(window, wait, paths):
    assert window.batch.start(paths)
    wait()
    return window.batch.items


def activate(window, wait, session):
    assert window.activate_session(session.id)
    wait()


def test_batch_continues_errors_deduplicates_and_does_not_export(loaded_window, sources, tmp_path):
    window, wait, _ = loaded_window
    invalid = tmp_path / 'invalido.pdf'
    invalid.write_text('arquivo invalido')
    protected = tmp_path / 'senha.pdf'
    with pymupdf.open() as doc:
        doc.new_page()
        doc.save(protected, encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw='dono', user_pw='senha')
    alias = tmp_path / 'atalho.pdf'
    alias.symlink_to(sources[0])
    original = [file_hash(path) for path in sources]
    items = batch(window, wait, [sources[0], alias, invalid, protected, sources[1]])
    assert len(items) == 4
    assert [item.status for item in items] == ['Convertido', 'Falhou', 'Falhou', 'Convertido']
    assert items[1].message and items[2].message
    assert window.result is None
    assert not list(tmp_path.rglob('Importados'))
    assert [file_hash(path) for path in sources] == original
    assert len(window.sessions) == 2
    assert all(item.session.document.isModified() for item in items if item.session)
    assert all(not path.exists() for path in window.workspaces if path not in [item.session.result.workspace for item in items if item.session])


def test_switch_preserves_previous_document_history_and_view(loaded_window, sources, monkeypatch):
    window, wait, _ = loaded_window
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *a: (str(sources[0]), 'PDF'))
    window.open_pdf()
    wait()
    original_result = window.result
    original_text = window.editor.toPlainText()
    document = window.editor.document()
    window.editor.moveCursor(QTextCursor.End)
    window.editor.insertPlainText('\n💡 Revisão do primeiro documento.')
    edited = window.editor.toPlainText()
    window.follow_page.setChecked(False)
    window.request_page(2)
    wait()
    window.set_manual_zoom(125)
    wait()
    window.tabs.setCurrentIndex(1)
    window.refresh_preview()
    window.preview.selection_mode.setChecked(True)
    selected = next(iter(window.preview.targets.values()))
    window.preview.selected_images.add(selected)
    window.preview.selection_changed.emit()
    cursor = window.editor.textCursor()
    cursor.setPosition(20)
    cursor.setPosition(4, QTextCursor.KeepAnchor)
    window.editor.setTextCursor(cursor)
    window.strip_markers_option.setChecked(True)
    window.warnings_toggle.setChecked(True)
    window.set_pdf_visible(False)
    window.save_active_session()
    previous = window.active_session
    items = batch(window, wait, [sources[1]])
    assert window.result is original_result
    assert window.editor.document() is document
    assert window.editor.toPlainText() == edited
    activate(window, wait, items[0].session)
    assert not window.strip_markers_option.isChecked()
    assert window.tabs.currentIndex() == 0
    activate(window, wait, previous)
    assert window.editor.document() is document
    assert window.editor.toPlainText() == edited
    assert window.editor.textCursor().anchor() == 20
    assert window.editor.textCursor().position() == 4
    assert window.displayed_page == 2
    assert window.zoom_mode == 'manual' and window.zoom_percent == 125
    assert window.pdf_panel.isHidden()
    assert not window.follow_page.isChecked()
    assert window.tabs.currentIndex() == 1
    assert window.warnings_toggle.isChecked()
    assert window.strip_markers_option.isChecked()
    assert window.preview.selected_images == {selected}
    assert window.preview.selection_mode.isChecked()
    window.editor.undo()
    assert window.editor.toPlainText() == original_text
    window.editor.redo()
    assert window.editor.toPlainText() == edited
    previous_workspace = items[0].session.result.workspace
    batch(window, wait, [sources[2]])
    assert previous.id in window.sessions
    assert not previous_workspace.exists()
    activate(window, wait, previous)
    assert window.editor.document() is document
    assert window.editor.toPlainText() == edited


def test_switch_during_render_ignores_old_pages(loaded_window, sources):
    window, wait, _ = loaded_window
    items = batch(window, wait, sources[:2])
    activate(window, wait, items[0].session)
    first_page_scroll = window.editor.verticalScrollBar().value()
    window.request_page(2)
    assert window.activate_session(items[1].session.id)
    wait()
    assert window.result is items[1].session.result
    assert window.displayed_page == 1
    assert window.page_view.page_rect[2] == 625
    assert window.active_render is None
    before = len(window.sessions)
    window.batch.handle('token-obsoleto', items[0].id, 'converted', items[0].session.result)
    assert len(window.sessions) == before
    activate(window, wait, items[0].session)
    window.follow_current_page()
    assert window.displayed_page == 2
    assert window.editor.verticalScrollBar().value() > 0
    activate(window, wait, items[1].session)
    assert window.activate_session(items[0].session.id)
    # Uma escolha nova durante o carregamento prevalece sobre a restauração.
    window.request_page(1)
    wait()
    assert window.displayed_page == 1
    assert window.editor.verticalScrollBar().value() == first_page_scroll


def test_batch_export_edits_selection_options_and_repeat_rules(loaded_window, sources, tmp_path):
    window, wait, _ = loaded_window
    items = batch(window, wait, sources[:2])
    first, second = items
    activate(window, wait, first.session)
    window.editor.moveCursor(QTextCursor.End)
    window.editor.insertPlainText('\nNota pessoal editada. 💡')
    window.strip_markers_option.setChecked(True)
    second.included = False
    vault = tmp_path / 'vault'
    vault.mkdir()
    assert window.batch.export_selected(vault)
    wait()
    first_target = Path(first.target)
    final = next(first_target.glob('*.md')).read_text()
    assert 'Nota pessoal editada. 💡' in final and '<!-- Página' not in final
    assert first.export_status == 'Salvo'
    assert window.batch.message == '1 salvo(s), 0 já salvo(s), 0 falha(s).'
    assert second.session.document.isModified()
    assert len(list((vault / 'Importados').iterdir())) == 1
    second.included = True
    assert window.batch.export_selected(vault)
    wait()
    assert first.export_status == 'Já salvo' and second.export_status == 'Salvo'
    assert window.batch.message == '1 salvo(s), 1 já salvo(s), 0 falha(s).'
    assert '<!-- Página' in next(Path(second.target).glob('*.md')).read_text()
    assert len(list((vault / 'Importados').iterdir())) == 2
    # Edição desfeita e opção revertida não criam outra pasta.
    window.editor.insertPlainText(' Temporário')
    window.editor.undo()
    window.strip_markers_option.setChecked(False)
    window.strip_markers_option.setChecked(True)
    assert window.batch.export_selected(vault)
    wait()
    assert all(item.export_status == 'Já salvo' for item in items)
    assert not window.editor.document().isModified()
    assert len(list((vault / 'Importados').iterdir())) == 2
    window.editor.moveCursor(QTextCursor.End)
    window.editor.insertPlainText('\nMais uma revisão.')
    assert window.batch.export_selected(vault)
    wait()
    assert Path(first.target) != first_target
    assert 'Mais uma revisão.' not in next(first_target.glob('*.md')).read_text()
    assert len(list((vault / 'Importados').iterdir())) == 3
    other = tmp_path / 'outro-vault'
    other.mkdir()
    assert window.batch.export_selected(other)
    wait()
    assert len(list((other / 'Importados').iterdir())) == 2
    assert window.batch.export_selected(vault)
    wait()
    assert len(list((vault / 'Importados').iterdir())) == 3
    recorded = first.session.exports[str(vault.resolve())].target
    shutil.rmtree(recorded)
    assert window.batch.export_selected(vault)
    wait()
    assert first.export_status == 'Salvo' and recorded.exists()


def test_export_failure_does_not_block_other_documents(loaded_window, sources, tmp_path):
    window, wait, _ = loaded_window
    items = batch(window, wait, sources)
    sources[1].write_bytes(sources[1].read_bytes() + b'\nmodificacao-sintetica')
    vault = tmp_path / 'vault'
    vault.mkdir()
    assert window.batch.export_selected(vault)
    wait()
    assert [item.export_status for item in items] == ['Salvo', 'Falhou', 'Salvo']
    assert 'mudou' in items[1].message
    assert items[1].session.document.isModified()
    assert len(list((vault / 'Importados').iterdir())) == 2
    assert not list((vault / 'Importados').glob('.pdf-obsidian-*'))


def test_same_name_sources_get_distinct_outputs(loaded_window, sources, tmp_path):
    window, wait, _ = loaded_window
    directory = tmp_path / 'subpasta'
    directory.mkdir()
    another = directory / sources[0].name
    another.write_bytes(sources[1].read_bytes())
    items = batch(window, wait, [sources[0], another])
    vault = tmp_path / 'vault'
    vault.mkdir()
    assert window.batch.export_selected(vault)
    wait()
    assert items[0].target != items[1].target
    assert Path(items[1].target).name.endswith('-2')
    assert all((Path(item.target) / 'original.pdf').read_bytes() == item.source.read_bytes() for item in items)


def test_cancel_conversion_preserves_completed_and_stops_queue(loaded_window, sources):
    window, wait, _ = loaded_window
    def cancel_after_progress():
        if (window.batch.mode == 'convert' and window.batch.active is window.batch.items[1]
                and window.batch.progress[0] > 0):
            window.batch.cancel()
    window.batch.progress_changed.connect(cancel_after_progress)
    assert window.batch.start(sources)
    wait()
    assert window.batch.items[0].status == 'Convertido'
    assert window.batch.items[1].status in ('Convertido', 'Cancelado')
    assert window.batch.items[2].status == 'Não executado'
    assert 'interrompida' in window.batch.message
    assert window.batch.items[0].session is not None
    assert window.batch.items[2].session is None


def test_cancel_export_stops_future_files(loaded_window, sources, tmp_path):
    window, wait, _ = loaded_window
    items = batch(window, wait, sources)
    vault = tmp_path / 'vault'
    vault.mkdir()
    def cancel_export():
        if window.batch.mode == 'export':
            window.batch.cancel()
    window.batch.changed.connect(cancel_export)
    assert window.batch.export_selected(vault)
    wait()
    assert items[0].export_status in ('Salvo', 'Cancelado')
    assert all(item.export_status == 'Não exportado' for item in items[1:])
    assert len(list((vault / 'Importados').iterdir())) <= 1 if (vault / 'Importados').exists() else True


def test_dialog_preparation_review_and_exclusion(loaded_window, sources, monkeypatch, app):
    window, wait, _ = loaded_window
    monkeypatch.setattr(QFileDialog, 'getOpenFileNames', lambda *a: ([str(sources[0]), str(sources[1]), str(sources[0])], 'PDF'))
    window.open_batch()
    dialog = window.batch_dialog
    dialog.add.click()
    assert dialog.tree.topLevelItemCount() == 2
    dialog.start.click()
    wait()
    assert not dialog.preparing
    assert dialog.tree.topLevelItemCount() == 2
    row = dialog.tree.topLevelItem(1)
    row.setCheckState(0, Qt.Unchecked)
    assert not window.batch.items[1].included
    assert window.batch.items[1].session is not None
    dialog.tree.setCurrentItem(dialog.tree.topLevelItem(0))
    dialog.review.click()
    wait()
    assert window.result is window.batch.items[0].session.result
    assert window.batch_dialog is None
    window.show_documents()
    assert window.batch_dialog.tree.topLevelItemCount() == 2
    window.batch_dialog.close()
    app.processEvents()


def test_dialog_progress_and_transitions_preserve_list(loaded_window, sources, tmp_path, monkeypatch, app):
    window, _, _ = loaded_window
    # Entregar os eventos explicitamente torna a sequência independente da
    # velocidade do processo auxiliar; apenas o primeiro PDF é convertido.
    original_commands = window.commands
    monkeypatch.setattr(window, 'commands', Queue())
    paths = [*sources, *(tmp_path / f'pendente-{n}.pdf' for n in range(35))]
    assert window.batch.start(paths)
    window._show_batch_dialog(False)
    dialog = window.batch_dialog
    try:
        tree = dialog.tree
        tree.header().setSectionResizeMode(0, QHeaderView.Interactive)
        tree.setColumnWidth(0, 1600)
        rows = [tree.topLevelItem(i) for i in range(len(paths))]
        tree.setCurrentItem(rows[18])
        tree.setFocus()
        app.processEvents()
        vertical, horizontal = tree.verticalScrollBar(), tree.horizontalScrollBar()
        vertical.setValue(vertical.maximum() // 2)
        horizontal.setValue(horizontal.maximum() // 2)
        scroll = (vertical.value(), horizontal.value())
        assert all(value > 0 for value in scroll)
        assert tree.hasFocus()
        model = tree.model()
        spies = [QSignalSpy(signal) for signal in (
            model.modelReset, model.rowsRemoved, model.rowsInserted, model.dataChanged,
            tree.itemSelectionChanged)]
        refreshes = []
        original_refresh = dialog.refresh
        def refresh():
            refreshes.append(True)
            original_refresh()
        monkeypatch.setattr(dialog, 'refresh', refresh)

        first = window.batch.active
        for current in range(1, 31):
            window.batch.handle(window.batch.token, first.id, 'progress', current, 40)
            app.processEvents()
            assert dialog.progress.value() == current
            assert dialog.progress.maximum() == 40
            assert tree.currentItem() is rows[18]
            assert tree.hasFocus()
            assert (vertical.value(), horizontal.value()) == scroll
        assert not refreshes
        assert all(spy.count() == 0 for spy in spies)
        # Eventos de progresso obsoletos também não alteram a tela.
        window.batch.handle('obsoleto', first.id, 'progress', 39, 40)
        assert dialog.progress.value() == 30

        result = convert(sources[0], window.batch.work)
        window.batch.handle(window.batch.token, first.id, 'converted', result)
        assert len(refreshes) == 1
        assert rows[0].text(1).startswith('Convertido')
        assert rows[0].text(2) == str(len(result.warnings))
        assert rows[1].text(1) == 'Convertendo'
        assert not rows[0].flags() & Qt.ItemIsUserCheckable
        window.batch.handle(window.batch.token, window.batch.active.id, 'error', 'Falha sintética')
        assert len(refreshes) == 2
        assert rows[1].text(1) == 'Falhou'
        assert 'Falha sintética' in rows[1].toolTip(1)
        app.processEvents()
        assert tree.currentItem() is rows[18]
        assert tree.hasFocus()
        assert (vertical.value(), horizontal.value()) == scroll

        window.batch.cancel()
        window.batch.handle(window.batch.token, window.batch.active.id, 'cancelled')
        assert rows[2].text(1) == 'Cancelado'
        assert rows[3].text(1) == 'Não executado'
        assert rows[0].flags() & Qt.ItemIsUserCheckable
        assert dialog.close_button.isEnabled()
        assert [tree.topLevelItem(i) for i in range(len(paths))] == rows
        assert all(spy.count() == 0 for spy in spies[:3])
    finally:
        if window.batch.running:
            window.batch.cancel()
            window.batch.handle(window.batch.token, window.batch.active.id, 'cancelled')
        monkeypatch.setattr(window, 'commands', original_commands)


def test_dialog_updates_export_and_checkboxes_without_replacing_rows(loaded_window, sources, tmp_path, monkeypatch, app):
    window, wait, _ = loaded_window
    items = batch(window, wait, sources[:2])
    window.show_documents()
    dialog = window.batch_dialog
    rows = [dialog.tree.topLevelItem(i) for i in range(2)]
    dialog.tree.setCurrentItem(rows[1])
    item_changes = QSignalSpy(dialog.tree.itemChanged)
    model_changes = QSignalSpy(dialog.tree.model().dataChanged)
    dialog.refresh()
    assert model_changes.count() == 0

    items[0].included = False
    dialog.refresh()
    assert rows[0].checkState(0) == Qt.Unchecked
    assert item_changes.count() == 0
    rows[0].setCheckState(0, Qt.Checked)
    app.processEvents()
    assert items[0].included
    assert dialog.tree.topLevelItem(0) is rows[0]
    assert dialog.tree.currentItem() is rows[1]

    vault = tmp_path / 'vault'
    vault.mkdir()
    monkeypatch.setattr(QFileDialog, 'getExistingDirectory', lambda *a: str(vault))
    for expected in ('Salvo', 'Já salvo'):
        dialog.export.click()
        wait()
        assert [dialog.tree.topLevelItem(i) for i in range(2)] == rows
        assert dialog.tree.currentItem() is rows[1]
        assert all(expected in row.text(1) for row in rows)
        assert all(item.export_status == expected for item in items)
        assert all(row.flags() & Qt.ItemIsUserCheckable for row in rows)


def test_dialog_preparation_preserves_remaining_rows_and_restores_signal_blocking(loaded_window, sources, monkeypatch):
    window, _, _ = loaded_window
    window.open_batch()
    dialog = window.batch_dialog
    dialog.paths = [str(path) for path in sources]
    dialog.refresh()
    first, second, third = [dialog.tree.topLevelItem(i) for i in range(3)]
    dialog.tree.setCurrentItem(second)
    dialog.remove_current()
    assert [dialog.tree.topLevelItem(i) for i in range(2)] == [first, third]
    assert len(dialog.paths) == 2
    original_refresh_rows = dialog.refresh_rows
    def fail():
        raise RuntimeError('Falha sintética na atualização')
    monkeypatch.setattr(dialog, 'refresh_rows', fail)
    for blocked in (False, True):
        dialog.tree.blockSignals(blocked)
        with pytest.raises(RuntimeError, match='Falha sintética'):
            dialog.refresh()
        assert dialog.tree.signalsBlocked() == blocked
        assert not dialog.refreshing
    dialog.tree.blockSignals(False)
    monkeypatch.setattr(dialog, 'refresh_rows', original_refresh_rows)
    dialog.refresh()
    assert dialog.tree.topLevelItemCount() == 2


def test_aggregate_discard_includes_unchecked_documents(loaded_window, sources, monkeypatch):
    window, wait, _ = loaded_window
    items = batch(window, wait, sources[:2])
    items[1].included = False
    activate(window, wait, items[0].session)
    old_workspaces = [item.session.result.workspace for item in items]
    prompts = []
    monkeypatch.setattr(QMessageBox, 'question', lambda *a: prompts.append(a[2]) or QMessageBox.No)
    window.close()
    assert window.worker.is_alive() and len(prompts) == 1
    assert '2 documento' in prompts[0]
    assert not window.batch.start([sources[2]])
    assert window.batch.items == items
    monkeypatch.setattr(QMessageBox, 'question', lambda *a: QMessageBox.Yes)
    assert window.batch.start([sources[2]])
    wait()
    assert all(not path.exists() for path in old_workspaces)
    assert len(window.sessions) == 1


def test_signature_ignores_undone_removal_audit(sources, tmp_path):
    from pdf_obsidian.cleanup import build_manual_cleanup_plan
    result = convert(sources[0], tmp_path / 'work')
    baseline = export_signature(result)
    selected = result.assets[0]
    plan = build_manual_cleanup_plan(result, result.markdown, [(selected.path, 0)])
    assert export_signature(result, cleanup_removals=plan.removals) == baseline
    assert export_signature(result, result.markdown + '\nAlterado') != baseline
    assert export_signature(result, strip_page_markers=True) != baseline


def test_worker_cancels_during_conversion(sources, tmp_path):
    commands, events = Queue(), Queue()
    cancel = threading.Event()
    class EventSink:
        def put(self, event):
            events.put(event)
            if event[:4] == ('batch', 'token', 'item', 'progress'):
                cancel.set()
    commands.put(('batch_convert', 'token', 'item', str(sources[0]), str(tmp_path / 'work')))
    commands.put(('stop',))
    run(commands, EventSink(), cancel)
    delivered = list(events.queue)
    assert delivered[-1] == ('batch', 'token', 'item', 'cancelled')
    assert not any(event[3] == 'converted' for event in delivered)


def test_worker_finishes_export_when_cancel_arrives_during_write(sources, tmp_path, monkeypatch):
    import pdf_obsidian.exporter as exporter
    result = convert(sources[0], tmp_path / 'work')
    vault = tmp_path / 'vault'
    vault.mkdir()
    commands, events = Queue(), Queue()
    cancel = threading.Event()
    actual = exporter.export_document
    def cancel_while_writing(*args, **kwargs):
        cancel.set()
        return actual(*args, **kwargs)
    monkeypatch.setattr(exporter, 'export_document', cancel_while_writing)
    commands.put(('batch_export', 'token', 'item', str(vault), result, result.markdown, False, ()))
    commands.put(('stop',))
    run(commands, events, cancel)
    message = events.get_nowait()
    assert message[:4] == ('batch', 'token', 'item', 'exported')
    assert (Path(message[-1]) / 'original.pdf').read_bytes() == sources[0].read_bytes()
    assert not list((vault / 'Importados').glob('.pdf-obsidian-*'))


def test_switch_isolates_crops_removals_and_reading_position(loaded_window, sources, tmp_path, app):
    from pdf_obsidian.comparison import reading_position
    import json
    window, wait, _ = loaded_window
    first, second = batch(window, wait, sources[:2])
    activate(window, wait, first.session)
    window.follow_page.setChecked(False)
    original = window.editor.toPlainText()
    window.editor.moveCursor(QTextCursor.End)
    window.crop((60, 270, 240, 350))
    wait()
    crop_text = window.editor.toPlainText()
    assert 'Recorte da página' in crop_text
    window.refresh_preview()
    selected = next(iter(window.preview.targets.values()))
    window.preview.selected_images = {selected}
    window.remove_preview_images()
    edited = window.editor.toPlainText()
    assert edited != crop_text
    assert len(window.cleanup_removals) == 1
    window.tabs.setCurrentIndex(1)
    app.processEvents()
    window.preview.verticalScrollBar().setValue(250)
    window.editor.verticalScrollBar().setValue(9)
    window.set_manual_zoom(150)
    wait()
    window.pdf_scroll.verticalScrollBar().setValue(380)
    window.pdf_scroll.horizontalScrollBar().setValue(100)
    preview_position = reading_position(window.preview)
    editor_scroll = window.editor.verticalScrollBar().value()
    pdf_scroll = window.pdf_scroll.verticalScrollBar().value()
    activate(window, wait, second.session)
    assert not window.cleanup_removals
    assert 'Recorte da página' not in window.editor.toPlainText()
    assert len(window.result.assets) == 2
    activate(window, wait, first.session)
    assert window.editor.toPlainText() == edited
    assert reading_position(window.preview) == preview_position
    assert window.editor.verticalScrollBar().value() == editor_scroll
    assert abs(window.pdf_scroll.verticalScrollBar().value() - pdf_scroll) <= 1
    assert len(window.cleanup_removals) == 1
    window.editor.undo()
    assert window.editor.toPlainText() == crop_text
    window.editor.undo()
    assert window.editor.toPlainText() == original
    window.editor.redo()
    window.editor.redo()
    vault = tmp_path / 'vault'
    vault.mkdir()
    assert window.batch.export_selected(vault)
    wait()
    report = json.loads((Path(first.target) / 'conversao.json').read_text())
    assert report['cleanup']['image_removals']
    assert any(asset['origin'] == 'manual' for asset in report['assets'])
    second_report = json.loads((Path(second.target) / 'conversao.json').read_text())
    assert not second_report['cleanup']['image_removals']
    assert all(asset['origin'] != 'manual' for asset in second_report['assets'])


def test_individual_export_updates_batch_record(loaded_window, sources, tmp_path, monkeypatch):
    window, wait, _ = loaded_window
    item = batch(window, wait, sources[:1])[0]
    activate(window, wait, item.session)
    vault = tmp_path / 'vault'
    vault.mkdir()
    monkeypatch.setattr(QFileDialog, 'getExistingDirectory', lambda *a: str(vault))
    window.export()
    assert not item.session.document.isModified()
    assert window.batch.export_selected(vault)
    wait()
    assert item.export_status == 'Já salvo'
    assert len(list((vault / 'Importados').iterdir())) == 1


def test_missing_asset_and_write_error_keep_documents_for_retry(loaded_window, sources, tmp_path):
    window, wait, _ = loaded_window
    first, second = batch(window, wait, sources[:2])
    asset = first.session.result.workspace / first.session.result.assets[0].path
    content = asset.read_bytes()
    asset.unlink()
    vault = tmp_path / 'vault'
    vault.mkdir()
    # Arquivo no lugar de Importados força uma falha real de gravação.
    blocked = vault / 'Importados'
    blocked.write_text('obstaculo sintetico')
    assert window.batch.export_selected(vault)
    wait()
    assert first.export_status == second.export_status == 'Falhou'
    assert 'Anexos' in first.message
    assert all(item.session.document.isModified() for item in (first, second))
    asset.write_bytes(content)
    blocked.unlink()
    assert window.batch.export_selected(vault)
    wait()
    assert all(item.export_status == 'Salvo' for item in (first, second))


def test_closing_running_dialog_cancels_and_preserves_completed(loaded_window, sources):
    window, wait, _ = loaded_window
    assert window.batch.start(sources)
    window._show_batch_dialog(False)
    dialog = window.batch_dialog
    dialog.close()
    assert window.batch.cancel_requested
    assert window.batch_dialog is dialog
    # Cancelamento repetido deve ser idempotente, inclusive por sinais.
    window.batch.cancel()
    wait()
    assert not window.batch.running
    assert not any(item.status == 'Pendente' for item in window.batch.items)
    dialog.close()
    assert window.batch_dialog is None


def test_worker_death_stops_batch_and_keeps_finished_documents(loaded_window, sources):
    window, wait, errors = loaded_window
    first = batch(window, wait, sources[:1])[0]
    activate(window, wait, first.session)
    assert window.batch.export_selected(sources[0].parent)
    window.worker.terminate()
    window.worker.join(timeout=2)
    window.poll()
    assert not window.batch.running
    assert first.session.id in window.sessions
    assert first.session.document.toPlainText()
    assert first.export_status == 'Falhou'
    assert not window.export_button.isEnabled()
    assert not window.batch_button.isEnabled()
    assert len(errors) == 1 and 'inesperadamente' in errors.pop()
