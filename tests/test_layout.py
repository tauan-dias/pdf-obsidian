from collections import Counter

import pymupdf

from pdf_obsidian.converter import convert
from pdf_obsidian.layout import extract_text_block, reconstruct_page
from pdf_obsidian.models import Block, Page, TextLine


def line(text, y, source=0, x=48, right=550, size=12, font="Arial", flags=0):
    return TextLine(text, (x, y - size, right, y + 3), size, font, flags, y, source)


def reconstruct(lines, images=(), vocabulary=()):
    blocks = [Block("text", item.text, 1, item.bbox, item.size, lines=[item]) for item in lines]
    page = Page(1, 595, 842, blocks + list(images))
    return reconstruct_page(page, 12, [20], {}, set(vocabulary))[0]


def test_fragmented_paragraph_and_distinct_next_paragraph():
    # Mesmo espaçamento e alinhamento da página fornecida, sem depender do PDF pessoal.
    blocks = reconstruct([
        line("Considere um exemplo de uma empresa. Nele", 480, 0),
        line("podemos encontrar arquivos pessoais (nome, endereço,", 498, 1, size=11.97),
        line("data de nascimento etc.) e dados funcionais.", 516, 2, right=310),
        line("Vale ressaltar que a coleção deve ser coerente.", 540, 3, x=68, right=370),
        line("Veja a seguir uma questão:", 564, 4, x=68, right=270),
    ])
    assert len(blocks) == 3
    assert "Nele podemos" in blocks[0].text
    assert "endereço, data" in blocks[0].text
    assert blocks[1].text.startswith("Vale ressaltar")
    assert blocks[2].text.startswith("Veja a seguir")


def test_pdf_conversion_reconstructs_independent_raw_blocks(tmp_path):
    source = tmp_path / "fragmented.pdf"
    with pymupdf.open() as doc:
        page = doc.new_page()
        page.insert_text((48, 100), "Considere uma empresa. Nela", fontsize=12)
        page.insert_text((48, 120), "podemos encontrar arquivos pessoais,", fontsize=12)
        page.insert_text((48, 140), "dados funcionais e pagamentos.", fontsize=12)
        page.insert_text((68, 175), "Vale ressaltar a coerencia dos dados.", fontsize=12)
        assert len(page.get_text("blocks")) == 4
        doc.save(source)
    result = convert(source, tmp_path / "work")
    assert "Nela podemos encontrar arquivos pessoais, dados funcionais e pagamentos." in result.markdown
    assert "pagamentos.\n\nVale ressaltar" in result.markdown
    assert any("2 junções entre blocos" in decision for decision in result.decisions)


def test_bold_and_italic_do_not_split_body_paragraph():
    blocks = reconstruct([
        line("Uma coleção de dados", 100),
        line("relacionados com coerência", 118, font="Arial-Bold", flags=16),
        line("permite consultas.", 136, font="Arial-Italic", flags=2),
    ])
    assert len(blocks) == 1


def test_short_terminal_line_starts_new_paragraph_even_in_same_block():
    blocks = reconstruct([line("Primeiro parágrafo.", 100, right=200),
                          line("Segundo parágrafo.", 118, right=220)])
    assert len(blocks) == 2


def test_heading_and_hanging_list_continuations():
    blocks = reconstruct([
        line("Título", 70, size=20),
        line("1. Item com uma explicação", 110),
        line("que continua nesta linha.", 128, x=62),
        line("2. Outro item.", 146, right=200),
    ])
    assert blocks[0].heading_level == 1
    assert blocks[1].text == "1. Item com uma explicação que continua nesta linha.\n2. Outro item."


def test_image_prevents_joining_text_across_figure():
    image = Block("image", "Figura", 1, (50, 115, 300, 120), asset="figure.png")
    blocks = reconstruct([line("Texto antes da figura", 100), line("continuação depois", 130)], [image])
    assert [block.kind for block in blocks] == ["text", "image", "text"]


def test_hyphens_require_evidence_and_preserve_compounds():
    blocks = reconstruct([line("Uma infor-", 100), line("mação útil.", 118)], vocabulary=["informação"])
    assert blocks[0].text == "Uma informação útil."
    blocks = reconstruct([line("Um guarda-", 100), line("chuva azul.", 118)])
    assert blocks[0].text == "Um guarda-chuva azul."
    blocks = reconstruct([line("Uma infor\u00ad", 100), line("mação útil.", 118)])
    assert blocks[0].text == "Uma informação útil."


def test_separate_columns_are_not_joined():
    blocks = reconstruct([line("Texto na esquerda", 100, right=250),
                          line("texto na direita", 100, x=320),
                          line("outra linha à esquerda", 118, right=250)])
    assert len(blocks) == 3


def test_spacing_between_independent_spans():
    raw = {"bbox": (48, 88, 180, 103), "lines": [{
        "bbox": (48, 88, 180, 103), "spans": [
            {"text": "dados", "size": 12, "font": "Arial", "bbox": (48, 88, 80, 103)},
            {"text": "pessoais", "size": 12, "font": "Arial-Bold", "bbox": (84, 88, 180, 103)},
        ]}]}
    block = extract_text_block(raw, 1, 0, Counter())
    assert block.text == "dados pessoais"
