"""Renderização compartilhada de tabelas nativas e OCR."""
import html
import math

def table_markdown(item, native_lines=(), has_header=True):
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
    if has_header and all(r1 == r0 + 1 and c1 == c0 + 1 for r0, r1, c0, c1, _ in entries):
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
