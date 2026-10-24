"""Adaptador PyMuPDF. Chamado somente pelo processo auxiliar na aplicação."""
from pathlib import Path
import pymupdf


class PDFError(ValueError):
    pass


def displayed_text(page, data):
    """Geometria extraída no mesmo espaço visual dos pixmaps e recortes."""
    matrix = page.rotation_matrix
    def box(value):
        return tuple(pymupdf.Rect(value) * matrix)
    for block in data['blocks']:
        block['bbox'] = box(block['bbox'])
        for line in block.get('lines', ()):
            line['bbox'] = box(line['bbox'])
            direction = pymupdf.Point(line.get('dir', (1, 0)))
            line['dir'] = tuple(direction * matrix - pymupdf.Point(0, 0) * matrix)
            for span in line['spans']:
                span['bbox'] = box(span['bbox'])
                if 'origin' in span:
                    span['origin'] = tuple(pymupdf.Point(span['origin']) * matrix)
    return data


def displayed_tables(page):
    """Evitar a normalização destrutiva de CropBox feita por find_tables.

    A rotação muda apenas no documento aberto em memória, nunca na origem.
    O detector recebe coordenadas não rotacionadas e devolvemos espaço visual.
    """
    rotation, matrix = page.rotation, page.rotation_matrix
    try:
        page.set_rotation(0)
        return [tuple(pymupdf.Rect(table.bbox) * matrix)
                for table in page.find_tables().tables]
    finally:
        page.set_rotation(rotation)


def open_pdf(path: Path):
    try:
        doc = pymupdf.open(path)
    except Exception as exc:
        raise PDFError(f"Não foi possível abrir o PDF: {exc}") from exc
    if not doc.is_pdf:
        doc.close()
        raise PDFError("O arquivo selecionado não é um PDF.")
    if doc.needs_pass:
        doc.close()
        raise PDFError("PDF protegido por senha. Abra uma cópia sem senha para converter.")
    if not len(doc):
        doc.close()
        raise PDFError("O PDF não contém páginas.")
    return doc


def render(source: Path, page_number: int, destination: Path,
           bbox=None, dpi: int = 150):
    with open_pdf(source) as doc:
        if not 1 <= page_number <= len(doc):
            raise PDFError("Número de página inválido.")
        page = doc[page_number - 1]
        clip = page.rect if bbox is None else pymupdf.Rect(bbox) & page.rect
        if clip.is_empty or clip.is_infinite:
            raise PDFError("Selecione uma região válida dentro da página.")
        destination.parent.mkdir(parents=True, exist_ok=True)
        page.get_pixmap(dpi=dpi, clip=clip, alpha=False).save(destination)
        return tuple(page.rect)
