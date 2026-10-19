"""Adaptador PyMuPDF. Chamado somente pelo processo auxiliar na aplicação."""
from pathlib import Path
import pymupdf


class PDFError(ValueError):
    pass


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
