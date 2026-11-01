"""Extração conservadora de grades nativas com bordas."""
def extract(page, blocks):
    from .structured_tables import table_markdown
    import pymupdf
    rotation, matrix = page.rotation, page.rotation_matrix
    result = {}
    native = [(line, pymupdf.Rect(line.bbox) * ~matrix)
              for block in blocks for line in block.lines]
    try:
        page.set_rotation(0)
        for table in page.find_tables(use_layout=False).tables:
            if len(table.rows) < 2 or not table.col_count:
                continue
            boxes = [box for row in table.rows for box in row.cells if box is not None]
            xs = sorted({round(box[i], 3) for box in boxes for i in (0, 2)})
            ys = sorted({round(box[i], 3) for box in boxes for i in (1, 3)})
            cells, assigned = [], []
            # Linhas que cruzam a borda também precisam entrar na conferência:
            # descartá-las aqui faria uma célula com texto parecer vazia.
            table_lines = [(line, box) for line, box in native
                           if pymupdf.Rect(table.bbox).intersects(box)]
            for r, row in enumerate(table.rows):
                for c, cell in enumerate(row.cells):
                    if cell is None:
                        continue
                    x0, y0, x1, y1 = [round(v, 3) for v in cell]
                    # O detector fornece a grade; o texto vem das mesmas linhas
                    # nativas usadas no documento, sem reordenar pontuação ou
                    # concatenar palavras pela extração independente de células.
                    cell_box = pymupdf.Rect(cell)
                    lines = sorted(((line, box) for line, box in table_lines
                                    if cell_box.contains(box)),
                                   key=lambda entry: (round(entry[1].y0 / 3), entry[1].x0))
                    assigned.extend(id(line) for line, _ in lines)
                    cells.append(dict(r0=ys.index(y0), r1=ys.index(y1),
                                      c0=xs.index(x0), c1=xs.index(x1),
                                      text='\n'.join(line.text.strip() for line, _ in lines)))
            # Uma linha cruzando divisórias ou atribuída mais de uma vez exige
            # revisão pelo recorte, em vez de publicar uma tabela incompleta.
            if not table_lines or sorted(assigned) != sorted(id(line) for line, _ in table_lines):
                continue
            header_box = pymupdf.Rect(xs[0], ys[0], xs[-1], ys[1]) * matrix
            header_lines = [line for block in blocks for line in block.lines
                            if header_box.contains(pymupdf.Rect(line.bbox))]
            has_header = bool(header_lines and all(line.flags & 16 for line in header_lines)
                              and all(cell['text'] for cell in cells if cell['r0'] == 0))
            rendered = table_markdown(dict(rows=len(ys)-1, cols=len(xs)-1, cells=cells),
                                      has_header=has_header)
            if rendered is None:
                continue
            box = tuple(pymupdf.Rect(table.bbox) * matrix)
            result[box] = rendered
    finally:
        page.set_rotation(rotation)
    return result
