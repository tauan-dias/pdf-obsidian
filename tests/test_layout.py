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


def test_two_columns_read_left_before_right():
    lines = []
    for i in range(4):
        lines.extend([line(f"Esquerda {i}.", 100 + i * 25, i, right=250),
                      line(f"Direita {i}.", 100 + i * 25, i + 10, x=320)])
    blocks = reconstruct(lines)
    assert [b.text for b in blocks] == (
        [f"Esquerda {i}." for i in range(4)] + [f"Direita {i}." for i in range(4)])


def test_spanning_heading_precedes_columns():
    lines = [line("Título", 50, size=20)]
    for i in range(3):
        lines.extend([line(f"Esquerda {i}.", 100 + i * 25, i, right=250),
                      line(f"Direita {i}.", 100 + i * 25, i + 10, x=320)])
    assert reconstruct(lines)[0].text == "Título"


def test_overlapping_spanning_figure_keeps_previous_order():
    from pdf_obsidian.reading_order import regions
    blocks = [Block("text", str(i), 1, (48, 100+i*25, 250, 112+i*25))
              for i in range(3)]
    blocks += [Block("text", str(i), 1, (320, 100+i*25, 550, 112+i*25))
               for i in range(3)]
    blocks.append(Block("image", "Figura", 1, (200, 120, 400, 145)))
    assert len(regions(blocks, 595)) == 1


def test_two_columns_keep_all_items_with_unequal_heights():
    from pdf_obsidian.reading_order import regions
    blocks = [Block("text", str(i), 1, (48, 100+i*25, 250, 112+i*25))
              for i in range(5)]
    blocks += [Block("text", str(i), 1, (320, 100+i*25, 550, 112+i*25))
               for i in range(3)]
    assert [b for group in regions(blocks, 595) for b in group] == blocks


def test_two_column_pdf_preserves_reading_order(tmp_path):
    source = tmp_path / "columns.pdf"
    with pymupdf.open() as doc:
        page = doc.new_page()
        for prefix, x in (("LEFT", 40), ("RIGHT", 330)):
            for i in range(5):
                page.insert_text((x, 100 + i * 30), f"{prefix}{i}.")
        doc.save(source)
    result = convert(source, tmp_path / "work")
    tokens = [f"{side}{i}" for side in ("LEFT", "RIGHT") for i in range(5)]
    positions = [result.markdown.index(token) for token in tokens]
    assert positions == sorted(positions)
    assert all(result.markdown.count(token) == 1 for token in tokens)
    assert any("duas colunas" in decision for decision in result.decisions)


def test_spanning_separator_splits_column_bands():
    from pdf_obsidian.reading_order import regions
    blocks = []
    for y in (100, 125, 200, 225):
        blocks += [Block("text", f"L{y}", 1, (48, y, 250, y+12)),
                   Block("text", f"R{y}", 1, (320, y, 550, y+12))]
    blocks.append(Block("text", "Heading", 1, (48, 160, 550, 180)))
    assert [b.text for group in regions(blocks, 595) for b in group] == [
        "L100", "L125", "R100", "R125", "Heading",
        "L200", "L225", "R200", "R225"]


def test_images_alone_are_not_column_evidence():
    from pdf_obsidian.reading_order import regions
    blocks = [Block("image", str(i), 1, (x, 100+i*25, x+150, 112+i*25))
              for x in (48, 320) for i in range(3)]
    assert len(regions(blocks, 595)) == 1


def test_column_image_stays_between_neighboring_text():
    lines = []
    for i in range(4):
        lines += [line(f"L{i}.", 100+i*30, i, right=250),
                  line(f"R{i}.", 100+i*30, i+10, x=320)]
    image = Block("image", "Figura", 1, (50, 115, 240, 120), asset="figure.png")
    output = reconstruct(lines, [image])
    assert [b.text for b in output] == [
        "L0.", "Figura", "L1.", "L2.", "L3.", "R0.", "R1.", "R2.", "R3."]


def test_asymmetric_columns():
    from pdf_obsidian.reading_order import regions
    blocks = [Block("text", f"{x}:{i}", 1, (x, 100+i*25, right, 112+i*25))
              for x, right in ((40, 170), (230, 550)) for i in range(4)]
    assert [b for group in regions(blocks, 595) for b in group] == blocks
