"""Destaque visual incremental; nunca modifica o Markdown da sessão."""
import re

from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat


class MarkdownHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self.styles = {}
        for name, color, bold, italic in (
            ('heading', '#fafafa', True, False),
            ('muted', '#a3a3a3', False, False),
            ('code', '#c4c4c4', False, False),
            ('bold', '#f2f2f2', True, False),
            ('italic', '#dedede', False, True),
            ('link', '#e5e5e5', False, False),
        ):
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            fmt.setFontWeight(QFont.Weight.Bold if bold else QFont.Weight.Normal)
            fmt.setFontItalic(italic)
            if name == 'link':
                fmt.setFontUnderline(True)
            self.styles[name] = fmt
        self.rules = [
            (re.compile(r'^ {0,3}#{1,6}(?:\s+.*|$)'), 'heading'),
            (re.compile(r'^\s*(?:>\s*|[-+*]\s+|\d+[.)]\s+)'), 'muted'),
            (re.compile(r'(?<!\\)(\*\*|__)(?=\S).+?\1'), 'bold'),
            (re.compile(r'(?<![\\*])\*(?!\*)(?=\S).+?\*(?!\*)'), 'italic'),
            (re.compile(r'!?\[[^\]\n]*\]\([^\n)]*\)|\[\[[^\]\n]+\]\]'), 'link'),
            (re.compile(r'(`+)[^`\n]+\1'), 'code'),
        ]

    def paint(self, text, start, end, style):
        # Qt offsets count UTF-16 code units, while regex offsets count characters.
        offset = len(text[:start].encode('utf-16-le')) // 2
        length = len(text[start:end].encode('utf-16-le')) // 2
        self.setFormat(offset, length, self.styles[style])

    def highlightBlock(self, text):
        self.setCurrentBlockState(0)
        previous = self.previousBlockState()
        fence = re.match(r'^ {0,3}(`{3,}|~{3,})(.*)$', text)
        if previous >= 6:
            marker = '`' if previous % 2 == 0 else '~'
            count = previous // 2
            closing = re.fullmatch(r' {0,3}' + re.escape(marker) + '{' + str(count) + r',}\s*', text)
            self.paint(text, 0, len(text), 'code')
            self.setCurrentBlockState(0 if closing else previous)
            return
        if previous != 1 and fence and not (fence[1][0] == '`' and '`' in fence[2]):
            self.setCurrentBlockState(len(fence[1]) * 2 + (fence[1][0] == '~'))
            self.paint(text, 0, len(text), 'code')
            return
        if previous != 1 and text.startswith(('    ', '\t')):
            self.paint(text, 0, len(text), 'code')
            return
        for pattern, style in self.rules:
            for match in pattern.finditer(text):
                self.paint(text, *match.span(), style)
        start = 0 if previous == 1 else text.find('<!--')
        while start >= 0:
            end = text.find('-->', start if previous == 1 and start == 0 else start + 4)
            if end < 0:
                self.paint(text, start, len(text), 'muted')
                self.setCurrentBlockState(1)
                break
            self.paint(text, start, end + 3, 'muted')
            start = text.find('<!--', end + 3)
