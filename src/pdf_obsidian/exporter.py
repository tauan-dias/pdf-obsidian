import json
import os
from pathlib import Path
import shutil
import tempfile
from dataclasses import asdict
from hashlib import sha256

from . import __version__
from .converter import file_hash, slug
from .markdown import analyse_markdown, strip_page_comments


def _prepare_export(result, markdown=None, *, strip_page_markers=False, cleanup_removals=()):
    final_markdown = result.markdown if markdown is None else markdown
    markers_removed = 0
    if strip_page_markers:
        final_markdown, markers_removed = strip_page_comments(final_markdown, len(result.pages))
    available = {path.relative_to(result.workspace).as_posix(): path
                 for path in (result.workspace / "assets").rglob("*") if path.is_file()}
    analysis = analyse_markdown(final_markdown, available)
    missing = analysis.references - available.keys()
    if missing:
        raise ValueError("Anexos referenciados não encontrados: " + ", ".join(sorted(missing)))
    selected_assets = set(available) if analysis.uncertainty else analysis.references
    # O estado atual prevalece: desfazer/refs compartilhadas não devem ser
    # apresentados como exclusão definitiva do arquivo.
    actions = {}
    for removal in cleanup_removals:
        key = (removal.asset, removal.original_markdown)
        previous = actions.get(key)
        if previous is None or removal.occurrences_before >= previous.occurrences_before:
            actions[key] = removal
    active_removals = []
    for (asset, _), removal in actions.items():
        remaining = sum(image.asset == asset and image.text == removal.original_markdown for image in analysis.images)
        count = max(0, removal.occurrences_before - remaining)
        if not count:
            continue
        active_removals.append({"asset": asset, "page": removal.page,
                                "group": removal.group, "reason": removal.reason,
                                "removed_occurrences": count,
                                "file_exported": asset in selected_assets})
    report = {"converter_version": __version__, "source_sha256": result.source_hash,
              "page_count": len(result.pages),
              "warnings": [{"page": w.page, "message": w.message} for w in result.warnings],
              "decisions": result.decisions,
              "assets": [asdict(asset) for asset in result.assets],
              "filtered_images": [{**asdict(item),
                  "incorporated": any(image.asset == item.asset for image in analysis.image_occurrences),
                  "referenced": item.asset in analysis.references,
                  "file_exported": item.asset in selected_assets}
                  for item in result.filtered_images],
              "cleanup": {"strip_page_markers": strip_page_markers,
                          "removed_page_markers": markers_removed,
                          "image_removals": active_removals,
                          "omitted_assets": sorted(available.keys() - selected_assets),
                          "reference_warnings": analysis.uncertainty}}
    return final_markdown, available, selected_assets, report


def export_signature(result, markdown=None, *, strip_page_markers=False, cleanup_removals=()):
    """Estado exportável compartilhado; anexos gerados são imutáveis na sessão."""
    final, _, _, report = _prepare_export(result, markdown, strip_page_markers=strip_page_markers,
                                        cleanup_removals=cleanup_removals)
    payload = json.dumps([final, report], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(payload.encode('utf-8')).hexdigest()


def export_document(result, vault, markdown=None, *, strip_page_markers=False, cleanup_removals=()):
    vault = Path(vault).resolve()
    if not vault.is_dir():
        raise ValueError("Escolha uma pasta de vault existente.")
    if file_hash(result.source) != result.source_hash:
        raise ValueError("O PDF original mudou desde a conversão. Converta novamente.")
    final_markdown, available, selected_assets, report = _prepare_export(
        result, markdown, strip_page_markers=strip_page_markers, cleanup_removals=cleanup_removals)
    parent = vault / "Importados"
    parent.mkdir(exist_ok=True)
    base = slug(result.title)
    staging = Path(tempfile.mkdtemp(prefix=".pdf-obsidian-", dir=parent))
    try:
        (staging / "assets").mkdir()
        for asset in sorted(selected_assets):
            destination = staging / asset
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(available[asset], destination)
        shutil.copyfile(result.source, staging / "original.pdf")
        if file_hash(staging / "original.pdf") != result.source_hash:
            raise ValueError("O PDF foi alterado durante a exportação.")
        (staging / f"{base}.md").write_text(final_markdown, encoding="utf-8")
        (staging / "conversao.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        index = 1
        while True:
            target = parent / (base if index == 1 else f"{base}-{index}")
            if target.exists():
                index += 1
                continue
            # Linux renameat2(RENAME_NOREPLACE) evita sobrescrita mesmo entre instâncias concorrentes.
            import ctypes
            libc = ctypes.CDLL(None, use_errno=True)
            renameat2 = libc.renameat2
            renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
            renameat2.restype = ctypes.c_int
            if renameat2(-100, os.fsencode(staging), -100, os.fsencode(target), 1) == 0:
                return target
            import errno
            error = ctypes.get_errno()
            if error == errno.EEXIST:
                index += 1
                continue
            raise OSError(error, os.strerror(error), str(target))
    finally:
        if staging.exists():
            shutil.rmtree(staging)
