import json
from pathlib import Path
import re

import pymupdf
import pytest

from pdf_obsidian.converter import convert, make_crop, ConversionCancelled
from pdf_obsidian.exporter import export_document
from pdf_obsidian.pdf import PDFError, render


def test_filename_newline_keeps_note_title_on_one_line(tmp_path):
    source = tmp_path / "Título com\nquebra de linha.pdf"
    with pymupdf.open() as doc:
        doc.new_page().insert_text((50, 100), "Conteudo preservado.")
        doc.save(source)
    original = source.read_bytes()
    result = convert(source, tmp_path / "work")
    assert result.title == "Título com quebra de linha"
    assert result.markdown.startswith("# Título com quebra de linha\n\n")
    target = export_document(result, tmp_path)
    assert (target / "original.pdf").read_bytes() == original == source.read_bytes()


@pytest.fixture
def source(tmp_path):
    path = tmp_path / "Apostila de Física.pdf"
    doc = pymupdf.open()
    for n in range(3):
        page = doc.new_page()
        page.insert_text((50, 40), "Curso de Fisica", fontsize=9)
        page.insert_text((50, 100), f"Capitulo {n + 1}", fontsize=20)
        page.insert_text((50, 150), "Texto com acentos: física, ação e revisão.", fontsize=12)
        page.insert_text((50, 175), "Segundo paragrafo.", fontsize=12)
        page.draw_rect(pymupdf.Rect(50, 250, 150, 300), color=(1, 0, 0), fill=(1, 1, 0))
        page.insert_text((50, 820), f"Pagina {n + 1}", fontsize=9)
    doc.set_toc([[1, "Capitulo 1", 1], [1, "Capitulo 2", 2], [1, "Capitulo 3", 3]])
    doc.save(path)
    doc.close()
    return path


def test_conversion_order_headings_figures(source, tmp_path):
    result = convert(source, tmp_path / "work")
    assert "## Capitulo 1" in result.markdown
    assert "física, ação e revisão" in result.markdown
    assert result.markdown.index("Capitulo 1") < result.markdown.index("Segundo paragrafo") < result.markdown.index("Capitulo 2")
    assert "Curso de Fisica" not in result.markdown
    assert "Pagina 1" not in result.markdown
    assert len(result.decisions) == 6
    assert len(list((result.workspace / "assets").glob("*.png"))) == 3
    for asset in re.findall(r"!\[[^]]*\]\(([^)]+)\)", result.markdown):
        assert (result.workspace / asset).is_file()


def test_export_edits_collision_and_report(source, tmp_path):
    result = convert(source, tmp_path / "work")
    crop = make_crop(source, result.workspace, 1, (40, 90, 250, 180))
    edited = result.markdown + f"\nCorrecao manual.\n![Recorte]({crop})\n"
    vault = tmp_path / "vault"
    vault.mkdir()
    first = export_document(result, vault, edited)
    second = export_document(result, vault, edited)
    assert first != second
    assert first.name == "apostila-de-fisica"
    assert second.name.endswith("-2")
    assert (first / crop).is_file()
    assert (first / "original.pdf").read_bytes() == source.read_bytes()
    assert "Correcao manual" in next(first.glob("*.md")).read_text()
    report = json.loads((first / "conversao.json").read_text())
    assert report["source_sha256"] == result.source_hash
    assert str(source) not in (first / "conversao.json").read_text()
    assert not list((vault / "Importados").glob(".pdf-obsidian-*"))


def test_invalid_encrypted_and_no_text(tmp_path):
    invalid = tmp_path / "invalid.pdf"
    invalid.write_text("not a pdf")
    with pytest.raises(PDFError):
        convert(invalid, tmp_path / "invalid-work")
    doc = pymupdf.open()
    doc.new_page()
    protected = tmp_path / "protected.pdf"
    doc.save(protected, encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw="owner", user_pw="secret")
    with pytest.raises(PDFError, match="senha"):
        convert(protected, tmp_path / "protected-work")
    blank = tmp_path / "blank.pdf"
    doc.save(blank)
    doc.close()
    result = convert(blank, tmp_path / "blank-work")
    assert any("Sem texto" in w.message for w in result.warnings)


def test_cancel_and_source_change(source, tmp_path):
    with pytest.raises(ConversionCancelled):
        convert(source, tmp_path / "cancel-work", cancelled=lambda: True)
    result = convert(source, tmp_path / "work")
    source.write_bytes(source.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="mudou"):
        export_document(result, tmp_path)


def test_export_cleanup_on_failure(source, tmp_path, monkeypatch):
    result = convert(source, tmp_path / "work")
    import pdf_obsidian.exporter as module
    original_copy = module.shutil.copyfile
    def fail(src, dst, **kwargs):
        if Path(src) == source:
            raise PermissionError("Sem permissao")
        return original_copy(src, dst, **kwargs)
    monkeypatch.setattr(module.shutil, "copyfile", fail)
    with pytest.raises(PermissionError):
        export_document(result, tmp_path)
    assert list((tmp_path / "Importados").iterdir()) == []


def test_render_and_invalid_crop(source, tmp_path):
    rect = render(source, 1, tmp_path / "page.png", dpi=100)
    assert rect[2] > 0
    with pytest.raises(PDFError):
        make_crop(source, tmp_path, 1, (0, 0, 0, 0))


def test_lists_and_markdown_escaping(tmp_path):
    source = tmp_path / "lista.pdf"
    with pymupdf.open() as doc:
        page = doc.new_page()
        page.insert_text((50, 100), "- Item um\n- Item dois\n1) Primeiro\n2) Segundo", fontsize=12)
        page.insert_text((50, 250), "Texto com *asterisco* e [referencia].", fontsize=12)
        doc.save(source)
    result = convert(source, tmp_path / "work")
    assert "- Item um\n- Item dois" in result.markdown
    assert "1. Primeiro\n2. Segundo" in result.markdown
    assert r"\*asterisco\*" in result.markdown
    assert r"\[referencia\]" in result.markdown


def test_table_as_image(tmp_path):
    source = tmp_path / "table.pdf"
    with pymupdf.open() as doc:
        page = doc.new_page()
        for x in (50, 150, 250):
            page.draw_line((x, 100), (x, 190))
        for y in (100, 130, 160, 190):
            page.draw_line((50, y), (250, y))
        for row in range(3):
            page.insert_text((60, 120 + row * 30), f"Celula {row}")
            page.insert_text((160, 120 + row * 30), f"Valor {row}")
        doc.save(source)
    result = convert(source, tmp_path / "work")
    assert any("Tabela preservada" in warning.message for warning in result.warnings)
    assert "![Tabela" in result.markdown
    assert "<table>" in result.markdown
    assert result.markdown.count("Celula 0") == 1
    assert any(asset.role == "table" and asset.origin == "detected" for asset in result.assets)


def test_numbered_chapters_are_not_discarded_as_running_headers(tmp_path):
    source = tmp_path / "chapters.pdf"
    with pymupdf.open() as doc:
        for number in range(1, 4):
            page = doc.new_page()
            page.insert_text((50, 40), f"Capitulo {number}", fontsize=20)
            page.insert_text((50, 140), "Conteudo da aula para estudo.", fontsize=12)
            page.insert_text((50, 820), str(number), fontsize=9)
        doc.save(source)
    result = convert(source, tmp_path / "work")
    for number in range(1, 4):
        assert f"## Capitulo {number}" in result.markdown
    assert len(result.decisions) == 3


def test_detected_formula_is_preserved_as_crop(tmp_path):
    source = tmp_path / "formula.pdf"
    with pymupdf.open() as doc:
        page = doc.new_page()
        font = pymupdf.Font("symb")
        page.insert_font(fontname="math", fontbuffer=font.buffer)
        page.insert_text((50, 100), "∑ ∫ √", fontname="math", fontsize=20)
        page.insert_text((50, 160), "Explicacao da formula.", fontsize=12)
        doc.save(source)
    result = convert(source, tmp_path / "work")
    assert "![Fórmula" in result.markdown
    assert any(asset.role == "formula" and asset.origin == "detected" for asset in result.assets)
    assert any("fórmula preservada" in w.message for w in result.warnings)
    assert "Explicacao da formula" in result.markdown
    assert len(list((result.workspace / "assets").glob("*.png"))) == 1
