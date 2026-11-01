"""Vínculo por página sem modificar o Markdown editável/exportado."""
from collections import Counter
from pathlib import Path
import os
import re
import stat
from uuid import uuid4

from PySide6.QtCore import QPoint, Qt, QUrl, QByteArray, QBuffer, QIODevice
from PySide6.QtGui import QColor, QTextBlockFormat, QTextCharFormat, QTextCursor, QTextDocument, QImageReader

from .tokens import COLORS
from .security import MAX_PIXELS

from .formatting import PARSER, parse_aligned


PAGE_MARKER = re.compile(r"(?m)^[ \t]*<!--[ \t]*Página[ \t]+([1-9]\d*)[ \t]*-->[ \t]*$")


def unique_markers(markdown):
    from .markdown import analyse_markdown
    protected = analyse_markdown(markdown).protected_lines
    matches = []
    offset = 0
    for number, line in enumerate(markdown.splitlines(keepends=True)):
        if number not in protected:
            match = PAGE_MARKER.match(markdown, offset, offset + len(line.rstrip('\r\n')))
            if match:
                matches.append(match)
        offset += len(line)
    counts = Counter(int(match[1]) for match in matches)
    return {int(match[1]): match for match in matches if counts[int(match[1])] == 1}


class PreviewDocument(QTextDocument):
    """Carregar somente imagens locais da pasta de anexos da sessão."""
    def __init__(self, workspace, parent=None):
        super().__init__(parent)
        self.assets_root = Path(workspace).resolve() / 'assets'

    def loadResource(self, kind, url):
        if kind != QTextDocument.ResourceType.ImageResource:
            return None
        resolved = self.baseUrl().resolved(url)
        if not resolved.isLocalFile() or resolved.host():
            return None
        path = Path(os.path.abspath(resolved.toLocalFile()))
        if not path.is_relative_to(self.assets_root):
            return None
        # Abrir por descritores sem seguir symlinks; decodificar os mesmos bytes
        # que foram validados, mesmo se outro processo trocar o caminho.
        descriptors = []
        try:
            fd = os.open(self.assets_root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            descriptors.append(fd)
            parts = path.relative_to(self.assets_root).parts
            if not parts:
                return None
            for part in parts[:-1]:
                fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                descriptors.append(fd)
            fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
            descriptors.append(fd)
            metadata = os.fstat(fd)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > 64 * 1024**2:
                return None
            with os.fdopen(os.dup(fd), 'rb') as stream:
                data = stream.read(64 * 1024**2 + 1)
            if len(data) > 64 * 1024**2:
                return None
        except (OSError, ValueError):
            return None
        finally:
            for descriptor in reversed(descriptors):
                os.close(descriptor)
        buffer = QBuffer()
        buffer.setData(QByteArray(data))
        buffer.open(QIODevice.OpenModeFlag.ReadOnly)
        reader = QImageReader(buffer)
        # Os anexos da conversão são PNG; não ampliar a superfície de codecs
        # para formatos ativos ou com referências próprias a outros arquivos.
        if reader.format() != b'png':
            return None
        size = reader.size()
        if not size.isValid() or size.width() * size.height() > MAX_PIXELS:
            return None
        image = reader.read()
        return image if not image.isNull() else None


def preview_document(markdown: str, workspace: Path, parent=None, *, link_color=None):
    """Instalar âncoras Qt após o parser; HTML <a> vazio é descartado por ele."""
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
    markers = unique_markers(markdown)

    def replace(match):
        page = int(match[1])
        if page not in markers or markers[page].span() != match.span():
            return match[0]
        token = f"PDFObsidian{nonce}Page{page}End"
        tokens[page] = token
        return token

    document = PreviewDocument(workspace, parent)
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
        if link_color is not None:
            # Presentation document only: improve reading rhythm without changing source.
            cursor = QTextCursor(block)
            block_format = block.blockFormat()
            block_format.setLineHeight(140, QTextBlockFormat.LineHeightTypes.ProportionalHeight.value)
            block_format.setTopMargin(16 if block_format.headingLevel() else 4)
            block_format.setBottomMargin(10)
            cursor.setBlockFormat(block_format)
        iterator = block.begin()
        while not iterator.atEnd():
            fragment = iterator.fragment()
            if fragment.charFormat().anchorHref():
                cursor = QTextCursor(document)
                cursor.setPosition(fragment.position())
                cursor.setPosition(fragment.position() + fragment.length(), QTextCursor.MoveMode.KeepAnchor)
                fmt = QTextCharFormat()
                fmt.setForeground(QColor(link_color or COLORS['accent']))
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
