"""Reconstrução conservadora de parágrafos a partir da geometria das linhas."""
from collections import Counter, defaultdict
import re
from statistics import median

from .models import Block, TextLine


LIST_START = re.compile(r"^(?:[•●▪]|[-*]|\d+[.)])\s+")
CAPTION_START = re.compile(r"^(?:figura|fig\.|tabela|quadro|gráfico|ilustração|fonte)(?:\b|\s|:)", re.I)
WORD = re.compile(r"[^\W\d_]+(?:-[^\W\d_]+)*", re.UNICODE)
TERMINAL = re.compile(r"[.!?…][\s\"'”’\)\]]*$")


def union_bbox(boxes):
    boxes = list(boxes)
    return (min(box[0] for box in boxes), min(box[1] for box in boxes),
            max(box[2] for box in boxes), max(box[3] for box in boxes))


def extract_text_block(raw, page, source_block, sizes):
    lines = []
    for raw_line in raw["lines"]:
        parts, styles = [], Counter()
        previous = None
        dx, dy = raw_line.get('dir', (1, 0))
        def projected_edges(bbox):
            x0, y0, x1, y1 = bbox
            return [x * dx + y * dy for x in (x0, x1) for y in (y0, y1)]
        for span in raw_line["spans"]:
            text = span["text"]
            size = round(span["size"], 1)
            weight = len(text.strip())
            sizes[size] += weight
            styles[(size, span.get("font", ""), span.get("flags", 0))] += weight
            if (previous and parts and text and not parts[-1].endswith(" ") and not text.startswith(" ")
                    and min(projected_edges(span['bbox'])) - max(projected_edges(previous['bbox']))
                    >= min(size, previous["size"]) * .15
                    and text[0] not in ",.;:!?)]}"):
                parts.append(" ")
            parts.append(text)
            previous = span
        if not styles:
            continue
        size, font, flags = styles.most_common(1)[0][0]
        monospace = bool(flags & 8) and abs(dx - 1) <= .01 and abs(dy) <= .01
        text = "".join(parts).rstrip() if monospace else re.sub(r"\s+", " ", "".join(parts)).strip()
        if not text.strip():
            continue
        baseline = median(span.get("origin", (0, raw_line["bbox"][3]))[1]
                          for span in raw_line["spans"] if span["text"].strip())
        lines.append(TextLine(text, tuple(raw_line["bbox"]), size, font, flags,
                              baseline, source_block, tuple(raw_line.get("dir", (1, 0))),
                              role='code' if monospace else None))
    if not lines:
        return None
    weights = Counter()
    for line in lines:
        weights[line.size] += len(line.text)
    separator = "\n" if any(LIST_START.match(line.text) for line in lines) else " "
    return Block("text", separator.join(line.text for line in lines), page,
                 tuple(raw["bbox"]), weights.most_common(1)[0][0], lines=lines)


def word_inventory(pages):
    return {match[0].casefold() for page in pages for block in page.blocks
            for line in block.lines for match in WORD.finditer(line.text)}


def _role(line, body_size, heading_sizes, outline):
    if line.role:
        return line.role, None
    if abs(line.direction[0] - 1) > .01 or abs(line.direction[1]) > .01:
        return "isolated", None
    if LIST_START.match(line.text):
        return "list", None
    if CAPTION_START.match(line.text):
        return "caption", None
    level = outline.get(line.text.casefold())
    if level is None and line.size >= body_size * 1.18 and len(line.text) <= 180:
        level = heading_sizes.index(line.size) + 1 if line.size in heading_sizes else 1
    return ("heading", level) if level else ("body", None)


def _font_family(font):
    font = font.split("+")[-1].casefold()
    return re.sub(r"[\s,_-]|bold|italic|oblique|regular|roman", "", font)


def _same_style(a, b):
    return (abs(a.size - b.size) <= max(.5, min(a.size, b.size) * .05)
            and _font_family(a.font) == _font_family(b.font)
            and a.flags & 8 == b.flags & 8)


def _leading(lines):
    values = []
    for first, second in zip(lines, lines[1:]):
        gap = second.baseline - first.baseline
        if (_same_style(first, second) and abs(first.bbox[0] - second.bbox[0]) <= first.size * 2
                and first.size * .8 <= gap <= first.size * 2.1):
            values.append(gap)
    return median(values) if values else median(line.size for line in lines) * 1.2


def _first_letter(text):
    return next((char for char in text if char.isalpha()), "")


def _image_between(first, second, images):
    left, right = min(first.bbox[0], second.bbox[0]), max(first.bbox[2], second.bbox[2])
    return any(image.bbox[0] < right and image.bbox[2] > left
               and first.baseline < image.bbox[1] < second.baseline for image in images)


def _can_join(group, line, role, level, leading, right_edge, images):
    previous = group.lines[-1]
    metadata_continuation = group.role == "question_header" and role == "question_metadata"
    if (not _same_style(previous, line) and not metadata_continuation) or _image_between(previous, line, images):
        return False
    gap = line.baseline - previous.baseline
    if group.role == role == 'code':
        return previous.size * .4 < gap <= max(previous.size, line.size) * 2.1
    if gap <= previous.size * .4 or gap > leading * 1.25:
        return False
    same_block = previous.source_block == line.source_block
    aligned = abs(line.bbox[0] - min(item.bbox[0] for item in group.lines)) <= line.size * .6
    lowercase = _first_letter(line.text).islower()
    terminal = bool(TERMINAL.search(previous.text))
    full_line = previous.bbox[2] >= right_edge - max(line.size * 1.5, (right_edge - previous.bbox[0]) * .05)
    hanging = group.lines[0].bbox[0] + line.size * .5 <= line.bbox[0] <= group.lines[0].bbox[0] + line.size * 4
    if group.role == "question_header" and role == "question_metadata":
        return aligned or hanging
    if group.role in ("question_header", "question_option", "question_statement"):
        if role == "body" and hanging and (not terminal or full_line):
            return True
    if group.role == "heading":
        return (role == "heading" and level == group.heading_level and same_block and aligned)
    if group.role == "list":
        hanging = group.lines[0].bbox[0] + line.size * .5 <= line.bbox[0] <= group.lines[0].bbox[0] + line.size * 4
        return role == "body" and (hanging or (aligned and not terminal and lowercase))
    if group.role == "caption":
        return role == "body" and same_block and aligned and not terminal
    if group.role not in ("body", "question_header", "question_option", "question_statement", "question_unresolved", "question_metadata") or role != "body":
        return False
    first_line_indent = (len(group.lines) == 1 and 0 < previous.bbox[0] - line.bbox[0] <= line.size * 2
                         and (full_line or lowercase))
    if not (aligned or first_line_indent):
        return False
    if not same_block:
        # Um bloco novo exige continuidade textual, além da proximidade física.
        return not terminal and (lowercase or full_line or previous.text.endswith((",", ";", ":", "-", "\u00ad")))
    # Dentro de um bloco, uma linha curta que encerra frase pode finalizar o
    # parágrafo; recuo ou espaçamento maior já foram tratados acima.
    return not (terminal and not full_line and not lowercase)


def _append(previous, following, vocabulary):
    if previous.endswith("\u00ad"):
        return previous[:-1] + following, 1
    if previous.endswith("-") and following and following[0].islower():
        first = re.search(r"([^\W\d_]+)-$", previous)
        second = re.match(r"[^\W\d_]+", following)
        if first and second:
            combined = (first[1] + second[0]).casefold()
            compound = (first[1] + "-" + second[0]).casefold()
            if combined in vocabulary and compound not in vocabulary:
                return previous[:-1] + following, 1
        # Sem evidência, preservar o hífen, inclusive em palavras compostas.
        return previous + following, 0
    return previous + " " + following, 0


def reconstruct_page(page, body_size, heading_sizes, outline, vocabulary, _regional=False):
    """Reconstruir dentro da página, preservando suas âncoras e as imagens."""
    if not _regional:
        from copy import copy
        from .reading_order import regions
        groups = regions(page.blocks, page.width)
        if len(groups) > 1:
            output, decisions = [], []
            for group in groups:
                region = copy(page)
                region.blocks = group
                blocks, changes = reconstruct_page(region, body_size, heading_sizes, outline, vocabulary, True)
                output.extend(blocks)
                decisions.extend(changes)
            decisions.append(f"Página {page.number}: leitura organizada em regiões de duas colunas.")
            return output, decisions
    text_blocks = [block for block in page.blocks if block.kind == "text"]
    images = [block for block in page.blocks if block.kind != "text"]
    lines = sorted((line for block in text_blocks for line in block.lines),
                   key=lambda line: (round(line.bbox[1] / 3), line.bbox[0]))
    if not lines:
        return page.blocks, []
    regular = [line for line in lines if _role(line, body_size, heading_sizes, outline)[0] == "body"]
    leading = _leading(regular or lines)
    ends = sorted(line.bbox[2] for line in regular or lines)
    right_edge = ends[min(len(ends) - 1, int(len(ends) * .85))]
    paragraphs = []
    dehyphenated = 0
    for line in lines:
        role, level = _role(line, body_size, heading_sizes, outline)
        if paragraphs and _can_join(paragraphs[-1], line, role, level, leading, right_edge, images):
            group = paragraphs[-1]
            if role == 'code':
                group.text, fixed = group.text + '\n' + line.text, 0
            else:
                group.text, fixed = _append(group.text, line.text, vocabulary)
            dehyphenated += fixed
            group.lines.append(line)
            group.bbox = union_bbox((group.bbox, line.bbox))
        else:
            paragraphs.append(Block("text", line.text, page.number, line.bbox, line.size,
                                    lines=[line], role=role, heading_level=level))
    ordered = sorted(paragraphs + images, key=lambda block: (round(block.bbox[1] / 3), block.bbox[0]))
    output = []
    for block in ordered:
        if (output and block.role == output[-1].role == "list" and block.kind == output[-1].kind == "text"
                and block.bbox[1] - output[-1].bbox[3] <= leading * 1.5):
            previous = output[-1]
            previous.text += "\n" + block.text
            previous.lines.extend(block.lines)
            previous.bbox = union_bbox((previous.bbox, block.bbox))
        else:
            output.append(block)
    joined = sum(max(0, len({line.source_block for line in block.lines}) - 1)
                 for block in output if block.kind == "text" and block.role != "list")
    source_groups = defaultdict(set)
    for index, block in enumerate(output):
        for line in block.lines:
            source_groups[line.source_block].add(index)
    separated = sum(max(0, len(groups) - 1) for groups in source_groups.values())
    decisions = []
    if joined or separated or dehyphenated:
        decisions.append(f"Página {page.number}: reconstrução de parágrafos — "
                         f"{joined} junções entre blocos, {separated} separações e "
                         f"{dehyphenated} hifens de quebra de linha resolvidos.")
    return output, decisions
