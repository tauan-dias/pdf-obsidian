import json

import pytest

from pdf_obsidian.cleanup import apply_cleanup, build_manual_cleanup_plan
from pdf_obsidian.converter import convert
from pdf_obsidian.exporter import export_document


@pytest.fixture
def result(manual_source, tmp_path):
    return convert(manual_source, tmp_path / "work")


def test_manual_removal_without_any_suggestions(result):
    images = [asset for asset in result.assets if asset.page == 1]
    assert {asset.origin for asset in images} == {"raster", "vector"}
    markdown = "💡 Minha nota pessoal.\n\n" + result.markdown
    plan = build_manual_cleanup_plan(result, markdown, [(asset.path, 0) for asset in images])
    assert len(plan.removals) == 2
    cleaned = apply_cleanup(markdown, plan)
    assert cleaned.startswith("💡 Minha nota pessoal.")
    assert "Legenda que deve permanecer intacta." in cleaned
    assert "<!-- Página 1 -->" in cleaned
    assert all(asset.generated_markdown not in cleaned for asset in images)
    assert all(asset.generated_markdown in cleaned for asset in result.assets if asset.page == 2)
    assert all((result.workspace / asset.path).is_file() for asset in result.assets)


def test_manual_removal_accepts_changed_alt_and_only_selected_duplicate(result, tmp_path):
    asset = result.assets[0]
    embedding = asset.generated_markdown.replace("Figura", "Imagem de decoração")
    markdown = result.markdown.replace(asset.generated_markdown, embedding + "\n\n" + embedding)
    plan = build_manual_cleanup_plan(result, markdown, [(asset.path, 1)])
    assert plan.removals[0].occurrences_before == 2
    assert plan.removals[0].original_markdown == embedding
    cleaned = apply_cleanup(markdown, plan)
    assert cleaned.count(embedding) == 1
    exported = export_document(result, tmp_path, cleaned, cleanup_removals=plan.removals)
    assert (exported / asset.path).exists()
    report = json.loads((exported / "conversao.json").read_text())
    assert report["cleanup"]["image_removals"][0]["removed_occurrences"] == 1
    assert report["cleanup"]["image_removals"][0]["file_exported"]
    restored = export_document(result, tmp_path, markdown, cleanup_removals=plan.removals)
    assert not json.loads((restored / "conversao.json").read_text())["cleanup"]["image_removals"]


def test_manual_source_mapping_excludes_code_and_preserves_inline_text(result):
    asset = result.assets[0]
    inline = f"Explicação com ![Imagem]({asset.path}) no parágrafo."
    markdown = f"```md\n{asset.generated_markdown}\n```\n\n{inline}\n\n" + result.markdown
    with pytest.raises(ValueError, match="isolada"):
        build_manual_cleanup_plan(result, markdown, [(asset.path, 0)])
    plan = build_manual_cleanup_plan(result, markdown, [(asset.path, 1)])
    cleaned = apply_cleanup(markdown, plan)
    assert inline in cleaned
    assert f"```md\n{asset.generated_markdown}\n```" in cleaned
    assert cleaned.count(asset.generated_markdown) == 1
    with pytest.raises(ValueError, match="mudou"):
        apply_cleanup(markdown + "Nova nota.", plan)


def test_repeated_manual_applications_report_all_removed_occurrences(result, tmp_path):
    asset = result.assets[0]
    markdown = result.markdown.replace(asset.generated_markdown, asset.generated_markdown + "\n\n" + asset.generated_markdown)
    first = build_manual_cleanup_plan(result, markdown, [(asset.path, 1)])
    once = apply_cleanup(markdown, first)
    second = build_manual_cleanup_plan(result, once, [(asset.path, 0)])
    cleaned = apply_cleanup(once, second)
    actions = first.removals + second.removals
    exported = export_document(result, tmp_path, cleaned, cleanup_removals=actions)
    report = json.loads((exported / "conversao.json").read_text())
    assert report["cleanup"]["image_removals"][0]["removed_occurrences"] == 2
    assert not (exported / asset.path).exists()
    undone = export_document(result, tmp_path, once, cleanup_removals=actions)
    report = json.loads((undone / "conversao.json").read_text())
    assert report["cleanup"]["image_removals"][0]["removed_occurrences"] == 1
    assert (undone / asset.path).exists()
