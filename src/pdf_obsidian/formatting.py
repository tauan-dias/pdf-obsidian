"""Transformações localizadas do Markdown; posições em caracteres Python."""
from dataclasses import dataclass
from html import escape, unescape
from html.parser import HTMLParser
import re

from markdown_it import MarkdownIt


PARSER = MarkdownIt("commonmark").enable("table")
ALIGNED = re.compile(r'<(p|h[1-6]) style="text-align: (center|right|justify);">(.*)</\1>', re.S)
PREFIX = re.compile(r"^(?: {0,3}#{1,6}\s+| {0,3}(?:[-+*]|\d+[.)])\s+|>\s?)")
MARKDOWN_LINK = re.compile(r"(?<!!)\[((?:\\.|[^\]\\\n])*)\](?:\((?:<[^>\n]*>|[^)\n]*)\)|\[[^\]\n]*\])")


@dataclass(frozen=True)
class Edit:
    start: int
    end: int
    text: str
    selection_start: int
    selection_end: int


class AlignedHTML(HTMLParser):
    """Ler somente os elementos e atributos emitidos pela barra de edição."""

    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.stack = []
        self.links = []
        self.feed(source)
        self.close()
        if self.stack:
            raise ValueError("HTML incompleto.")

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if len(attributes) != len(attrs):
            raise ValueError("Atributos repetidos.")
        if tag == "br" and not attrs:
            self.parts.append("  \n")
            return
        if tag not in ("strong", "em", "code", "a"):
            raise ValueError("Elemento HTML não reconhecido.")
        if self.stack and self.stack[-1][0] == "code":
            raise ValueError("Código com elementos HTML.")
        if tag == "a":
            if set(attributes) - {"href", "title"} or "href" not in attributes:
                raise ValueError("Link HTML não reconhecido.")
            href = attributes["href"]
            if not href or not PARSER.validateLink(href) or any(c in href for c in "\r\n<>"):
                raise ValueError("Destino de link inválido.")
            if any(item[0] == "a" for item in self.stack):
                raise ValueError("Links aninhados.")
            self.links.append(href)
            self.parts.append("[")
        elif attrs:
            raise ValueError("Atributo HTML não reconhecido.")
        elif tag != "code" and not any(item[0] == tag for item in self.stack):
            self.parts.append({"strong": "**", "em": "*"}[tag])
        self.stack.append((tag, attributes, len(self.parts)))

    def handle_endtag(self, tag):
        if not self.stack or self.stack[-1][0] != tag:
            raise ValueError("Tags HTML sobrepostas.")
        _, attributes, start = self.stack.pop()
        if tag == "a":
            title = attributes.get("title")
            suffix = (' "' + title.replace('"', '&quot;') + '"') if title else ""
            self.parts.append("](<" + attributes["href"] + ">" + suffix + ")")
        elif tag == "code":
            content = "".join(self.parts[start:])
            fence = "`" * (max((len(m[0]) for m in re.finditer(r"`+", content)), default=0) + 1)
            pad = " " if content.startswith(("`", " ")) or content.endswith(("`", " ")) else ""
            self.parts[start:] = [fence + pad + content + pad + fence]
        elif not any(item[0] == tag for item in self.stack):
            self.parts.append({"strong": "**", "em": "*"}[tag])

    def handle_data(self, data):
        if self.stack and self.stack[-1][0] == "code":
            self.parts.append(data)
        else:
            self.parts.append(re.sub(r"([\\`*_\[\]<>])", r"\\\1", data))

    def handle_comment(self, data):
        raise ValueError("Comentário dentro do bloco alinhado.")

    def handle_decl(self, decl):
        raise ValueError("Declaração HTML não reconhecida.")

    def handle_pi(self, data):
        raise ValueError("Instrução HTML não reconhecida.")

    def unknown_decl(self, data):
        raise ValueError("Declaração HTML não reconhecida.")

    def handle_startendtag(self, tag, attrs):
        if tag != "br":
            raise ValueError("Elemento HTML não reconhecido.")
        self.handle_starttag(tag, attrs)


def parse_aligned(source):
    match = ALIGNED.fullmatch(source)
    if not match:
        return None
    try:
        parsed = AlignedHTML(match[3])
    except (ValueError, TypeError):
        return None
    return match, parsed


def aligned_markdown(source):
    parsed = parse_aligned(source)
    if parsed is None:
        raise ValueError("HTML personalizado não pode ser alterado pela barra.")
    match, content = parsed
    # Estilos adjacentes equivalentes devem virar um único trecho Markdown;
    # delimitadores encostados podem adquirir outro significado no parser.
    merged = re.sub(r"</(strong|em)><\1>", "", match[3])
    if merged != match[3]:
        content = AlignedHTML(merged)
    prefix = "" if match[1] == "p" else "#" * int(match[1][1]) + " "
    body = "".join(content.parts)
    # Texto literal como "# exemplo" ou "1. item" não deve adquirir uma
    # estrutura nova ao deixar o HTML.
    body = re.sub(r"(?m)^( {0,3})([#>+\-=])", r"\1\\\2", body)
    body = re.sub(r"(?m)^( {0,3}\d+)([.)])(?=\s)", r"\1\\\2", body)
    return prefix + body


def _render_aligned(source, alignment, environment):
    if "[[" in source:
        raise ValueError("Wikilinks não podem ser alinhados nesta versão.")
    tokens = PARSER.parse(source or "Texto", environment)
    if len(tokens) != 3 or tokens[0].type not in ("paragraph_open", "heading_open"):
        raise ValueError("Alinhe somente parágrafos textuais e títulos.")
    inline = tokens[1]
    if any(child.type in ("image", "html_inline") for child in inline.children or []):
        raise ValueError("Trechos com imagens ou HTML personalizado não podem ser alinhados.")
    body = PARSER.renderer.renderInline(inline.children or [], PARSER.options, environment) if source else ""
    # Um bloco por linha facilita a edição do código-fonte e a análise de anexos.
    body = body.replace("\n", " ")
    tag = tokens[0].tag
    result = f'<{tag} style="text-align: {alignment};">{body}</{tag}>'
    if parse_aligned(result) is None:
        raise ValueError("Este trecho contém formatação incompatível com o alinhamento.")
    return result


def _blocks(text):
    lines = text.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    blocks = []
    for token in PARSER.parse(text):
        if token.level == 0 and token.map and not token.type.endswith("_close"):
            a, b = (offsets[index] for index in token.map)
            blocks.append((a, b - (len(text[a:b]) - len(text[a:b].rstrip("\r\n"))), token.type))
    if text.startswith(("---\n", "---\r\n")):
        close = next((i for i, line in enumerate(lines[1:], 1) if line.strip() in ("---", "...")), len(lines) - 1)
        end = offsets[close + 1]
        blocks = [(a, b, "protected" if a < end else kind) for a, b, kind in blocks]
    return blocks


def _inline_bounds(source, lo, hi, kind):
    if kind == "html_block":
        parsed = parse_aligned(source)
        if parsed is None:
            raise ValueError("HTML personalizado deve ser editado diretamente no Markdown.")
        match, _ = parsed
        lo, hi = max(lo, match.start(3)), min(hi, match.end(3))
        if lo > hi:
            raise ValueError("Posicione o cursor no texto do bloco, fora das tags.")
    elif kind == "heading_open":
        prefix = re.match(r" {0,3}#{1,6}\s+", source)
        if prefix:
            lo = max(lo, prefix.end())
            hi = max(lo, hi)
        elif "\n" in source:
            raise ValueError("Converta o título para o formato com # antes de editar seu estilo.")
    elif kind in ("bullet_list_open", "ordered_list_open", "blockquote_open"):
        line_start = source.rfind("\n", 0, lo) + 1
        line_end = source.find("\n", lo)
        line_end = len(source) if line_end < 0 else line_end
        if hi > line_end:
            raise ValueError("Para negrito, itálico ou link, selecione texto de um único item ou linha da citação.")
        prefix = PREFIX.match(source[line_start:line_end])
        if prefix:
            lo = max(lo, line_start + prefix.end())
            hi = max(lo, hi)
    return lo, hi


def _visible_text(source, html=False):
    if html:
        return unescape(re.sub(r"<[^>]*>", "", source))
    tokens = PARSER.parseInline(source)
    return "".join(" " if child.type in ("softbreak", "hardbreak") else child.content
                   for token in tokens for child in token.children or []
                   if child.type in ("text", "code_inline", "softbreak", "hardbreak"))


def link_label(text, start, end):
    """Texto legível para o diálogo, sem os delimitadores de formatação."""
    if start == end:
        return ""
    blocks = [(a, b, kind) for a, b, kind in _blocks(text) if a < end and b > start]
    if len(blocks) != 1:
        raise ValueError("Selecione texto dentro de um único bloco para inserir um link.")
    a, b, kind = blocks[0]
    lo, hi = _inline_bounds(text[a:b], max(0, start - a), min(b - a, end - a), kind)
    return _visible_text(text[a:b][lo:hi], kind == "html_block")


def _inline(source, a, b, command, value, html=False):
    if command in ("bold", "italic") and a != b:
        selected = source[a:b]
        leading = len(selected) - len(selected.lstrip())
        trailing = len(selected) - len(selected.rstrip())
        if leading == len(selected):
            raise ValueError("Selecione texto além dos espaços para aplicar o estilo.")
        a += leading
        b -= trailing
    if html:
        parsed = parse_aligned(source)
        if parsed is None:
            raise ValueError("HTML personalizado não pode ser alterado pela barra.")
        match, _ = parsed
        lo, hi = match.start(3), match.end(3)
        if a < lo or b > hi:
            raise ValueError("Selecione apenas o texto dentro do bloco alinhado, sem as tags externas.")
        for token in re.finditer(r"<[^>]*>|&(?:#\d+|#x[0-9a-fA-F]+|\w+);", source):
            if token.start() < a < token.end() or token.start() < b < token.end():
                raise ValueError("A seleção interrompe uma tag ou entidade HTML.")
    elif any(m.start() < b and m.end() > a or a == b and m.start() <= a < m.end()
             for m in re.finditer(r"(`+).*?\1|!\[[^\]\n]*\]\([^\n]*?\)", source, re.S)):
        raise ValueError("Não aplique formatação dentro de código ou imagens.")
    if not html:
        for match in MARKDOWN_LINK.finditer(source):
            touches = match.start() < b and match.end() > a or a == b and match.start() <= a < match.end()
            if not touches:
                continue
            if command == "link":
                raise ValueError("Este trecho já contém um link. Edite seu destino diretamente no Markdown.")
            if not (match.start(1) <= a <= b <= match.end(1) or a <= match.start() and b >= match.end()):
                raise ValueError("Selecione o texto do link sem incluir partes de seu destino ou delimitadores.")
    selected = source[a:b]
    if command == "link":
        label, destination = value
        if not destination or not PARSER.validateLink(destination) or any(c in destination for c in "\r\n<>"):
            raise ValueError("Informe um destino de link válido.")
        if html:
            body = selected if label in (selected, _visible_text(selected, True)) else escape(label)
            replacement = '<a href="' + escape(destination, quote=True) + '">' + body + '</a>'
        else:
            body = selected if label in (selected, _visible_text(selected)) else re.sub(r"([\\\[\]])", r"\\\1", label)
            replacement = "[" + body + "](<" + destination + ">)"
        left = 0
        right = len(replacement)
    else:
        opening, closing = (("<strong>", "</strong>") if command == "bold" else ("<em>", "</em>")) if html else (("**", "**") if command == "bold" else ("*", "*"))
        if selected.startswith(opening) and selected.endswith(closing) and len(selected) >= len(opening + closing):
            replacement = selected[len(opening):-len(closing)]
            left, right = 0, len(replacement)
        elif (source[:a].endswith(opening) and source[b:].startswith(closing)
              and (html or command == "bold" or not (source[:a].endswith("**") or source[b:].startswith("**")))):
            a -= len(opening)
            b += len(closing)
            replacement = selected
            left, right = 0, len(replacement)
        else:
            replacement = opening + selected + closing
            left, right = len(opening), len(opening) + len(selected)
    result = source[:a] + replacement + source[b:]
    if html and parse_aligned(result) is None:
        raise ValueError("Selecione um trecho com tags completas para evitar formatação sobreposta.")
    return Edit(a, b, replacement, a + left, a + right)


def format_text(text, start, end, command, value=None):
    """Validar toda a seleção antes de devolver uma única edição atômica."""
    if not 0 <= start <= end <= len(text):
        raise ValueError("Seleção inválida.")
    if command not in ("bold", "italic", "link", "heading", "bullet", "ordered", "quote", "align"):
        raise ValueError("Comando de formatação desconhecido.")
    if command == "align" and value not in ("left", "center", "right", "justify"):
        raise ValueError("Alinhamento inválido.")
    if command == "heading" and value not in range(7):
        raise ValueError("Nível de título inválido.")
    blocks = [(a, b, kind) for a, b, kind in _blocks(text)
              if (a <= start <= b if start == end else a < end and b > start)]
    # Marcadores são separadores: nunca convertê-los, mesmo entre páginas.
    blocks = [(a, b, kind) for a, b, kind in blocks
              if not re.fullmatch(r"\s*<!--\s*Página\s+[1-9]\d*\s*-->\s*", text[a:b])]
    if not blocks:
        line_start = text.rfind("\n", 0, start) + 1
        line_end = text.find("\n", start)
        line_end = len(text) if line_end < 0 else line_end
        if text[line_start:line_end].strip():
            raise ValueError("Escolha um parágrafo de texto para formatar.")
        blocks = [(line_start, line_end, "paragraph_open")]
    for a, b, kind in blocks:
        managed = kind == "html_block" and parse_aligned(text[a:b]) is not None
        if kind not in ("paragraph_open", "heading_open", "bullet_list_open", "ordered_list_open", "blockquote_open") and not managed:
            raise ValueError("A seleção contém código, tabela, metadados ou HTML personalizado; nenhuma alteração foi aplicada.")
        if not managed:
            for token in PARSER.parse(text[a:b]):
                if token.type in ("fence", "code_block", "html_block") or any(
                        child.type == "html_inline" for child in token.children or []):
                    raise ValueError("Código e HTML personalizado devem ser editados diretamente no Markdown.")
    if command in ("bold", "italic", "link"):
        if len(blocks) != 1:
            raise ValueError("Selecione texto dentro de um único bloco para esta formatação.")
        a, b, kind = blocks[0]
        if start < a or end > b:
            raise ValueError("A seleção deve ficar dentro do texto do bloco.")
        source = text[a:b]
        lo, hi = _inline_bounds(source, start - a, end - a, kind)
        edit = _inline(source, lo, hi, command, value, kind == "html_block")
        return Edit(a + edit.start, a + edit.end, edit.text, a + edit.selection_start, a + edit.selection_end)
    replacements = []
    item_number = 0
    environment = {}
    if command == "align":
        PARSER.parse(text, environment)
    for a, b, kind in blocks:
        source = text[a:b]
        managed = kind == "html_block"
        if managed:
            if command in ("bullet", "ordered", "quote"):
                raise ValueError("Use o alinhamento à esquerda antes de transformar este bloco em lista ou citação.")
            if command == "heading":
                match, _ = parse_aligned(source)
                tag = f"h{value}" if value and match[1] != f"h{value}" else "p"
                replacement = f'<{tag} style="text-align: {match[2]};">{match[3]}</{tag}>'
            else:
                match, _ = parse_aligned(source)
                replacement = aligned_markdown(source) if value == "left" else f'<{match[1]} style="text-align: {value};">{match[3]}</{match[1]}>'
        elif command == "align":
            if kind not in ("paragraph_open", "heading_open"):
                raise ValueError("Alinhe somente parágrafos e títulos; listas e citações devem permanecer à esquerda.")
            replacement = source if value == "left" else _render_aligned(source, value, environment)
        elif command == "heading":
            if kind not in ("paragraph_open", "heading_open"):
                raise ValueError("Transforme a lista ou citação em parágrafos antes de aplicar um título.")
            previous = PARSER.parse(source)
            content = previous[1].content if previous else ""
            old = int(previous[0].tag[1]) if previous and previous[0].type == "heading_open" else 0
            level = 0 if old == value else value
            replacement = ("#" * level + " " if level else "") + content
        else:
            lines = source.splitlines() or [""]
            if any(re.match(r"^\s{2,}(?:[-+*]|\d+[.)])\s|^>\s*>|^\s*(```|~~~)", item) for item in lines):
                raise ValueError("Listas ou citações complexas devem ser editadas diretamente no Markdown.")
            pattern = {"bullet": r"^[-+*]\s+", "ordered": r"^\d+[.)]\s+", "quote": r"^>\s?"}[command]
            toggle = bool(source.strip()) and all(re.match(pattern, item) for item in lines if item.strip())
            replacement_lines = []
            for item in lines:
                plain = re.sub(pattern, "", item) if toggle else PREFIX.sub("", item)
                if item.strip() or len(lines) == 1:
                    item_number += 1
                prefix = "" if toggle else {"bullet": "- ", "ordered": f"{item_number}. ", "quote": "> "}[command]
                replacement_lines.append(prefix + plain if item.strip() or len(lines) == 1 else "")
            replacement = "\n".join(replacement_lines)
        replacements.append((a, b, replacement))
    a, b = blocks[0][0], blocks[-1][1]
    result = text[a:b]
    for lo, hi, replacement in reversed(replacements):
        result = result[:lo - a] + replacement + result[hi - a:]
    if start == end:
        caret = a + min(max(0, start - a), len(result))
        parsed = parse_aligned(result)
        if parsed:
            caret = max(caret, a + parsed[0].start(3))
        selection_start = selection_end = caret
    else:
        selection_start, selection_end = a, a + len(result)
    return Edit(a, b, result, selection_start, selection_end)
