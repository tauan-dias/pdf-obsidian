"""Remoções manuais revisáveis, independentes da interface e da extração."""
from dataclasses import dataclass
from hashlib import sha256

from .markdown import PAGE_COMMENT, analyse_markdown
from .models import ConversionResult


@dataclass(frozen=True)
class CleanupRemoval:
    asset: str
    page: int
    start: int
    end: int
    original_markdown: str
    group: str
    reason: str
    occurrences_before: int = 1


@dataclass(frozen=True)
class CleanupPlan:
    source_hash: str
    removals: tuple[CleanupRemoval, ...]
    skipped: tuple[str, ...]


def text_hash(markdown):
    return sha256(markdown.encode("utf-8")).hexdigest()


def apply_cleanup(markdown: str, plan: CleanupPlan):
    if text_hash(markdown) != plan.source_hash:
        raise ValueError("O Markdown mudou desde a análise. Atualize a prévia e selecione as imagens novamente.")
    for removal in reversed(plan.removals):
        markdown = markdown[:removal.start] + markdown[removal.end:]
    return markdown


def build_manual_cleanup_plan(result: ConversionResult, markdown: str, selected_images):
    """Remover as ocorrências escolhidas, sem exigir classificação automática."""
    analysis = analyse_markdown(markdown, (asset.path for asset in result.assets))
    occurrences = {(image.asset, image.occurrence): image for image in analysis.image_occurrences}
    metadata = {asset.path: asset for asset in result.assets}
    markers = []
    offset = 0
    for line_number, line in enumerate(markdown.splitlines(keepends=True)):
        match = PAGE_COMMENT.fullmatch(line.rstrip("\r\n"))
        if (match and line_number not in analysis.protected_lines
                and int(match[1]) <= len(result.pages)):
            markers.append((offset, int(match[1])))
        offset += len(line)
    removals = []
    for key in sorted(set(selected_images)):
        image = occurrences.get(key)
        if image is None or image.paragraph is None:
            raise ValueError("A imagem selecionada mudou ou não possui uma incorporação isolada. Atualize a prévia e selecione novamente.")
        paragraph = image.paragraph
        asset = metadata.get(image.asset)
        page = asset.page if asset else 0
        preceding = [marker for marker in markers if marker[0] < paragraph.start]
        if preceding:
            page = preceding[-1][1]
        count = sum(item.asset == image.asset and item.text == paragraph.text for item in analysis.images)
        removals.append(CleanupRemoval(
            image.asset, page, paragraph.start, paragraph.end, paragraph.text,
            f"manual:{image.asset}", "Imagem selecionada manualmente na prévia pelo usuário.", count,
        ))
    return CleanupPlan(text_hash(markdown), tuple(sorted(removals, key=lambda item: item.start)), ())
