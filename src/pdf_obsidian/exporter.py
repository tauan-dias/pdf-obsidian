import json
import os
from pathlib import Path
import shutil
import tempfile
from contextlib import contextmanager
from dataclasses import asdict
from hashlib import sha256

from . import __version__
from .converter import file_hash, slug
from .markdown import analyse_markdown, strip_page_comments


def export_parent(vault):
    """Validar o destino inclusive antes de reutilizar uma publicação."""
    vault = Path(vault).resolve()
    if not vault.is_dir():
        raise ValueError("Escolha uma pasta de vault existente.")
    parent = vault / "Importados"
    if not parent.resolve().is_relative_to(vault):
        raise ValueError("A pasta Importados aponta para fora do vault selecionado.")
    return parent


@contextmanager
def publication_parent(vault):
    """Manter staging/rename/limpeza ancorados ao diretório aberto no Linux."""
    public = export_parent(vault)
    public.mkdir(exist_ok=True)
    physical = public.resolve()
    if not physical.is_relative_to(Path(vault).resolve()):
        raise ValueError("A pasta Importados aponta para fora do vault selecionado.")
    descriptor = os.open(physical, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        yield public, Path(f"/proc/self/fd/{descriptor}")
    finally:
        os.close(descriptor)


def export_manifest(target):
    """Manifesto em memória; nunca seguir links de uma publicação."""
    target = Path(target)
    if target.is_symlink() or not target.is_dir():
        return {}
    manifest = {}
    for path in target.rglob('*'):
        if path.is_symlink():
            return {}
        if path.is_file():
            manifest[path.relative_to(target).as_posix()] = (path.stat().st_size, file_hash(path))
    return manifest


def export_intact(record, vault=None):
    if not record or not record.manifest:
        return False
    target = Path(record.target)
    if vault is not None:
        parent = export_parent(vault)
        if target.parent.resolve() != parent.resolve():
            return False
    try:
        if target.is_symlink() or not target.is_dir():
            return False
        for name, expected in record.manifest.items():
            relative = Path(name)
            if relative.is_absolute() or '..' in relative.parts:
                return False
            path = target
            for part in relative.parts:
                path = path / part
                if path.is_symlink():
                    return False
            if not path.is_file() or (path.stat().st_size, file_hash(path)) != expected:
                return False
        return True
    except OSError:
        return False


def _prepare_export(result, markdown=None, *, strip_page_markers=False, cleanup_removals=()):
    final_markdown = result.markdown if markdown is None else markdown
    markers_removed = 0
    if strip_page_markers:
        final_markdown, markers_removed = strip_page_comments(final_markdown, len(result.pages))
    assets = result.workspace / "assets"
    if assets.is_symlink():
        raise ValueError("A pasta de anexos temporários foi substituída por um link simbólico. Converta novamente.")
    available = {}
    for path in assets.rglob("*"):
        if path.is_symlink():
            raise ValueError("Anexo temporário contém link simbólico: " + path.relative_to(result.workspace).as_posix())
        if path.is_file():
            available[path.relative_to(result.workspace).as_posix()] = path
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
    if result.recognition is not None:
        report["recognition"] = result.recognition
    return final_markdown, available, selected_assets, report


def export_signature(result, markdown=None, *, strip_page_markers=False, cleanup_removals=()):
    """Estado exportável compartilhado; anexos gerados são imutáveis na sessão."""
    final, _, _, report = _prepare_export(result, markdown, strip_page_markers=strip_page_markers,
                                        cleanup_removals=cleanup_removals)
    payload = json.dumps([final, report], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(payload.encode('utf-8')).hexdigest()


def export_document(result, vault, markdown=None, *, strip_page_markers=False, cleanup_removals=(), manifest=None):
    vault = Path(vault).resolve()
    if not vault.is_dir():
        raise ValueError("Escolha uma pasta de vault existente.")
    if file_hash(result.source) != result.source_hash:
        raise ValueError("O PDF original mudou desde a conversão. Converta novamente.")
    final_markdown, available, selected_assets, report = _prepare_export(
        result, markdown, strip_page_markers=strip_page_markers, cleanup_removals=cleanup_removals)
    with publication_parent(vault) as (public, parent):
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
            # Capturar antes do rename: leitores externos só devem observar a
            # publicação depois de conhecermos todos os arquivos esperados.
            captured = export_manifest(staging) if manifest is not None else None
            index = 1
            while True:
                # Uma troca do caminho durante a cópia não pode redirecionar a
                # publicação nem fazer a limpeza alcançar outra pasta.
                export_parent(vault)
                opened, current = os.stat(parent), os.stat(public)
                if (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino):
                    raise ValueError("A pasta de destino mudou durante a publicação. Tente novamente.")
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
                    if manifest is not None:
                        manifest.clear()
                        manifest.update(captured)
                    return public / target.name
                import errno
                error = ctypes.get_errno()
                if error == errno.EEXIST:
                    index += 1
                    continue
                raise OSError(error, os.strerror(error), str(target))
        finally:
            if staging.exists():
                shutil.rmtree(staging)
