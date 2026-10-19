import pytest

from pdf_obsidian.markdown import analyse_markdown, strip_page_comments


@pytest.mark.parametrize("markdown,expected", [
    ("![Imagem](assets/a.png)", {"assets/a.png"}),
    ("[Abrir](./assets/a.png)", {"assets/a.png"}),
    ("[![Imagem](assets/a.png)](assets/b.png)", {"assets/a.png", "assets/b.png"}),
    ("![Imagem][foto]\n\n[foto]: assets/a.png", {"assets/a.png"}),
    ("[foto][]\n\n[foto]: assets/a.png", {"assets/a.png"}),
    ("[foto]\n\n[foto]: assets/a.png", {"assets/a.png"}),
    ("![[assets/a.png|200]]", {"assets/a.png"}),
    ("[[a.png|Abrir]]", {"assets/a.png"}),
    ("![Imagem](assets/imagem%20com%20espaco.png)", {"assets/imagem com espaco.png"}),
    ("| Figura |\n| --- |\n| ![Imagem](assets/a.png) |", {"assets/a.png"}),
    ("![Imagem](https://example.org/imagem.png)", set()),
    ("`![Imagem](assets/a.png)`", set()),
    ("```md\n![Imagem](assets/a.png)\n![[assets/b.png]]\n```", set()),
    ("    ![Imagem](assets/a.png)\n", set()),
    ("<!-- ![Imagem](assets/a.png) -->", set()),
])
def test_reference_analysis(markdown, expected):
    analysis = analyse_markdown(markdown, ["assets/a.png", "assets/b.png", "assets/imagem com espaco.png"])
    assert analysis.references == expected
    assert not analysis.uncertainty


@pytest.mark.parametrize("markdown", [
    '<img src="assets/a.png">',
    'Texto <span data-src="assets/a.png">imagem</span>',
    '---\ncover: assets/a.png\n---\nTexto',
    '![[assets/a.png',
    '[Imagem](assets/a.png',
    '![[pasta-desconhecida/imagem.png]]',
    '[Imagem](../assets/a.png)',
])
def test_uncertain_references_are_explicit(markdown):
    assert analyse_markdown(markdown, ["assets/a.png"]).uncertainty


def test_page_cleanup_only_changes_actual_markers():
    markdown = ("<!-- Página 1 -->\n\nTexto da página 1.\n\n"
                "```md\n<!-- Página 2 -->\n```\n\n"
                "~~~\n<!-- Página 3 -->\n~~~\n\n"
                "    <!-- Página 4 -->\n\n"
                "`<!-- Página 5 -->`\n\n"
                "<pre>\n<!-- Página 6 -->\n</pre>\n\n"
                "<!-- Página 2 -->\n\n<!-- Página 99 -->\n")
    cleaned, count = strip_page_comments(markdown, 6)
    assert count == 2
    assert "Texto da página 1." in cleaned
    assert "```md\n<!-- Página 2 -->\n```" in cleaned
    assert "~~~\n<!-- Página 3 -->\n~~~" in cleaned
    assert "    <!-- Página 4 -->" in cleaned
    assert "`<!-- Página 5 -->`" in cleaned
    assert "<pre>\n<!-- Página 6 -->\n</pre>" in cleaned
    assert "<!-- Página 99 -->" in cleaned
    assert strip_page_comments(cleaned, 6) == (cleaned, 0)


def test_frontmatter_page_comments_are_preserved():
    markdown = "---\nexample: |\n  <!-- Página 1 -->\n---\n\n<!-- Página 1 -->\n\nTexto."
    cleaned, count = strip_page_comments(markdown, 1)
    assert count == 1
    assert "  <!-- Página 1 -->" in cleaned
