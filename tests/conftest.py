import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QT_QPA_PLATFORMTHEME"] = ""
os.environ["QT_STYLE_OVERRIDE"] = "Fusion"
os.environ["QT_QUICK_BACKEND"] = "software"

# Unit/regression fixtures must not load multi-GB models implicitly. Explicit
# OCR integration tools/tests opt into the prepared local directory.
import tempfile
_unprepared_ocr = tempfile.TemporaryDirectory(prefix='pdf-obsidian-unprepared-test-ocr-')
os.environ['PDF_OBSIDIAN_OCR_DIR'] = _unprepared_ocr.name

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def decorative_source(tmp_path):
    """Dois logos no topo; uma figura central compartilha o raster do primeiro."""
    import pymupdf
    images = []
    for color in ((20, 70, 160), (180, 60, 40)):
        pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 80, 20), False)
        pixmap.set_rect(pixmap.irect, color)
        images.append(pixmap.tobytes("png"))
    source = tmp_path / "apostila-com-logos.pdf"
    with pymupdf.open() as doc:
        font = pymupdf.Font("symb")
        for number in range(1, 6):
            page = doc.new_page()
            page.insert_image(pymupdf.Rect(50, 20, 170, 50), stream=images[0])
            page.insert_image(pymupdf.Rect(350, 20, 470, 50), stream=images[1])
            page.insert_text((50, 110), f"Capitulo {number}", fontsize=20)
            page.insert_text((50, 150), "Conteudo para estudo e comparacao.", fontsize=12)
            page.insert_font(fontname="math", fontbuffer=font.buffer)
            page.insert_text((50, 200), "∑ ∫ √", fontname="math", fontsize=16)
            page.insert_image(pymupdf.Rect(50, 250, 170, 280), stream=images[0])
            page.draw_rect(pymupdf.Rect(50, 370, 150, 400), color=(.1, .2, .6), fill=(.8, .9, 1))
        doc.save(source)
    return source


@pytest.fixture
def manual_source(tmp_path):
    """Duas páginas com raster e ornamento vetorial: nenhuma sugestão automática."""
    import pymupdf
    logo = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 80, 24), False)
    logo.set_rect(logo.irect, (30, 90, 160))
    image = logo.tobytes("png")
    source = tmp_path / "apostila-sem-sugestoes.pdf"
    with pymupdf.open() as doc:
        for number in range(1, 3):
            page = doc.new_page()
            page.insert_text((50, 90), f"Aula {number}", fontsize=20)
            page.insert_text((50, 140), "Texto essencial para estudar.", fontsize=12)
            page.insert_image(pymupdf.Rect(50, 180, 170, 216), stream=image)
            page.insert_text((50, 255), "Legenda que deve permanecer intacta.", fontsize=12)
            page.draw_rect(pymupdf.Rect(50, 310, 170, 340), color=(.7, .2, .1), fill=(.95, .7, .6))
        doc.save(source)
    return source
