"""Código sintético com espaços textuais e recuo geométrico."""
import pymupdf
import pytest
from markdown_it import MarkdownIt

from pdf_obsidian.converter import convert


@pytest.mark.parametrize("positioned_indent", [False, True])
def test_native_code_preserves_lines_indentation_and_markdown_literals(tmp_path, positioned_indent):
    source = tmp_path / "code.pdf"
    expected = ['# exemplo ``` literal', 'if valor >= 3:', '    print("a_b * c")',
                '    if ativo:', '        print("ok")', 'else:', '    print("fim")']
    with pymupdf.open() as doc:
        page = doc.new_page()
        page.insert_text((40, 70), "Explicacao antes do codigo.")
        for i, line in enumerate(expected):
            spaces = len(line) - len(line.lstrip())
            page.insert_text((40 + (spaces * 6.6 if positioned_indent else 0), 110 + i * 16),
                             line.lstrip() if positioned_indent else line, fontname="cour", fontsize=11)
        page.insert_text((40, 260), "Explicacao depois do codigo.")
        doc.save(source)
    original = source.read_bytes()
    result = convert(source, tmp_path / "work")
    fences = [token.content.rstrip('\n') for token in MarkdownIt().parse(result.markdown)
              if token.type == 'fence']
    assert '\n'.join(expected) in fences
    assert 'Explicacao antes do codigo.' in result.markdown
    assert 'Explicacao depois do codigo.' in result.markdown
    assert source.read_bytes() == original
