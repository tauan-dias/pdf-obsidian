"""Regressões dos estados de apresentação, sem documentos pessoais."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor, QPalette, QColor
from PySide6.QtWidgets import QMessageBox

from pdf_obsidian.gui import Window
from pdf_obsidian.appearance import apply_theme


def test_dark_only_and_editor_history(app, monkeypatch):
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.Yes)
    window = Window()
    try:
        assert not hasattr(window, 'theme_selector')
        assert not hasattr(window, 'settings')
        assert window.palette().color(QPalette.Window) == QColor('#090909')
        window.editor.setPlainText('Texto original')
        window.editor.moveCursor(QTextCursor.End)
        window.editor.insertPlainText(' editado')
        window.editor.selectAll()
        saved = window.editor.textCursor()
        window.preview.selected_images.add(('assets/example.png', 0))
        apply_theme(window)
        assert window.editor.toPlainText() == 'Texto original editado'
        assert window.editor.textCursor().anchor() == saved.anchor()
        assert window.editor.textCursor().position() == saved.position()
        assert window.preview.selected_images == {('assets/example.png', 0)}
        assert window.editor.document().isModified()
        window.editor.undo()
        assert window.editor.toPlainText() == 'Texto original'
        window.editor.redo()
        assert window.editor.toPlainText() == 'Texto original editado'
    finally:
        window.close()


def test_presentation_states_and_compact_geometry(app, monkeypatch, tmp_path):
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.Yes)
    window = Window()
    try:
        window.show()
        app.processEvents()
        window.resize(1024, 700)
        app.processEvents()
        assert window.width() == 1024
        assert window.height() == 700
        assert not window.welcome.state['converting']
        assert window.content.currentWidget() is window.welcome
        assert window.workspace.isHidden()
        assert window.modified_label.isHidden()
        assert window.warning_list.isHidden()
        window.warnings_toggle.setChecked(True)
        assert not window.warning_list.isHidden()
        assert window.warnings_toggle.arrowType() == Qt.DownArrow
        window.warnings_toggle.setChecked(False)
        assert window.warning_list.isHidden()
        window.busy, window.operation = True, 'convert'
        window.update_controls()
        assert window.welcome.state['converting']
        assert not window.welcome.state['canImport']
        assert window.content.currentWidget() is window.welcome
        assert not window.welcome.state['cancelling']
        assert not window.export_button.isEnabled()
        window.busy, window.operation = False, None
        window.update_controls()
        assert not window.welcome.state['converting']
        window.preview.selection_mode.setChecked(True)
        assert not window.preview.remove_button.isHidden()
        window.preview.selection_mode.setChecked(False)
        assert window.preview.remove_button.isHidden()
    finally:
        window.close()



def test_formatting_toolbar_is_compact_and_icons_have_names(app):
    window = Window()
    try:
        window.show()
        app.processEvents()
        buttons = window.editor_tools.buttons
        assert len({button.geometry().y() for button in buttons.values()}) == 1
        for command in ('bullet', 'ordered', 'quote', 'link', 'align:left', 'align:center', 'align:right', 'align:justify'):
            button = buttons[command]
            assert not button.icon().isNull()
            assert button.accessibleName()
            assert button.toolTip()
    finally:
        window.close()


def test_adaptive_toolbar_reflows_without_replacing_editor(app):
    from PySide6.QtWidgets import QBoxLayout, QPlainTextEdit, QVBoxLayout, QWidget
    from pdf_obsidian.editor_tools import EditorTools
    from pdf_obsidian.appearance import AdaptiveRow
    panel = QWidget()
    layout = QVBoxLayout(panel)
    editor = QPlainTextEdit()
    tools = EditorTools(editor, lambda *_: None)
    layout.addWidget(tools)
    layout.addWidget(editor)
    editor.setPlainText('Texto')
    editor.moveCursor(QTextCursor.End)
    editor.insertPlainText(' editado')
    editor.selectAll()
    saved = editor.textCursor()
    document = editor.document()
    try:
        panel.resize(650, 400)
        panel.show()
        app.processEvents()
        row = tools.findChild(AdaptiveRow)
        assert row.row.direction() == QBoxLayout.Direction.LeftToRight
        panel.resize(300, 400)
        app.processEvents()
        assert row.row.direction() == QBoxLayout.Direction.TopToBottom
        assert editor.document() is document
        assert editor.textCursor().anchor() == saved.anchor()
        assert editor.textCursor().position() == saved.position()
        editor.undo()
        assert editor.toPlainText() == 'Texto'
        panel.resize(650, 400)
        app.processEvents()
        assert row.row.direction() == QBoxLayout.Direction.LeftToRight
    finally:
        panel.close()


def test_preview_link_theme_keeps_destination_and_page_anchor(app, tmp_path):
    from pdf_obsidian.appearance import COLORS
    from pdf_obsidian.comparison import preview_document
    document = preview_document('<!-- Página 1 -->\n\n[PDF original](original.pdf)\n\nTexto', tmp_path)
    link = document.find('PDF original')
    assert link.charFormat().anchorHref() == 'original.pdf'
    assert link.charFormat().foreground().color() == QColor(COLORS['accent'])
    anchors = []
    block = document.begin()
    while block.isValid():
        iterator = block.begin()
        while not iterator.atEnd():
            anchors.extend(iterator.fragment().charFormat().anchorNames())
            iterator += 1
        block = block.next()
    assert 'pdf-page-1' in anchors


def test_semantic_text_colors_meet_contrast_minimum():
    """Check the actual text/surface pairs used by shared QML components."""
    from pdf_obsidian.tokens import COLORS

    def luminance(value):
        channels = [int(value[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        linear = [c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4 for c in channels]
        return sum(c * weight for c, weight in zip(linear, (.2126, .7152, .0722)))

    pairs = [(fg, bg) for fg in ('text', 'muted') for bg in ('background', 'surface', 'raised', 'hover', 'canvas')]
    pairs += [('text', 'selection'), ('warning', 'warningSurface'), ('danger', 'dangerSurface')]
    pairs += [(tone, 'background') for tone in ('success', 'warning', 'danger')]
    pairs += [('on_accent', bg) for bg in ('accent', 'accentHover', 'accentPressed')]
    for foreground, background in pairs:
        light, dark = sorted((luminance(COLORS[foreground]), luminance(COLORS[background])), reverse=True)
        assert (light + .05) / (dark + .05) >= 4.5, (foreground, background)
