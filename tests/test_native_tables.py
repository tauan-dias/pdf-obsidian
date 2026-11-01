import pymupdf
import pytest
from pdf_obsidian.converter import convert


@pytest.mark.parametrize("header", [False, True])
@pytest.mark.parametrize("merged", [False, True])
def test_native_table_keeps_image_and_cells(tmp_path, merged, header):
    source = tmp_path / "table.pdf"
    with pymupdf.open() as doc:
        page = doc.new_page()
        for row in range(4):
            page.draw_line((40, 80 + row*30), (340, 80 + row*30))
        for col in range(4):
            page.draw_line((40 + col*100, 110 if merged and col == 1 else 80),
                           (40 + col*100, 170))
        for row in range(3):
            for col in range(3):
                if merged and row == 0 and col == 1:
                    continue
                page.insert_text((50+col*100, 100+row*30), f"R{row}C{col}", fontname="hebo" if header and row == 0 else "helv")
        doc.save(source)
    before = source.read_bytes()
    result = convert(source, tmp_path / "work")
    assert ("<table>" in result.markdown) == (merged or not header)
    assert "![Tabela" in result.markdown
    assert result.markdown.count("R0C0") == 1
    if merged:
        assert 'colspan="2"' in result.markdown
    assert before == source.read_bytes()


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_native_cells_use_positioned_lines_instead_of_detector_text(tmp_path, monkeypatch, rotation):
    """O detector pode juntar palavras e deslocar pontuação sem perder letras."""
    from pymupdf.table import Table

    source = tmp_path / "positioned-cells.pdf"
    with pymupdf.open() as doc:
        page = doc.new_page()
        for y in (80, 120, 160):
            page.draw_line((40, y), (440, y))
        for x in (40, 240, 440):
            page.draw_line((x, 80), (x, 160))
        for x, y, text in [(50, 100, "Dados locais"), (250, 100, "Projeto, seguranca"),
                            (50, 140, "Foco principal"), (250, 140, "Valor: 3.6")]:
            page.insert_text((x, y), text)
        page.set_rotation(rotation)
        doc.save(source)
    monkeypatch.setattr(Table, "extract", lambda self, **kwargs:
                        [["Dadoslocais", "Projetoseguranca,"],
                         ["Focoprincipal", "Valor36:."]])
    result = convert(source, tmp_path / "work")
    for text in ("Dados locais", "Projeto, seguranca", "Foco principal", "Valor: 3.6"):
        assert text in result.markdown
    assert "Projetoseguranca" not in result.markdown
    assert "![Tabela" in result.markdown


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
@pytest.mark.parametrize("position", [(50, 88), (50, 158), (38, 100), (425, 100), (50, 128)])
def test_partial_cell_overlap_refuses_incomplete_transcription(tmp_path, rotation, position):
    """Inclui caixa tipográfica que cruza a borda sem perder os glifos."""
    source = tmp_path / "partial-cell.pdf"
    with pymupdf.open() as doc:
        page = doc.new_page()
        for y in (80, 120, 160):
            page.draw_line((40, y), (440, y))
        for x in (40, 240, 440):
            page.draw_line((x, 80), (x, 160))
        page.insert_text(position, "EDGE")
        page.insert_text((250, 105), "Outro valor")
        page.insert_text((250, 145), "Ultima linha")
        if position == (50, 88):
            assert page.find_tables(use_layout=False).tables[0].extract()[0][0] == "EDGE"
        page.set_rotation(rotation)
        doc.save(source)
    original = source.read_bytes()
    result = convert(source, tmp_path / "work")
    assert not any(block.kind == "recognized_table" for page in result.pages for block in page.blocks)
    assert "<table>" not in result.markdown
    assert "![Tabela" in result.markdown
    assert all((result.workspace / asset.path).is_file() for asset in result.assets)
    assert source.read_bytes() == original


def test_text_outside_table_does_not_block_complete_transcription(tmp_path):
    source = tmp_path / "outside-table.pdf"
    with pymupdf.open() as doc:
        page = doc.new_page()
        for y in (80, 120, 160):
            page.draw_line((40, y), (440, y))
        for x in (40, 240, 440):
            page.draw_line((x, 80), (x, 160))
        page.insert_text((50, 70), "Texto externo")
        page.insert_text((50, 105), "Primeiro valor")
        page.insert_text((250, 145), "Segundo valor")
        doc.save(source)
    result = convert(source, tmp_path / "work")
    assert any(block.kind == "recognized_table" for page in result.pages for block in page.blocks)
    assert "Primeiro valor" in result.markdown and "Segundo valor" in result.markdown
    assert result.markdown.count("Texto externo") == 1
