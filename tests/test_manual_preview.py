import json
import time

import pytest
from PySide6.QtCore import QPoint, QRectF, Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QFileDialog, QMessageBox

from pdf_obsidian.gui import Window


@pytest.fixture
def manual_window(app, manual_source, tmp_path, monkeypatch):
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args: (str(manual_source), "PDF"))
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QMessageBox, "information", lambda *args: QMessageBox.StandardButton.Ok)
    errors = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *args: errors.append(args[-1]))
    vault = tmp_path / "vault"
    vault.mkdir()
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *args: str(vault))
    window = Window()
    window.show()

    def settle():
        deadline = time.monotonic() + 15
        idle = None
        while True:
            app.processEvents()
            if time.monotonic() > deadline:
                pytest.fail("A prévia não terminou de atualizar.")
            if window.busy or window.preview_dirty:
                idle = None
            elif idle is None:
                idle = time.monotonic()
            elif time.monotonic() - idle >= .03:
                return
            QTest.qWait(5)
    try:
        window.open_pdf()
        settle()
        window.tabs.setCurrentWidget(window.preview)
        app.processEvents()
        assert not errors
        yield window, vault, settle
        assert not errors
    finally:
        window.editor.document().setModified(False)
        window.close()
        app.processEvents()


def click_image(window, key, app):
    preview = window.preview
    position = next(position for position, target in preview.targets.items() if target == key)
    cursor = QTextCursor(preview.document())
    cursor.setPosition(position)
    preview.setTextCursor(cursor)
    preview.ensureCursorVisible()
    app.processEvents()
    rect = preview.image_rect(position)
    visible = rect.intersected(QRectF(preview.viewport().rect()))
    assert not visible.isEmpty()
    QTest.mouseClick(preview.viewport(), Qt.MouseButton.LeftButton, pos=visible.center().toPoint())
    app.processEvents()


def test_select_images_directly_without_automatic_suggestions(manual_window, app):
    window, vault, settle = manual_window
    preview = window.preview
    page_images = [asset for asset in window.result.assets if asset.page == 1]
    keys = [(asset.path, 0) for asset in page_images]
    assert len(preview.targets) == len(window.result.assets) == 4
    assert not preview.selection_mode.isChecked()
    click_image(window, keys[0], app)
    assert not preview.selected_images
    preview.selection_mode.setChecked(True)
    click_image(window, keys[0], app)
    click_image(window, keys[1], app)
    assert preview.selected_images == set(keys)
    assert preview.selection_count.text() == "2 selecionadas"
    assert preview.remove_button.isEnabled()
    original = window.editor.toPlainText()
    preview.remove_button.click()
    settle()
    assert all(asset.generated_markdown not in window.editor.toPlainText() for asset in page_images)
    assert all(asset.generated_markdown in window.editor.toPlainText() for asset in window.result.assets if asset.page == 2)
    assert "Legenda que deve permanecer intacta." in window.editor.toPlainText()
    assert not preview.selected_images
    assert preview.undo_button.isEnabled()
    assert window.tabs.currentWidget() is preview
    assert all((window.result.workspace / asset.path).exists() for asset in page_images)
    window.export()
    exported = next((vault / "Importados").iterdir())
    assert all(not (exported / asset.path).exists() for asset in page_images)
    report = json.loads((exported / "conversao.json").read_text())
    assert len(report["cleanup"]["image_removals"]) == 2
    assert all(action["group"].startswith("manual:") for action in report["cleanup"]["image_removals"])
    preview.undo_button.click()
    settle()
    assert window.editor.toPlainText() == original
    assert len(preview.targets) == 4
    assert preview.redo_button.isEnabled()
    preview.redo_button.click()
    settle()
    assert all(asset.generated_markdown not in window.editor.toPlainText() for asset in page_images)


def test_selection_toggle_clear_and_text_edits_invalidate_targets(manual_window, app):
    window, _, settle = manual_window
    preview = window.preview
    key = (window.result.assets[0].path, 0)
    preview.selection_mode.setChecked(True)
    click_image(window, key, app)
    assert preview.selected_images == {key}
    click_image(window, key, app)
    assert not preview.selected_images
    click_image(window, key, app)
    preview.clear_button.click()
    assert not preview.selected_images
    click_image(window, key, app)
    cursor = window.editor.textCursor()
    cursor.setPosition(0)
    cursor.insertText("💡 Anotação nova.\n\n")
    assert not preview.selected_images
    assert not preview.remove_button.isEnabled()
    settle()
    assert preview.selection_mode.isChecked()
    click_image(window, key, app)
    preview.remove_button.click()
    settle()
    assert window.editor.toPlainText().startswith("💡 Anotação nova.")
    preview.setFocus()
    QTest.keyClick(preview, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
    settle()
    assert window.result.assets[0].generated_markdown in window.editor.toPlainText()


def test_only_clicked_duplicate_is_removed_and_mode_off_keeps_document(manual_window, app):
    window, _, settle = manual_window
    asset = window.result.assets[0]
    original = window.editor.toPlainText().replace(asset.generated_markdown,
                                                  asset.generated_markdown + "\n\n" + asset.generated_markdown)
    window.editor.setPlainText(original)
    settle()
    preview = window.preview
    preview.selection_mode.setChecked(True)
    click_image(window, (asset.path, 1), app)
    preview.remove_button.click()
    settle()
    assert window.editor.toPlainText().count(asset.generated_markdown) == 1
    preview.undo_button.click()
    settle()
    click_image(window, (asset.path, 0), app)
    preview.selection_mode.setChecked(False)
    assert not preview.selected_images
    assert window.editor.toPlainText() == original
    assert not preview.remove_button.isEnabled()


def test_whitespace_does_not_select_nearest_image(manual_window, app):
    window, _, _ = manual_window
    preview = window.preview
    preview.selection_mode.setChecked(True)
    preview.verticalScrollBar().setValue(0)
    QTest.mouseClick(preview.viewport(), Qt.MouseButton.LeftButton, pos=QPoint(preview.viewport().width() - 5, 5))
    assert not preview.selected_images


def test_selection_survives_page_navigation_and_removes_across_pages(manual_window, app):
    window, _, settle = manual_window
    preview = window.preview
    first = window.result.assets[0]
    last = window.result.assets[-1]
    preview.selection_mode.setChecked(True)
    click_image(window, (first.path, 0), app)
    window.request_page(2)
    settle()
    assert preview.selected_images == {(first.path, 0)}
    click_image(window, (last.path, 0), app)
    assert len(preview.selected_images) == 2
    original = window.editor.toPlainText()
    preview.remove_button.click()
    settle()
    assert first.generated_markdown not in window.editor.toPlainText()
    assert last.generated_markdown not in window.editor.toPlainText()
    preview.undo_button.click()
    settle()
    assert window.editor.toPlainText() == original
