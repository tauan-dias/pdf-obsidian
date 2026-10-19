import time

import pymupdf
import pytest
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QTextCursor, QPixmap
from PySide6.QtTest import QTest, QSignalSpy
from PySide6.QtWidgets import QFileDialog, QMessageBox

from pdf_obsidian.comparison import reading_position, unique_markers
from pdf_obsidian.gui import Window


@pytest.fixture
def wait(app):
    def until(predicate):
        deadline = time.monotonic() + 15
        while not predicate():
            app.processEvents()
            if time.monotonic() > deadline:
                pytest.fail("A navegação não terminou a tempo.")
            QTest.qWait(5)
        app.processEvents()
    return until


@pytest.fixture
def loaded(app, wait, tmp_path, monkeypatch):
    source = tmp_path / "comparacao.pdf"
    with pymupdf.open() as doc:
        for number in range(1, 4):
            page = doc.new_page(width=842 if number == 2 else 595,
                                height=595 if number == 2 else 842)
            page.insert_text((50, 100), f"Capitulo {number}", fontsize=20)
            for line in range(22 if number == 2 else 36):
                page.insert_text((50, 140 + line * 16),
                                 f"Pagina {number}, paragrafo {line}: texto para comparar.", fontsize=11)
        doc.save(source)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args: (str(source), "PDF"))
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    errors = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *args: errors.append(args[-1]))
    window = Window()
    window.show()
    window.activateWindow()
    app.processEvents()
    try:
        window.open_pdf()
        wait(lambda: window.result is not None and not window.busy)
        assert not errors
        yield window, errors, source
    finally:
        window.editor.document().setModified(False)
        window.close()
        app.processEvents()


def test_page_controls_field_and_shortcuts(loaded, wait, app):
    window, errors, _ = loaded
    panel = window.pdf_panel
    window.editor.document().setModified(False)
    assert window.zoom_mode == "width"
    assert "de 3" in panel.page_number.text()
    assert not panel.previous.isEnabled()
    panel.next.click()
    wait(lambda: not window.busy)
    assert window.displayed_page == 2
    assert window.pdf_scroll.verticalScrollBar().value() == 0
    assert panel.previous.isEnabled()
    panel.page_number.setFocus()
    panel.page_number.selectAll()
    QTest.keyClicks(panel.page_number, "3")
    assert window.requested_page == 2
    QTest.keyClick(panel.page_number, Qt.Key.Key_Return)
    wait(lambda: not window.busy)
    assert window.displayed_page == 3
    assert not panel.next.isEnabled()
    text = window.editor.toPlainText()
    window.editor.setFocus()
    app.processEvents()
    QTest.keyClick(window.editor, Qt.Key.Key_Left, Qt.KeyboardModifier.AltModifier)
    wait(lambda: not window.busy)
    assert window.displayed_page == 2
    assert window.editor.toPlainText() == text
    QTest.keyClick(window.editor, Qt.Key.Key_Right, Qt.KeyboardModifier.AltModifier)
    wait(lambda: not window.busy)
    assert window.displayed_page == 3
    assert not window.editor.document().isModified()
    assert not errors


def test_zoom_fit_resize_limits_and_focus(loaded, wait, app):
    window, errors, _ = loaded
    panel = window.pdf_panel
    window.set_manual_zoom(100)
    wait(lambda: not window.busy)
    assert window.page_view.width() == round(595 * 100 / 72)
    vertical = window.pdf_scroll.verticalScrollBar()
    vertical.setValue(250)
    center = (vertical.value() + window.pdf_scroll.viewport().height() / 2) / window.page_view.height()
    window.set_manual_zoom(200)
    wait(lambda: not window.busy)
    new_center = (vertical.value() + window.pdf_scroll.viewport().height() / 2) / window.page_view.height()
    assert abs(center - new_center) < .01
    assert abs(window.page_view.original.width() - 595 * 200 / 72) <= 1
    panel.fit_page.click()
    wait(lambda: not window.busy)
    assert window.page_view.width() <= window.pdf_scroll.viewport().width()
    assert window.page_view.height() <= window.pdf_scroll.viewport().height()
    assert vertical.maximum() == 0
    window.resize(1500, 1000)
    app.processEvents()
    wait(lambda: not window.busy)
    assert window.zoom_mode == "page"
    assert window.page_view.height() <= window.pdf_scroll.viewport().height()
    panel.fit_width.click()
    wait(lambda: not window.busy)
    assert abs(window.page_view.width() - window.pdf_scroll.viewport().width()) <= 3
    window.request_page(2)
    wait(lambda: not window.busy)
    assert window.zoom_mode == "width"
    assert abs(window.page_view.width() - window.pdf_scroll.viewport().width()) <= 3
    window.set_manual_zoom(10)
    wait(lambda: not window.busy)
    assert window.zoom_percent == 25
    assert not panel.zoom_out.isEnabled()
    panel.zoom.setFocus()
    panel.zoom.selectAll()
    QTest.keyClicks(panel.zoom, "400")
    QTest.keyClick(panel.zoom, Qt.Key.Key_Return)
    wait(lambda: not window.busy)
    assert window.zoom_percent == 300
    assert not panel.zoom_in.isEnabled()
    window.page_view.setFocus()
    app.processEvents()
    QTest.keyClick(window.page_view, Qt.Key.Key_Minus, Qt.KeyboardModifier.ControlModifier)
    wait(lambda: not window.busy)
    assert window.zoom_percent == 275
    QTest.keyClick(window.page_view, Qt.Key.Key_0, Qt.KeyboardModifier.ControlModifier)
    wait(lambda: not window.busy)
    assert window.zoom_mode == "width"
    assert not errors


def test_rapid_navigation_keeps_only_latest_request(loaded, wait, monkeypatch):
    window, errors, _ = loaded
    shown = []
    show = window.page_view.show_page
    def record(*args):
        shown.append(window.displayed_page)
        return show(*args)
    monkeypatch.setattr(window.page_view, "show_page", record)
    window.request_page(2)
    window.request_page(3)
    window.request_page(1)
    assert window.active_render[2] == 2
    assert window.pending_render[2] == 1
    assert not window.page_view.selection_enabled
    assert not window.editor.isReadOnly()
    assert window.pdf_panel.next.isEnabled()
    wait(lambda: not window.busy)
    assert window.displayed_page == window.requested_page == 1
    assert shown == [1]
    assert window.active_render is None and window.pending_render is None
    assert not list(window.root.glob("page-*.png"))
    shown.clear()
    for percent in (100, 125, 150):
        window.set_manual_zoom(percent)
    assert window.active_render is None  # O temporizador agrupa as três intenções.
    assert window.pending_render[3] == 150
    wait(lambda: not window.busy)
    assert shown == [1]
    assert abs(window.page_view.original.width() - 595 * 150 / 72) <= 1
    assert not errors


def test_render_failure_retains_page_and_recovers(loaded, wait):
    window, errors, source = loaded
    saved = source.with_suffix(".backup")
    source.rename(saved)
    original = window.page_view.original.cacheKey()
    window.request_page(2)
    window.request_page(3)
    wait(lambda: not window.busy)
    assert len(errors) == 1  # O erro do pedido obsoleto não abre uma mensagem.
    assert window.displayed_page == window.requested_page == window.page_number.value() == 1
    assert window.page_view.original.cacheKey() == original
    assert window.page_view.isEnabled()
    saved.rename(source)
    window.pdf_panel.next.click()
    wait(lambda: not window.busy)
    assert window.displayed_page == 2


def test_follow_page_preserves_edits_cursor_selection_and_undo(loaded, wait, app):
    window, errors, _ = loaded
    editor = window.editor
    before = editor.toPlainText()
    cursor = editor.textCursor()
    cursor.setPosition(0)
    cursor.insertText("Nota pessoal.\n\n")
    cursor.setPosition(5)
    cursor.setPosition(10, QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)
    edited = editor.toPlainText()
    window.request_page(2)
    wait(lambda: not window.busy)
    assert editor.toPlainText() == edited
    assert editor.textCursor().anchor() == 5
    assert editor.textCursor().position() == 10
    assert editor.document().isModified()
    marker = unique_markers(edited)[2]
    block = editor.document().findBlock(marker.start())
    assert abs(editor.firstVisibleBlock().blockNumber() - block.blockNumber()) <= 2
    window.tabs.setCurrentWidget(window.preview)
    app.processEvents()
    assert window.preview.verticalScrollBar().value() > 0
    first_visible = window.preview.cursorForPosition(QPoint(2, 2)).block().text()
    assert first_visible == "\u200b" or "Capitulo 2" in first_visible
    window.follow_page.setChecked(False)
    editor.verticalScrollBar().setValue(0)
    window.preview.verticalScrollBar().setValue(0)
    window.request_page(3)
    wait(lambda: not window.busy)
    assert editor.verticalScrollBar().value() == 0
    assert window.preview.verticalScrollBar().value() == 0
    assert editor.toPlainText() == edited
    editor.undo()
    assert editor.toPlainText() == before
    assert not errors


@pytest.mark.parametrize("duplicate", [False, True])
def test_missing_or_duplicate_marker_does_not_guess(loaded, wait, duplicate):
    window, errors, _ = loaded
    text = window.editor.toPlainText()
    marker = "<!-- Página 2 -->"
    text = text.replace(marker, marker + "\n\n" + marker if duplicate else "")
    window.editor.setPlainText(text)
    window.refresh_preview()
    window.editor.verticalScrollBar().setValue(0)
    window.request_page(2)
    wait(lambda: not window.busy)
    assert window.displayed_page == 2
    assert "ausente ou duplicado" in window.statusBar().currentMessage()
    assert window.editor.verticalScrollBar().value() == 0
    assert window.editor.toPlainText() == text
    assert not errors


@pytest.mark.parametrize("at_anchor", [False, True])
def test_preview_retains_reading_position_after_edit(loaded, wait, app, at_anchor):
    window, errors, _ = loaded
    window.follow_page.setChecked(False)
    window.tabs.setCurrentWidget(window.preview)
    window.refresh_preview()
    app.processEvents()
    if at_anchor:
        window.preview.scrollToAnchor("pdf-page-2")
    else:
        window.preview.verticalScrollBar().setValue(650)
    before = reading_position(window.preview)
    cursor = window.editor.textCursor()
    cursor.setPosition(0)
    cursor.insertText("Paragrafo novo acima da leitura.\n\n")
    window.refresh_preview()
    app.processEvents()
    after = reading_position(window.preview)
    assert after[0] == before[0]
    assert abs(after[3] - before[3]) <= 2
    assert not errors


def test_crops_use_pdf_coordinates_at_different_zooms(loaded, wait):
    window, errors, _ = loaded
    for percent in (50, 200):
        window.set_manual_zoom(percent)
        wait(lambda: not window.busy)
        view = window.page_view
        width, height = view.width(), view.height()
        selection = QRect(round(30 / 595 * width), round(30 / 842 * height),
                          round(120 / 595 * width), round(70 / 842 * height))
        bbox = view.selection_bbox(selection)
        assert bbox == pytest.approx((30, 30, 150, 100), abs=1)
        assert view.selection_bbox(QRect(-100, -100, 20, 20)) is None
        spy = QSignalSpy(view.selected)
        QTest.mousePress(view, Qt.MouseButton.LeftButton, pos=selection.topLeft())
        QTest.mouseMove(view, selection.bottomRight())
        QTest.mouseRelease(view, Qt.MouseButton.LeftButton, pos=selection.bottomRight())
        wait(lambda: not window.busy)
        assert spy.count() == 1
        assert spy.at(0)[0] == pytest.approx((30, 30, 150, 100), abs=1)
    crops = list((window.result.workspace / "assets").glob("*recorte*.png"))
    assert len(crops) == 2
    for crop in crops:
        image = QPixmap(str(crop))
        assert abs(image.width() - 120 * 150 / 72) <= 3
        assert abs(image.height() - 70 * 150 / 72) <= 3
    assert not errors


def test_document_layout_restore_and_warning(loaded, wait, app):
    window, errors, _ = loaded
    window.resize(1300, 850)
    app.processEvents()
    window.set_manual_zoom(125)
    wait(lambda: not window.busy)
    window.editor.moveCursor(QTextCursor.End)
    window.editor.insertPlainText('\nNota de revisão')
    window.editor.selectAll()
    cursor = window.editor.textCursor()
    original = window.editor.toPlainText()
    sizes = window.splitter.sizes()
    page, zoom = window.displayed_page, window.zoom_percent
    window.pdf_toggle.click()
    app.processEvents()
    assert window.pdf_panel.isHidden()
    assert window.pdf_toggle.text() == 'Mostrar PDF'
    window.pdf_toggle.click()
    app.processEvents()
    assert window.splitter.sizes() == sizes
    assert (window.displayed_page, window.zoom_percent) == (page, zoom)
    assert window.editor.toPlainText() == original
    assert window.editor.textCursor().anchor() == cursor.anchor()
    assert window.editor.textCursor().position() == cursor.position()
    assert not window.modified_label.isHidden()
    window.editor.undo()
    window.editor.redo()
    assert window.editor.toPlainText() == original
    window.set_pdf_visible(False)
    from PySide6.QtWidgets import QListWidgetItem
    item = QListWidgetItem('Página 2: revisar')
    item.setData(Qt.UserRole, 2)
    window.warning_clicked(item)
    wait(lambda: not window.busy)
    assert not window.pdf_panel.isHidden()
    assert window.displayed_page == 2
    assert not errors


def test_named_formatting_menus(loaded, app):
    window, _, _ = loaded
    window.editor.setPlainText('Texto de exemplo')
    window.editor.selectAll()
    menu = window.editor_tools.menus['Listas'].menu()
    menu.actions()[0].trigger()
    assert window.editor.toPlainText() == '- Texto de exemplo'
    assert window.editor.hasFocus()
    window.editor.undo()
    assert window.editor.toPlainText() == 'Texto de exemplo'
    window.editor_tools.menus['Alinhar'].menu().actions()[1].trigger()
    assert 'text-align: center' in window.editor.toPlainText()
    window.editor.undo()
    assert window.editor.toPlainText() == 'Texto de exemplo'
