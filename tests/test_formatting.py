import pytest
from markdown_it import MarkdownIt

from pdf_obsidian.formatting import aligned_markdown, format_text, parse_aligned
from pdf_obsidian.markdown import analyse_markdown, strip_page_comments


def change(text, command, value=None, start=0, end=None):
    edit = format_text(text, start, len(text) if end is None else end, command, value)
    return text[:edit.start] + edit.text + text[edit.end:]


@pytest.mark.parametrize("command,marker", [("bold", "**"), ("italic", "*")])
def test_inline_toggle_and_empty_insertion(command, marker):
    source = "💡 Ação e revisão"
    styled = change(source, command, start=2, end=6)
    assert styled == "💡 " + marker + "Ação" + marker + " e revisão"
    assert change(styled, command, start=2 + len(marker), end=6 + len(marker)) == source
    assert change(styled, command, start=2, end=6 + 2 * len(marker)) == source
    edit = format_text("Texto", 2, 2, command)
    assert edit.text == marker * 2
    assert edit.selection_start == edit.selection_end == 2 + len(marker)


def test_italic_inside_bold_does_not_remove_bold_delimiters():
    assert change("**texto**", "italic", start=2, end=7) == "***texto***"


def test_inline_preserves_heading_and_list_prefixes():
    assert change("## Título", "bold") == "## **Título**"
    assert change("- Item", "italic") == "- *Item*"
    assert change("> Texto", "bold") == "> **Texto**"
    with pytest.raises(ValueError):
        change("- Item\n- Outro", "bold")


@pytest.mark.parametrize("level", range(1, 7))
def test_heading_levels_and_toggle(level):
    styled = change("Texto", "heading", level)
    assert styled == "#" * level + " Texto"
    assert change(styled, "heading", level) == "Texto"
    assert change(styled, "heading", 0) == "Texto"


@pytest.mark.parametrize("command,expected", [
    ("bullet", "- Um\n- Dois"), ("ordered", "1. Um\n2. Dois"), ("quote", "> Um\n> Dois"),
])
def test_list_and_quote_conversion_and_toggle(command, expected):
    assert change("Um\nDois", command) == expected
    assert change(expected, command) == "Um\nDois"
    assert change("", command) in ("- ", "1. ", "> ")


def test_ordered_items_across_paragraphs_are_numbered_in_order():
    assert change("Um\n\nDois", "ordered") == "1. Um\n\n2. Dois"


@pytest.mark.parametrize("alignment", ["center", "right", "justify"])
def test_alignment_round_trip_preserves_inline_semantics(alignment):
    source = "Ação **forte**, *ênfase* e `x < 2` com [link](<assets/a.png>)."
    styled = change(source, "align", alignment)
    assert styled.startswith(f'<p style="text-align: {alignment};">')
    assert "<strong>forte</strong>" in styled
    assert "<em>ênfase</em>" in styled
    assert "<code>x &lt; 2</code>" in styled
    assert change(styled, "align", "left") == source
    assert not analyse_markdown(styled).uncertainty
    assert analyse_markdown(styled).references == {"assets/a.png"}


def test_aligned_heading_and_style_buttons():
    styled = change("## Título", "align", "center")
    assert styled == '<h2 style="text-align: center;">Título</h2>'
    styled = change(styled, "heading", 3)
    assert styled.startswith("<h3 ")
    styled = change(styled, "bold")
    assert "<strong>Título</strong>" in styled
    assert change(styled, "align", "left") == "### **Título**"
    assert change(styled, "heading", 3).startswith("<p ")
    assert "text-align: right" in change(styled, "align", "right")


def test_aligned_inline_buttons_preserve_tags_and_entities():
    source = change("A & B e **forte**", "align", "center")
    a = source.index("forte")
    styled = change(source, "italic", start=a, end=a + 5)
    assert "<strong><em>forte</em></strong>" in styled
    assert change(styled, "italic", start=styled.index("forte"), end=styled.index("forte") + 5) == source
    for a, b in [(source.index("style") + 1, source.index("style") + 2),
                 (source.index("&amp;") + 1, source.index("&amp;") + 3),
                 (source.index("<strong>") + 2, source.index("forte") + 2),
                 (source.index("forte") + 1, source.index("</strong>") + 3)]:
        with pytest.raises(ValueError):
            change(source, "bold", start=a, end=b)


def test_links_in_markdown_and_aligned_html():
    assert change("site", "link", ("site", "https://example.org/a?q=1&b=2")) == "[site](<https://example.org/a?q=1&b=2>)"
    source = change("Texto", "align", "center")
    a = source.index("Texto")
    linked = change(source, "link", ("Consultar", "assets/a.png"), a, a + 5)
    assert '<a href="assets/a.png">Consultar</a>' in linked
    assert analyse_markdown(linked).references == {"assets/a.png"}
    assert "[Consultar](<assets/a.png>)" in change(linked, "align", "left")
    with pytest.raises(ValueError):
        change("Texto", "link", ("Texto", "javascript:alert(1)"))


def test_page_markers_are_never_formatted_or_wrapped():
    source = "<!-- Página 1 -->\n\nPrimeiro.\n\n<!-- Página 2 -->\n\nSegundo.\n"
    styled = change(source, "align", "center")
    assert styled.count('style="text-align: center;"') == 2
    assert "<!-- Página 1 -->\n\n<p" in styled
    assert "<!-- Página 2 -->\n\n<p" in styled
    assert strip_page_comments(styled, 2)[1] == 2
    assert change(styled, "align", "left") == source
    with pytest.raises(ValueError):
        change("<!-- Página 1 -->", "bold")


@pytest.mark.parametrize("source", [
    "![Imagem](assets/a.png)", "Texto [[Nota]]", "- Lista", "> Citação",
    "| A | B |\n| - | - |\n| 1 | 2 |", "```python\nx = 1\n```", "    código",
    '<div>HTML</div>', '<p style="text-align: center;"><img src="assets/a.png"></p>',
    "---\ncover: assets/a.png\n---\n\nTexto",
])
def test_alignment_refuses_unsupported_selection_without_edits(source):
    with pytest.raises(ValueError):
        change(source, "align", "center")


def test_aligned_lists_and_quotes_request_left_alignment_first():
    source = change("Texto", "align", "center")
    for command in ("bullet", "ordered", "quote"):
        with pytest.raises(ValueError, match="esquerda"):
            change(source, command)


def test_unknown_html_remains_conservative_for_asset_export():
    for source in ['<p style="text-align: center;" onclick="x()">Texto</p>',
                   '<p style="text-align: center;"><a href="x" data-extra="a">x</a></p>',
                   '<p style="text-align: center;"><strong>x</em></p>',
                   '<p style="text-align: center;"><!-- escondido --></p>']:
        assert parse_aligned(source) is None
        assert analyse_markdown(source).uncertainty


def test_alignment_preserves_hard_breaks_and_code_backticks():
    source = "Primeiro  \nSegundo com ``a`b``."
    styled = change(source, "align", "justify")
    restored = aligned_markdown(styled)
    # Comparar a renderização: normalização de espaços do HTML não muda o conteúdo.
    assert MarkdownIt().render(restored) == MarkdownIt().render(source)


def test_inline_code_and_images_are_protected():
    for source in ["`código`", "![Figura](assets/a.png)"]:
        with pytest.raises(ValueError):
            change(source, "bold")


def test_selection_ending_at_next_block_does_not_format_that_block():
    source = "Primeiro\n\nSegundo"
    assert change(source, "heading", 2, 0, source.index("Segundo")) == "## Primeiro\n\nSegundo"


@pytest.mark.parametrize("source", [r"\# Não é título.", r"\- texto", r"1\. texto", r"\> texto", r"\==="])
def test_literal_markdown_prefixes_survive_alignment_round_trip(source):
    restored = aligned_markdown(change(source, "align", "center"))
    assert MarkdownIt().render(restored) == MarkdownIt().render(source)


def test_alignment_resolves_reference_links_using_document_definitions():
    source = '[Consultar][ref]\n\n[ref]: assets/a.png "Imagem original"\n'
    styled = change(source, "align", "center", 0, source.index("\n"))
    assert '<a href="assets/a.png" title="Imagem original">Consultar</a>' in styled
    assert analyse_markdown(styled).references == {"assets/a.png"}


def test_custom_inline_html_and_nested_code_remain_protected():
    for source in ['Texto <span class="especial">manual</span>', '- Item\n\n      código']:
        for command, value in [("bold", None), ("heading", 2), ("quote", None)]:
            with pytest.raises(ValueError):
                change(source, command, value)


def test_emphasis_excludes_outer_whitespace():
    assert change(" palavra ", "bold") == " **palavra** "
    source = change("uma palavra aqui", "align", "center")
    a = source.index(" palavra ")
    styled = change(source, "bold", start=a, end=a + len(" palavra "))
    assert "uma <strong>palavra</strong> aqui" in styled
    assert "uma **palavra** aqui" == aligned_markdown(styled)


def test_adjacent_and_redundant_html_emphasis_returns_valid_markdown():
    for tag, expected in [("strong", "**ab**"), ("em", "*ab*")]:
        source = f'<p style="text-align: center;"><{tag}>a</{tag}><{tag}>b</{tag}></p>'
        assert aligned_markdown(source) == expected
    source = '<p style="text-align: center;"><strong>a<strong>b</strong></strong></p>'
    assert aligned_markdown(source) == "**ab**"


def test_markdown_link_destinations_and_nested_links_are_protected():
    source = "[Consultar](<assets/a.png>) e texto"
    a = source.index("assets")
    with pytest.raises(ValueError, match="destino"):
        change(source, "bold", start=a, end=a + 6)
    with pytest.raises(ValueError, match="já contém"):
        change(source, "link", ("Consultar", "https://example.org"), 1, 10)
    assert change(source, "bold", start=1, end=10).startswith("[**Consultar**](<assets/a.png>)")


def test_link_dialog_label_preserves_existing_html_and_markdown_styles():
    from pdf_obsidian.formatting import link_label

    for source in ["## **A & B**", change("**A & B**", "align", "center")]:
        label = link_label(source, 0, len(source))
        assert label == "A & B"
        linked = change(source, "link", (label, "assets/a.png"))
        if source.startswith("<"):
            assert '<a href="assets/a.png"><strong>A &amp; B</strong></a>' in linked
        else:
            assert linked == "## [**A & B**](<assets/a.png>)"
