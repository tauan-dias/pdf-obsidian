"""Presentation must preserve editable source and its undo history."""
from PySide6.QtGui import QFont, QTextCursor, QTextDocument

from pdf_obsidian.highlighting import MarkdownHighlighter
from pdf_obsidian.comparison import preview_document


def formats(block):
    return block.layout().formats()


def test_highlighting_preserves_source_modified_and_history(app):
    text = '# Título\n\n💡 **ação** e *ênfase* [link](assets/a.png)\n<!-- Página 1 -->'
    doc = QTextDocument()
    doc.documentLayout()
    doc.setPlainText(text)
    doc.setModified(False)
    highlighter = MarkdownHighlighter(doc)
    highlighter.rehighlight()
    assert doc.toPlainText() == text
    assert not doc.isModified()
    assert not doc.isUndoAvailable()
    assert formats(doc.begin())[0].format.fontWeight() == QFont.Weight.Bold
    block = doc.findBlockByNumber(2)
    bold = next(f for f in formats(block) if f.format.fontWeight() == QFont.Weight.Bold)
    assert bold.start == 3  # emoji occupies two UTF-16 units
    cursor = QTextCursor(doc)
    cursor.movePosition(QTextCursor.MoveOperation.End)
    cursor.insertText(' fim')
    app.processEvents()
    doc.undo()
    assert doc.toPlainText() == text
    doc.redo()
    assert doc.toPlainText() == text + ' fim'


def test_incremental_fences_comments_and_code(app):
    doc = QTextDocument()
    doc.documentLayout()
    doc.setPlainText('````python\n# codigo\n```\n````\n# titulo\n<!-- aberto\n# comentario\n-->\n# fim')
    h = MarkdownHighlighter(doc)
    h.rehighlight()
    assert doc.findBlockByNumber(1).userState() == 8
    assert doc.findBlockByNumber(2).userState() == 8
    assert doc.findBlockByNumber(3).userState() == 0
    assert doc.findBlockByNumber(6).userState() == 1
    assert formats(doc.findBlockByNumber(1))[0].format.fontWeight() != QFont.Weight.Bold
    assert formats(doc.findBlockByNumber(4))[0].format.fontWeight() == QFont.Weight.Bold
    cursor = QTextCursor(doc)
    cursor.setPosition(0)
    cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
    cursor.insertText('normal')
    app.processEvents()
    assert formats(doc.findBlockByNumber(1))[0].format.fontWeight() == QFont.Weight.Bold


def test_preview_optional_link_palette_preserves_source_and_anchor(app, tmp_path):
    source = '<!-- Página 1 -->\n\n[arquivo](assets/a.png)'
    doc = preview_document(source, tmp_path, link_color='#e5e5e5')
    fragment = doc.find('arquivo').charFormat()
    assert fragment.anchorHref() == 'assets/a.png'
    assert fragment.foreground().color().name() == '#e5e5e5'
    assert 'Página' not in doc.toPlainText()
