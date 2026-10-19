"""Análise conservadora do Markdown para limpeza e seleção de anexos."""
from dataclasses import dataclass, field
from pathlib import PurePosixPath
import posixpath
import re
from urllib.parse import unquote, urlsplit

from markdown_it import MarkdownIt

from .formatting import parse_aligned


PAGE_COMMENT = re.compile(r"[ \t]*<!--[ \t]*Página[ \t]+([1-9]\d*)[ \t]*-->[ \t]*")
WIKILINK = re.compile(r"!?\[\[([^\]\n]+)\]\]")


@dataclass(frozen=True)
class ImageParagraph:
    asset: str
    start: int
    end: int
    text: str


@dataclass
class MarkdownImage:
    asset: str
    occurrence: int
    paragraph: ImageParagraph | None = None


@dataclass
class MarkdownAnalysis:
    references: set[str] = field(default_factory=set)
    images: list[ImageParagraph] = field(default_factory=list)
    protected_lines: set[int] = field(default_factory=set)
    uncertainty: list[str] = field(default_factory=list)
    image_occurrences: list[MarkdownImage] = field(default_factory=list)


def utf16_position(text, offset):
    return len(text[:offset].encode("utf-16-le")) // 2


def analyse_markdown(markdown: str, available_assets=()):
    """Nunca usar exemplos de código como referências ou alvos de edição.

    HTML, frontmatter e caminhos não resolvidos preservam os anexos por segurança.
    Nenhum alvo externo é aberto ou consultado.
    """
    result = MarkdownAnalysis()
    available = set(available_assets)
    lines = markdown.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    tokens = MarkdownIt("commonmark").enable("table").parse(markdown)
    image_counts = {}

    def uncertain(reason):
        if reason not in result.uncertainty:
            result.uncertainty.append(reason)

    if markdown.startswith(("---\n", "---\r\n")):
        uncertain("Metadados YAML: possíveis referências fora da sintaxe Markdown.")
        end = next((index for index, line in enumerate(lines[1:], start=1)
                    if line.strip() in ("---", "...")), len(lines) - 1)
        result.protected_lines.update(range(end + 1))

    def target(raw, wiki=False):
        if wiki:
            raw = raw.split("|", 1)[0].strip()
        try:
            url = urlsplit(raw)
        except ValueError:
            uncertain("Destino de link não reconhecido.")
            return None
        if url.scheme or url.netloc:
            if url.scheme not in ("http", "https", "mailto", "data"):
                uncertain("Link com protocolo que pode conter referências locais.")
            return None
        path = posixpath.normpath(unquote(url.path).replace("\\", "/"))
        if path.startswith("assets/"):
            result.references.add(path)
            return path
        if path in available:
            result.references.add(path)
            return path
        if path in (".", "original.pdf"):
            return None
        matches = {asset for asset in available if PurePosixPath(asset).name == path}
        if matches:
            result.references.update(matches)
            return next(iter(matches)) if len(matches) == 1 else None
        if wiki or "assets" in path.split("/"):
            uncertain("Referência local não resolvida; os anexos foram preservados.")
        return None

    def visit(children):
        for child in children:
            if child.type == "image":
                asset = target(child.attrGet("src") or "")
                if asset:
                    occurrence = image_counts.get(asset, 0)
                    result.image_occurrences.append(MarkdownImage(asset, occurrence))
                    image_counts[asset] = occurrence + 1
            elif child.type == "link_open":
                target(child.attrGet("href") or "")
            elif child.type == "text":
                for match in WIKILINK.finditer(child.content):
                    target(match[1], wiki=True)
                remaining = WIKILINK.sub("", child.content)
                if "[[" in remaining or "assets/" in remaining:
                    uncertain("Possível referência com sintaxe incompleta ou não reconhecida.")
            elif child.type == "html_inline":
                if not re.fullmatch(r"<!--.*?-->", child.content, flags=re.S):
                    uncertain("HTML pode referenciar anexos fora dos links Markdown.")

    for index, token in enumerate(tokens):
        if token.type in ("fence", "code_block") and token.map:
            result.protected_lines.update(range(*token.map))
        if token.type == "html_block":
            content = token.content.strip()
            aligned = parse_aligned(content)
            if aligned:
                for href in aligned[1].links:
                    target(href)
            elif not re.fullmatch(r"<!--.*?-->", content, flags=re.S):
                uncertain("HTML pode referenciar anexos fora dos links Markdown.")
            if not PAGE_COMMENT.fullmatch(content) and token.map:
                result.protected_lines.update(range(*token.map))
        if token.type != "inline":
            continue
        children = token.children or []
        visit(children)
        if (token.level == 1 and token.map and token.map[1] == token.map[0] + 1
                and index > 0 and tokens[index - 1].type == "paragraph_open"
                and len(children) == 1 and children[0].type == "image"):
            start_line, end_line = token.map
            asset = target(children[0].attrGet("src") or "")
            if asset:
                end = offsets[end_line]
                # Remover somente a quebra vazia que acompanha a incorporação.
                if end_line < len(lines) and lines[end_line] in ("\n", "\r\n"):
                    end = offsets[end_line + 1]
                paragraph = ImageParagraph(
                    asset, offsets[start_line], end, lines[start_line].rstrip("\r\n"),
                )
                result.images.append(paragraph)
                result.image_occurrences[-1].paragraph = paragraph
    return result


def strip_page_comments(markdown: str, page_count: int):
    analysis = analyse_markdown(markdown)
    output, removed = [], 0
    for number, line in enumerate(markdown.splitlines(keepends=True)):
        match = PAGE_COMMENT.fullmatch(line.rstrip("\r\n"))
        if number not in analysis.protected_lines and match and int(match[1]) <= page_count:
            removed += 1
        else:
            output.append(line)
    return "".join(output), removed
