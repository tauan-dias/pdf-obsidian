import json

import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog, QFileDialog, QMessageBox, QPlainTextEdit, QVBoxLayout, QWidget

from pdf_obsidian.comparison import preview_document, unique_markers
from pdf_obsidian.converter import convert
from pdf_obsidian.editor_tools import EditorTools, LinkDialog
from pdf_obsidian.gui import Window
from pdf_obsidian.markdown import utf16_position


@pytest.fixture
def editor_ui(app):
    panel = QWidget()
    layout = QVBoxLayout(panel)
    editor = QPlainTextEdit()
    messages = []
    tools = EditorTools(editor, messages.append)
    layout.addWidget(tools)
    layout.addWidget(editor)
    panel.resize(650, 450)
    panel.show()
    panel.activateWindow()
    editor.setFocus()
    app.processEvents()
    yield editor, tools, messages
    panel.close()
    app.processEvents()


def select(editor, start, end=None, reverse=False):
    end = start if end is None else end
    text = editor.toPlainText()
    a, b = utf16_position(text, start), utf16_position(text, end)
    if reverse:
        a, b = b, a
    cursor = editor.textCursor()
    cursor.setPosition(a)
    cursor.setPosition(b, QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)


def test_buttons_unicode_reverse_selection_and_atomic_undo(editor_ui, app):
    editor, tools, messages = editor_ui
    original = "💡 Ação e revisão"
    editor.setPlainText(original)
    select(editor, 2, 6, reverse=True)
    QTest.mouseClick(tools.buttons["bold"], Qt.MouseButton.LeftButton)
    assert editor.toPlainText() == "💡 **Ação** e revisão"
    assert editor.textCursor().selectedText() == "Ação"
    assert editor.textCursor().anchor() > editor.textCursor().position()
    assert editor.hasFocus()
    editor.undo()
    assert editor.toPlainText() == original
    editor.redo()
    assert editor.toPlainText() == "💡 **Ação** e revisão"
    assert messages[-1] == "Formatação aplicada."


@pytest.mark.parametrize("keys,expected", [(Qt.Key.Key_B, "**Texto**"), (Qt.Key.Key_I, "*Texto*")])
def test_shortcuts_with_editor_focus(editor_ui, app, keys, expected):
    editor, _, _ = editor_ui
    editor.setPlainText("Texto")
    editor.selectAll()
    QTest.keyClick(editor, keys, Qt.KeyboardModifier.ControlModifier)
    assert editor.toPlainText() == expected


def test_shortcuts_do_not_apply_outside_editor_or_when_disabled(editor_ui, app):
    editor, tools, _ = editor_ui
    editor.setPlainText("Texto")
    editor.selectAll()
    tools.heading.setFocus()
    QTest.keyClick(tools.heading, Qt.Key.Key_B, Qt.KeyboardModifier.ControlModifier)
    assert editor.toPlainText() == "Texto"
    tools.setEnabled(False)
    editor.setFocus()
    QTest.keyClick(editor, Qt.Key.Key_B, Qt.KeyboardModifier.ControlModifier)
    assert editor.toPlainText() == "Texto"


def test_empty_inline_insertion_and_style_menu(editor_ui):
    editor, tools, _ = editor_ui
    editor.setPlainText("Texto")
    select(editor, 2)
    tools.buttons["italic"].click()
    assert editor.toPlainText() == "Te**xto"
    assert editor.textCursor().position() == 3
    editor.undo()
    tools.heading.setCurrentIndex(3)  # Título 2
    tools.heading.activated.emit(3)
    assert editor.toPlainText() == "## Texto"
    assert tools.heading.currentIndex() == 0


def test_alignment_preview_and_formatting_inside_generated_html(editor_ui, app, tmp_path):
    editor, tools, _ = editor_ui
    source = "<!-- Página 1 -->\n\nTítulo\n\nTexto **forte**."
    editor.setPlainText(source)
    select(editor, source.index("Título"))
    tools.buttons["align:center"].click()
    text = editor.toPlainText()
    assert '<p style="text-align: center;">Título</p>' in text
    assert editor.textCursor().position() == utf16_position(text, text.index("Título"))
    select(editor, text.index("Título"), text.index("Título") + 6)
    tools.buttons["bold"].click()
    assert "<strong>Título</strong>" in editor.toPlainText()
    for alignment, qt_alignment in (("center", Qt.AlignmentFlag.AlignHCenter),
                                     ("right", Qt.AlignmentFlag.AlignRight),
                                     ("justify", Qt.AlignmentFlag.AlignJustify)):
        tools.buttons["align:" + alignment].click()
        document = preview_document(editor.toPlainText(), tmp_path)
        found = document.find("Título")
        assert found.blockFormat().alignment() & qt_alignment
        assert not document.find("Texto forte.").isNull()
    tools.buttons["align:left"].click()
    assert "\n\n**Título**\n\n" in editor.toPlainText()
    assert set(unique_markers(editor.toPlainText())) == {1}


def test_rejected_action_preserves_document_selection_and_history(editor_ui):
    editor, tools, messages = editor_ui
    source = "Texto\n\n![Figura](assets/a.png)"
    editor.setPlainText(source)
    editor.selectAll()
    selection = editor.textCursor().selectedText()
    tools.buttons["align:center"].click()
    assert editor.toPlainText() == source
    assert editor.textCursor().selectedText() == selection
    assert not editor.document().isUndoAvailable()
    assert "imagens" in messages[-1]


def test_link_dialog_accept_cancel_and_ctrl_k(editor_ui, app):
    editor, tools, _ = editor_ui
    editor.setPlainText("Consultar")
    editor.selectAll()
    observed = []

    def fill():
        dialog = next(widget for widget in app.topLevelWidgets() if isinstance(widget, LinkDialog) and widget.isVisible())
        observed.append(dialog.label.text())
        assert dialog.width() >= 480
        assert dialog.destination.width() >= 400
        assert dialog.destination.y() > dialog.layout().labelForField(dialog.destination).y()
        dialog.destination.setText("https://example.org")
        dialog.accept()

    QTimer.singleShot(0, fill)
    QTest.keyClick(editor, Qt.Key.Key_K, Qt.KeyboardModifier.ControlModifier)
    assert observed == ["Consultar"]
    assert editor.toPlainText() == "[Consultar](<https://example.org>)"
    app.processEvents()
    assert editor.hasFocus()
    original = editor.toPlainText()

    def cancel():
        dialog = next(widget for widget in app.topLevelWidgets() if isinstance(widget, LinkDialog) and widget.isVisible())
        dialog.reject()

    QTimer.singleShot(0, cancel)
    tools.buttons["link"].click()
    assert editor.toPlainText() == original
    editor.undo()
    assert editor.toPlainText() == "Consultar"


def test_window_state_preview_manual_images_and_export(app, manual_source, tmp_path, monkeypatch):
    window = Window()
    monkeypatch.setattr(QMessageBox, "information", lambda *args: QMessageBox.StandardButton.Ok)
    vault = tmp_path / "vault"
    vault.mkdir()
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *args: str(vault))
    try:
        assert not window.editor_tools.isEnabled()
        result = convert(manual_source, tmp_path / "work")
        window.result = result
        window.editor.setPlainText(result.markdown)
        window.update_controls()
        assert window.editor_tools.isEnabled()
        for operation in ("convert", "crop", "render", None):
            window.operation = operation
            window.busy = operation is not None
            window.update_controls()
            assert window.editor_tools.isEnabled() == (operation in (None, "render"))
        original = window.editor.toPlainText()
        first_text = "Legenda que deve permanecer intacta."
        a = original.index(first_text)
        select(window.editor, a, a + len(first_text))
        window.editor_tools.buttons["align:center"].click()
        window.refresh_preview()
        assert first_text in window.preview.toPlainText()
        assert len(window.preview.targets) == len(result.assets)
        assert set(unique_markers(window.editor.toPlainText())) == {1, 2}
        image = result.assets[0]
        window.preview.selected_images = {(image.path, 0)}
        window.remove_preview_images()
        cleaned = window.editor.toPlainText()
        assert image.generated_markdown not in cleaned
        assert "text-align: center" in cleaned
        window.export()
        exported = next((vault / "Importados").iterdir())
        assert next(exported.glob("*.md")).read_text() == cleaned
        assert not (exported / image.path).exists()
        report = json.loads((exported / "conversao.json").read_text())
        assert not report["cleanup"]["reference_warnings"]
        window.editor.undo()
        assert image.generated_markdown in window.editor.toPlainText()
        window.editor.undo()
        assert window.editor.toPlainText() == original
    finally:
        window.editor.document().setModified(False)
        window.close()
        app.processEvents()


def test_keyboard_toolbar_preserves_reverse_unicode_selection(editor_ui, app):
    editor, tools, _ = editor_ui
    original = "💡 Ação e revisão"
    editor.setPlainText(original)
    select(editor, 2, 6, reverse=True)
    tools.buttons['bold'].setFocus(Qt.FocusReason.TabFocusReason)
    app.processEvents()
    assert tools.buttons['bold'].hasFocus()
    QTest.keyClick(tools.buttons['bold'], Qt.Key.Key_Space)
    assert editor.toPlainText() == "💡 **Ação** e revisão"
    assert editor.textCursor().selectedText() == "Ação"
    assert editor.textCursor().anchor() > editor.textCursor().position()
    assert editor.hasFocus()
    editor.undo()
    assert editor.toPlainText() == original
    tools.menus['Listas'].setFocus(Qt.FocusReason.TabFocusReason)
    app.processEvents()
    assert tools.menus['Listas'].hasFocus()
    observed = []
    def choose_list():
        menu = tools.menus['Listas'].menu()
        observed.append(menu.isVisible())
        menu.setActiveAction(menu.actions()[0])
        QTest.keyClick(menu, Qt.Key.Key_Return)
        menu.close()
    QTimer.singleShot(50, choose_list)
    QTest.keyClick(tools.menus['Listas'], Qt.Key.Key_Space)
    assert observed == [True]
    assert editor.toPlainText() == '- ' + original
    editor.undo()
    assert editor.toPlainText() == original
