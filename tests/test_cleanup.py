import json

import pytest

from pdf_obsidian.cleanup import apply_cleanup, build_manual_cleanup_plan
from pdf_obsidian.converter import convert
from pdf_obsidian.exporter import export_document
from pdf_obsidian.markdown import analyse_markdown
from pdf_obsidian.filtered_images import restoration_edit


@pytest.fixture
def result(decorative_source, tmp_path):
    result = convert(decorative_source, tmp_path / "work")
    # Exercitar a exclusão manual também para figuras recuperadas do filtro.
    for item in result.filtered_images:
        position, insertion = restoration_edit(result, result.markdown, item)
        result.markdown = result.markdown[:position] + insertion + result.markdown[position:]
    return result


def test_export_cleans_copy_and_omits_only_unused_assets(result, tmp_path):
    chosen = [asset for asset in result.assets if asset.origin == "raster" and asset.bbox[3] <= asset.page_size[1] * .1][:5]
    plan = build_manual_cleanup_plan(result, result.markdown, [(asset.path, 0) for asset in chosen])
    cleaned = apply_cleanup(result.markdown, plan)
    # Um link comum ainda depende de um dos arquivos removidos da incorporação.
    shared = chosen[0].path
    cleaned += f"\n[Consultar imagem]({shared})\n"
    exported = export_document(result, tmp_path, cleaned, strip_page_markers=True,
                               cleanup_removals=plan.removals)
    markdown = next(exported.glob("*.md")).read_text()
    assert "<!-- Página" not in markdown
    assert "<!-- Página" in result.markdown
    assert (exported / shared).exists()
    for asset in chosen[1:]:
        assert not (exported / asset.path).exists()
        assert (result.workspace / asset.path).exists()
    assert (exported / "original.pdf").read_bytes() == result.source.read_bytes()
    analysis = analyse_markdown(markdown)
    assert all((exported / path).exists() for path in analysis.references)
    report = json.loads((exported / "conversao.json").read_text())
    assert report["cleanup"]["removed_page_markers"] == 5
    assert len(report["cleanup"]["image_removals"]) == 5
    assert len(report["cleanup"]["omitted_assets"]) == 4
    assert any(action["file_exported"] for action in report["cleanup"]["image_removals"])
    restored = export_document(result, tmp_path, result.markdown, cleanup_removals=plan.removals)
    restored_report = json.loads((restored / "conversao.json").read_text())
    assert not restored_report["cleanup"]["image_removals"]
    assert not restored_report["cleanup"]["omitted_assets"]


def test_export_ignores_code_examples_and_respects_uncertainty(result, tmp_path):
    asset = result.assets[0].path
    for markdown, preserve in ((f"```md\n![Exemplo]({asset})\n```", False),
                               (f'<img src="{asset}">', True),
                               (f"---\ncover: {asset}\n---\nTexto.", True),
                               (f"![Exemplo]({asset}", True)):
        exported = export_document(result, tmp_path, markdown)
        assert bool(list((exported / "assets").glob("*.png"))) is preserve
    with pytest.raises(ValueError, match="não encontrados"):
        export_document(result, tmp_path, "![Faltando](assets/missing.png)")
