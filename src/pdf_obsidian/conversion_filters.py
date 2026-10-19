"""Correções geométricas conservadoras, sem OCR ou classificação semântica."""
from collections import Counter, defaultdict
from hashlib import sha256
import json
import re

from .layout import extract_text_block, union_bbox


def deduplicate_text_blocks(raw_blocks, page, decisions):
    """Descartar somente linhas iguais e sobrepostas antes de contar estilos."""
    parsed = []
    for raw in raw_blocks:
        if raw.get('type') != 0:
            continue
        entries = []
        for raw_line in raw['lines']:
            block = extract_text_block({**raw, 'lines': [raw_line]}, page, 0, Counter())
            if block:
                entries.append((raw_line, block.lines[0]))
        parsed.append((raw, entries))
    prefixes = [(match[1], line) for _, entries in parsed for _, line in entries
                if (match := re.match(r'^(\d{1,4}[.)])\s*\(', line.text))]
    seen = defaultdict(list)
    for raw, entries in parsed:
        kept = []
        for raw_line, line in entries:
            if re.fullmatch(r'\d{1,4}[.)]', line.text) and any(
                    number == line.text and line.direction == following.direction
                    and all(abs(line.bbox[axis] - following.bbox[axis]) <= 1 for axis in (0, 1, 3))
                    and line.bbox[2] <= following.bbox[2]
                    for number, following in prefixes):
                decisions.append(f'Página {page}: removido número sobreposto ao prefixo de questão: {line.text}')
                continue
            key = (line.text, line.direction)
            if any(all(abs(a - b) <= 1 for a, b in zip(line.bbox, previous))
                   for previous in seen[key]):
                decisions.append(f'Página {page}: removida linha sobreposta duplicada: {line.text}')
                continue
            seen[key].append(line.bbox)
            kept.append(raw_line)
        if kept:
            yield {**raw, 'lines': kept, 'bbox': union_bbox(line['bbox'] for line in kept)}


def margin_zone(bbox, height):
    if bbox[1] >= 0 and bbox[3] <= height * .1:
        return 'cabeçalho'
    if bbox[1] >= height * .9 and bbox[3] <= height:
        return 'rodapé'
    return None


def vector_signature(rect, drawings):
    """Identidade de caminhos locais, independente da posição na página."""
    import pymupdf

    def local(value):
        if isinstance(value, pymupdf.Point):
            return [round(value.x - rect.x0, 3), round(value.y - rect.y0, 3)]
        if isinstance(value, pymupdf.Rect):
            return [round(value.x0 - rect.x0, 3), round(value.y0 - rect.y0, 3),
                    round(value.x1 - rect.x0, 3), round(value.y1 - rect.y0, 3)]
        if isinstance(value, pymupdf.Quad):
            return [local(point) for point in (value.ul, value.ur, value.ll, value.lr)]
        if isinstance(value, (tuple, list)):
            return [local(item) for item in value]
        if isinstance(value, float):
            return round(value, 3)
        return value

    paths = []
    for drawing in drawings:
        bounds = drawing['rect']
        if not rect.contains(bounds):
            continue
        keys = ('type', 'color', 'fill', 'width', 'lineCap', 'lineJoin', 'dashes',
                'even_odd', 'closePath', 'fill_opacity', 'stroke_opacity', 'items')
        paths.append({key: local(drawing.get(key)) for key in keys})
    if not paths:
        return None
    return sha256(json.dumps(paths, sort_keys=True).encode()).hexdigest()


def recurring_margins(pages, regions):
    """Retornar índices (página, região) com identidade e geometria recorrentes.

    Cada grupo inteiro precisa caber na tolerância; não encadear deslocamentos
    que levariam elementos distantes ao mesmo grupo.
    """
    groups = defaultdict(list)
    for page, items in zip(pages, regions):
        for index, (rect, kind, digest) in enumerate(items):
            zone = margin_zone(rect, page.height)
            if not zone or kind not in ('image', 'figure') or not digest:
                continue
            geometry = (rect.x0 / page.width, rect.y0 / page.height,
                        rect.width / page.width, rect.height / page.height)
            key = kind, zone, digest
            candidates = groups[key]
            group = next((group for group in candidates if all(
                max(*(item[2][axis] for item in group), geometry[axis])
                - min(*(item[2][axis] for item in group), geometry[axis]) <= .005 + 1e-9
                for axis in range(4))), None)
            if group is None:
                group = []
                candidates.append(group)
            group.append((page.number, index, geometry))
    filtered = {}
    for (_, zone, digest), candidates in groups.items():
        for group in candidates:
            count = len({item[0] for item in group})
            if count >= max(3, len(pages) * .7):
                reason = f'Elemento recorrente no {zone}: {count} de {len(pages)} páginas, mesma identidade e posição.'
                for page, index, _ in group:
                    filtered[page, index] = reason, digest
    return filtered
