"""Conservative OCR composition in the PDF's displayed coordinate system."""
import html
import math
import re
import unicodedata

from .models import Block, TextLine


def intersection(a, b):
    return max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))


def area(box):
    return max(0, box[2] - box[0]) * max(0, box[3] - box[1])


def normalized(text):
    return re.sub(r'\W+', '', unicodedata.normalize('NFKC', text).casefold())


def formula_markdown(text):
    text = text.strip()
    if not text or len(text) > 16000 or any(token in text for token in ('<unk>', '<pad>', '<s>', '</s>')):
        return None
    text = text.removeprefix('$$').removesuffix('$$').strip()
    depth = 0
    for token in re.findall(r'\\.|[{}]', text):
        if token == '{': depth += 1
        if token == '}': depth -= 1
        if depth < 0: return None
    if depth or not text:
        return None
    return '$$\n' + text + '\n$$'


def table_markdown(item, native_lines=()):
    rows, cols, cells = item.get('rows'), item.get('cols'), item.get('cells')
    if not isinstance(rows, int) or not isinstance(cols, int) or not (0 < rows <= 500 and 0 < cols <= 100):
        return None
    if not isinstance(cells, list) or not cells or len(cells) > 10000:
        return None
    occupied, entries = set(), []
    for cell in cells:
        if not isinstance(cell, dict): return None
        indices = [cell.get(k) for k in ('r0', 'r1', 'c0', 'c1')]
        if any(type(n) is not int for n in indices): return None
        r0, r1, c0, c1 = indices
        if not (0 <= r0 < r1 <= rows and 0 <= c0 < c1 <= cols): return None
        covered = {(r, c) for r in range(r0, r1) for c in range(c0, c1)}
        if covered & occupied: return None
        occupied |= covered
        text = cell.get('text', '')
        if not isinstance(text, str) or len(text) > 20000: return None
        box = cell.get('bbox')
        if isinstance(box, list) and len(box) == 4 and all(isinstance(n, (float, int)) and math.isfinite(n) for n in box):
            direct = [line.text for line in native_lines if intersection(line.bbox, box) >= area(line.bbox) * .85]
            if direct:
                text = ' '.join(direct)
        entries.append((r0, r1, c0, c1, text))
    if len(occupied) != rows * cols: return None
    if all(r1 == r0 + 1 and c1 == c0 + 1 for r0, r1, c0, c1, _ in entries):
        grid = [[''] * cols for _ in range(rows)]
        for r0, _, c0, _, text in entries:
            grid[r0][c0] = html.escape(text).replace('|', '\\|').replace('\n', '<br>')
        lines = ['| ' + ' | '.join(row) + ' |' for row in grid]
        lines.insert(1, '| ' + ' | '.join(['---'] * cols) + ' |')
        return '\n'.join(lines)
    output = ['<table>']
    for r in range(rows):
        output.append('<tr>')
        for r0, r1, c0, c1, text in sorted(entries):
            if r0 == r:
                output.append(f'<td rowspan="{r1-r0}" colspan="{c1-c0}">{html.escape(text).replace(chr(10), "<br>")}</td>')
        output.append('</tr>')
    output.append('</table>')
    return '\n'.join(output)


def merge_recognition(page, recognized, native_blocks, regions, decisions, warnings):
    from .models import Warning
    native = [line for block in native_blocks for line in block.lines]
    # Keep only candidates in the requested regions; the model cannot rewrite
    # unrelated native text merely because it saw the whole page bitmap.
    def eligible(box):
        return any(intersection(box, region) >= area(box) * .7 for region in regions)
    structured, additions = [], []
    for item in recognized:
        if item['kind'] == 'text' or not eligible(item['bbox']):
            continue
        text = table_markdown(item, native) if item['kind'] == 'table' else formula_markdown(item.get('text', ''))
        if text is None:
            warnings.append(Warning(page.number, f'Reconhecimento de {"tabela" if item["kind"] == "table" else "fórmula"} inválido; confira a imagem.'))
            continue
        box = tuple(item['bbox'])
        # Do not hide conflicting direct text under a recognized structure.
        direct = [line for line in native if intersection(line.bbox, box) >= area(line.bbox) * .85]
        if item['kind'] == 'table':
            joined = normalized(' '.join(c.get('text', '') for c in item.get('cells', [])))
            if direct and any(normalized(line.text) not in joined for line in direct):
                # Native cells may have filled OCR mistakes; verify against final output too.
                if any(normalized(line.text) not in normalized(html.unescape(re.sub(r'<[^>]+>', ' ', text))) for line in direct):
                    warnings.append(Warning(page.number, 'Tabela reconhecida conflita com texto nativo; imagem e texto preservados.'))
                    continue
        structured.append(box)
        additions.append(Block('recognized_' + item['kind'], text, page.number, box, role='recognized'))
    for index, item in enumerate(recognized):
        box = tuple(item['bbox'])
        if item['kind'] != 'text' or not eligible(box) or any(intersection(box, region) >= area(box) * .7 for region in structured):
            continue
        text = re.sub(r'\s+', ' ', item.get('text', '')).strip()
        if not text: continue
        nearby = [line for line in native if intersection(box, line.bbox) >= min(area(box), area(line.bbox)) * .5]
        if nearby:
            joined = normalized(' '.join(line.text for line in nearby))
            if normalized(text) and normalized(text) in joined:
                continue
            # Ambiguity favors native text; it is never silently replaced.
            warnings.append(Warning(page.number, 'OCR sobrepõe texto nativo com conteúdo diferente; extração direta preservada.'))
            continue
        size = min(12., max(6., (box[3] - box[1]) * .75))
        line = TextLine(text, box, size, 'OCR', 0, box[3], -index - 1, role='body')
        additions.append(Block('text', text, page.number, box, size=size, lines=[line], role='body'))
    # Remove native duplicates only inside a validated table, and only when its
    # text is present in that table. Leave all other native blocks unchanged.
    for block in list(page.blocks):
        if block.kind != 'text': continue
        kept = [line for line in block.lines if not any(
            addition.kind == 'recognized_table' and intersection(line.bbox, addition.bbox) >= area(line.bbox) * .85
            and normalized(line.text) in normalized(html.unescape(re.sub(r'<[^>]+>', ' ', addition.text))) for addition in additions)]
        if len(kept) != len(block.lines):
            if kept:
                block.lines = kept
                block.text = ' '.join(line.text for line in kept)
                block.bbox = (min(l.bbox[0] for l in kept), min(l.bbox[1] for l in kept), max(l.bbox[2] for l in kept), max(l.bbox[3] for l in kept))
            else:
                page.blocks.remove(block)
    page.blocks.extend(additions)
    if additions:
        warnings.append(Warning(page.number, 'Conteúdo reconhecido automaticamente por OCR; confira texto, tabelas e fórmulas nas imagens preservadas.'))
        decisions.append(f'Página {page.number}: OCR adicionou {len(additions)} blocos, preservando as imagens de referência.')
    return len(additions)
