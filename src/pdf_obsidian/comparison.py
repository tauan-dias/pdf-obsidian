"""Vínculo por página sem modificar o Markdown editável/exportado."""
from collections import Counter
from pathlib import Path
import re
from uuid import uuid4

from PySide6.QtCore import QPoint, Qt, QUrl
from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor, QTextDocument

from .tokens import COLORS

from .formatting import PARSER, parse_aligned


PAGE_MARKER = re.compile(r"(?m)^[ \t]*<!--[ \t]*Página[ \t]+([1-9]\d*)[ \t]*-->[ \t]*$")


def unique_markers(markdown):
    matches = list(PAGE_MARKER.finditer(markdown))
    counts = Counter(int(match[1]) for match in matches)
    return {int(match[1]): match for match in matches if counts[int(match[1])] == 1}


def preview_document(markdown: str, workspace: Path, parent=None):
    """Instalar âncoras Qt após o parser; HTML <a> vazio é descartado por ele."""
    markers = unique_markers(markdown)
    nonce = uuid4().hex
    tokens = {}
    aligned_tokens = {}
    lines = markdown.splitlines(keepends=True)
    # O importador Markdown do Qt pode juntar HTML ao parágrafo anterior e
    # descartar seu alinhamento. Inserir esses blocos após o parser evita isso.
    replacements = []
    for index, item in enumerate(PARSER.parse(markdown)):
        if item.type != "html_block" or item.level != 0 or not item.map:
            continue
        html = item.content.strip()
        parsed = parse_aligned(html)
        if parsed is None:
            continue
        token = f"PDFObsidian{nonce}Aligned{index}End"
        aligned_tokens[token] = (html, parsed[0][2])
        start, end = item.map
        replacements.append((start, end, token + "\n\n"))
    for start, end, replacement in reversed(replacements):
        lines[start:end] = [replacement]
    markdown = "".join(lines)

    def replace(match):
        page = int(match[1])
        if page not in markers:
            return match[0]
        token = f"PDFObsidian{nonce}Page{page}End"
        tokens[page] = token
        return token

    document = QTextDocument(parent)
    document.setBaseUrl(QUrl.fromLocalFile(str(workspace) + "/"))
    document.setMarkdown(PAGE_MARKER.sub(replace, markdown))
    alignments = {"center": Qt.AlignmentFlag.AlignHCenter,
                  "right": Qt.AlignmentFlag.AlignRight, "justify": Qt.AlignmentFlag.AlignJustify}
    for token, (html, alignment) in aligned_tokens.items():
        cursor = document.find(token)
        if not cursor.isNull():
            cursor.insertHtml(html)
            fmt = cursor.blockFormat()
            fmt.setAlignment(alignments[alignment])
            cursor.setBlockFormat(fmt)
    for page, token in tokens.items():
        cursor = document.find(token)
        if not cursor.isNull():
            fmt = QTextCharFormat()
            fmt.setAnchor(True)
            fmt.setAnchorNames([f"pdf-page-{page}"])
            cursor.insertText("\u200b", fmt)
    # Qt Markdown assigns blue to links independently of the widget palette.
    # Style the presentation document only; source/export and anchors stay intact.
    block = document.begin()
    while block.isValid():
        iterator = block.begin()
        while not iterator.atEnd():
            fragment = iterator.fragment()
            if fragment.charFormat().anchorHref():
                cursor = QTextCursor(document)
                cursor.setPosition(fragment.position())
                cursor.setPosition(fragment.position() + fragment.length(), QTextCursor.MoveMode.KeepAnchor)
                fmt = QTextCharFormat()
                fmt.setForeground(QColor(COLORS['accent']))
                cursor.mergeCharFormat(fmt)
            iterator += 1
        block = block.next()
    return document


def scroll_editor_to(editor, position):
    """Mover a janela de leitura, mantendo cursor, seleção e histórico intactos."""
    saved = editor.textCursor()
    horizontal = editor.horizontalScrollBar().value()
    target = QTextCursor(editor.document())
    target.setPosition(position)
    editor.setTextCursor(target)
    editor.centerCursor()
    top = editor.blockBoundingGeometry(target.block()).translated(editor.contentOffset()).top()
    line_height = max(1, editor.fontMetrics().lineSpacing())
    vertical = editor.verticalScrollBar().value() + round(top / line_height)
    editor.setTextCursor(saved)
    editor.verticalScrollBar().setValue(vertical)
    editor.horizontalScrollBar().setValue(horizontal)


def reading_position(browser):
    cursor = browser.cursorForPosition(QPoint(2, 2))
    anchor = None
    it = cursor.block().begin()
    while not it.atEnd():
        names = it.fragment().charFormat().anchorNames()
        if names:
            anchor = names[0]
            break
        it += 1
    return (cursor.block().text(), cursor.position(), cursor.position() - cursor.block().position(),
            browser.cursorRect(cursor).top(), browser.verticalScrollBar().value(), anchor)


def restore_reading_position(browser, saved):
    text, position, within_block, offset, scroll, anchor = saved
    if anchor:
        block = browser.document().begin()
        while block.isValid():
            it = block.begin()
            while not it.atEnd():
                fragment = it.fragment()
                if anchor in fragment.charFormat().anchorNames():
                    cursor = QTextCursor(browser.document())
                    cursor.setPosition(fragment.position())
                    browser.verticalScrollBar().setValue(
                        browser.verticalScrollBar().value() + browser.cursorRect(cursor).top() - offset)
                    return
                it += 1
            block = block.next()
    if text.strip("\u200b \t"):
        # Em texto repetido, escolher a ocorrência mais próxima da posição anterior.
        candidates = []
        cursor = browser.document().find(text)
        while not cursor.isNull():
            candidates.append(cursor)
            cursor = browser.document().find(text, cursor.selectionEnd())
        if candidates:
            cursor = min(candidates, key=lambda item: abs(item.selectionStart() + within_block - position))
            cursor.setPosition(min(cursor.selectionEnd(), cursor.selectionStart() + within_block))
            browser.verticalScrollBar().setValue(
                browser.verticalScrollBar().value() + browser.cursorRect(cursor).top() - offset)
            return
    browser.verticalScrollBar().setValue(scroll)
