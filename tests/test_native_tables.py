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
