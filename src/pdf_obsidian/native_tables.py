"""Extração conservadora de grades nativas com bordas."""
from .recognition_merge import normalized


def extract(page, blocks):
    from .structured_tables import table_markdown
    import pymupdf
    rotation, matrix = page.rotation, page.rotation_matrix
    result = {}
    try:
        page.set_rotation(0)
        for table in page.find_tables(use_layout=False).tables:
            rows = table.extract()
            if len(rows) < 2 or not rows[0]:
                continue
            boxes = [box for row in table.rows for box in row.cells if box is not None]
            xs = sorted({round(box[i], 3) for box in boxes for i in (0, 2)})
            ys = sorted({round(box[i], 3) for box in boxes for i in (1, 3)})
            cells = []
            for r, row in enumerate(table.rows):
                for c, cell in enumerate(row.cells):
                    if cell is None:
                        continue
                    x0, y0, x1, y1 = [round(v, 3) for v in cell]
                    cells.append(dict(r0=ys.index(y0), r1=ys.index(y1),
                                      c0=xs.index(x0), c1=xs.index(x1),
                                      text=rows[r][c] or ""))
            header_box = pymupdf.Rect(xs[0], ys[0], xs[-1], ys[1]) * matrix
            header_lines = [line for block in blocks for line in block.lines
                            if header_box.contains(pymupdf.Rect(line.bbox))]
            has_header = bool(header_lines and all(line.flags & 16 for line in header_lines)
                              and all(rows[0]))
            rendered = table_markdown(dict(rows=len(ys)-1, cols=len(xs)-1, cells=cells),
                                      has_header=has_header)
            if rendered is None:
                continue
            box = tuple(pymupdf.Rect(table.bbox) * matrix)
            joined = normalized(' '.join(cell or '' for row in rows for cell in row))
            lines = [line for block in blocks for line in block.lines
                     if pymupdf.Rect(box).contains(pymupdf.Rect(line.bbox))]
            if not lines or any(normalized(line.text) not in joined for line in lines):
                continue
            result[box] = rendered
    finally:
        page.set_rotation(rotation)
    return result
