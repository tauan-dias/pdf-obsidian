from collections import Counter
from hashlib import sha256
from pathlib import Path
import re
import unicodedata

from .models import AssetInfo, Block, Page, Warning, ConversionResult, FilteredImage
from .layout import extract_text_block, reconstruct_page, word_inventory
from .pdf import open_pdf, render
from .footers import remove_recurring_footers
from .questions import prepare_questions, serialize_blocks, QuestionRendering
from .conversion_filters import deduplicate_text_blocks, margin_zone, recurring_margins, vector_signature


class ConversionCancelled(Exception):
    pass


def file_hash(path):
    digest = sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def slug(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:80] or "documento"


def escape(text):
    return re.sub(r"([\\`*_{}\[\]<>#|])", r"\\\1", text)


def repeated_key(block, page):
    x0, y0, x1, y1 = block.bbox
    zone = "topo" if y1 <= page.height * .10 else "rodape" if y0 >= page.height * .90 else None
    if zone is None or block.kind != "text":
        return None
    text = block.text.casefold().strip()
    # Normalizar apenas paginação, nunca títulos como "Capítulo 1", "Capítulo 2".
    if re.fullmatch(r"(?:(?:p[aá]gina|page|p\.)\s*)?\d+(?:\s*(?:/|de|of)\s*\d+)?", text):
        text = "#pagina"
    return zone, text


def convert(source: Path, workspace: Path, progress=None, cancelled=None):
    source, workspace = Path(source).resolve(), Path(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "assets").mkdir(exist_ok=True)
    pages, warnings, decisions, assets = [], [], [], []
    sizes = Counter()
    page_regions, filtered_images = [], []

    def check():
        if cancelled and cancelled():
            raise ConversionCancelled()

    check()
    initial_hash = file_hash(source)
    with open_pdf(source) as doc:
        title = source.stem
        outline = {item[1].strip().casefold(): item[0] for item in doc.get_toc() if item[1].strip()}
        for index, pdf_page in enumerate(doc):
            check()
            number = index + 1
            page = Page(number, pdf_page.rect.width, pdf_page.rect.height)
            # TEXT evita carregar bytes de todas as imagens no resultado de extração.
            import pymupdf
            data = pdf_page.get_text("dict", flags=pymupdf.TEXTFLAGS_TEXT, sort=True)
            for source_block, raw in enumerate(deduplicate_text_blocks(data["blocks"], number, decisions)):
                if raw.get("type") != 0:
                    continue
                block = extract_text_block(raw, number, source_block, sizes)
                if block:
                    page.blocks.append(block)
            if not page.blocks:
                warnings.append(Warning(number, "Sem texto extraível; OCR indisponível. Use um recorte da página."))

            regions = []
            for block in page.blocks:
                if any(symbol in block.text for symbol in "∫∑√≈≠∞"):
                    regions.append((block.bbox, "formula", None))
                    warnings.append(Warning(number, "Possível fórmula preservada como imagem; confira o recorte."))
            # Tabelas reconhecidas são rasterizadas; não transcrever sua geometria como parágrafos.
            try:
                for table in pdf_page.find_tables().tables:
                    regions.append((tuple(table.bbox), "table", None))
            except Exception:
                warnings.append(Warning(number, "Não foi possível analisar tabelas nesta página."))
            for info in pdf_page.get_image_info(hashes=True):
                regions.append((tuple(info["bbox"]), "image", info["digest"].hex()))
            # Desenhos vetoriais próximos são agrupados pela própria biblioteca.
            try:
                drawings = pdf_page.get_drawings()
                regions.extend((tuple(rect), "figure", vector_signature(rect, drawings)
                                if margin_zone(rect, page.height) else None)
                               for rect in pdf_page.cluster_drawings(drawings=drawings))
            except Exception:
                warnings.append(Warning(number, "Revise figuras vetoriais nesta página."))
            accepted = []
            for bbox, kind, digest in regions:
                check()
                rect = pymupdf.Rect(bbox) & pdf_page.rect
                if rect.width < 8 or rect.height < 8:
                    continue
                if any((rect & old).get_area() >= rect.get_area() * .85 for old, _, _ in accepted):
                    continue
                accepted.append((rect, kind, digest))
            pages.append(page)
            page_regions.append(accepted)
            if progress:
                progress(number, len(doc) * 2)

        filtered = recurring_margins(pages, page_regions)
        for page, accepted in zip(pages, page_regions):
            check()
            number = page.number
            pdf_page = doc[number - 1]
            # Uma imagem de fundo pode ter camada de texto: evitar duplicar a página inteira.
            for region_index, (rect, kind, digest) in enumerate(accepted):
                check()
                omission = filtered.get((number, region_index))
                covered = [b for b in page.blocks if
                           (pymupdf.Rect(b.bbox) & rect).get_area() >= pymupdf.Rect(b.bbox).get_area() * .8]
                if kind == "image" and rect.get_area() > pdf_page.rect.get_area() * .8 and covered:
                    warnings.append(Warning(number, "Imagem de fundo com camada de texto; revise a página e faça recortes se necessário."))
                    continue
                if kind != "image" and not omission:
                    for block in covered:
                        page.blocks.remove(block)
                name = f"p{number:04d}-fig{region_index + 1:03d}.png"
                asset = f"assets/{name}"
                pdf_page.get_pixmap(dpi=150, clip=rect, alpha=False).save(workspace / asset)
                label = {"table": "Tabela", "formula": "Fórmula"}.get(kind, "Figura")
                if omission:
                    reason, signature = omission
                    filtered_images.append(FilteredImage(asset, number, tuple(rect), reason, signature))
                    decisions.append(f"Página {number}: figura filtrada {asset}: {reason}")
                else:
                    page.blocks.append(Block("image", label, number, tuple(rect), asset=asset))
                assets.append(AssetInfo(
                    asset, {"image": "raster", "figure": "vector"}.get(kind, "detected"),
                    kind if kind in ("table", "formula") else "figure", number,
                    tuple(rect), (page.width, page.height), digest,
                    f"![{label} — página {number}]({asset})",
                ))
                if kind == "table":
                    warnings.append(Warning(number, "Tabela preservada como imagem; confira os limites do recorte."))
            # Evidência simples de colunas; a ordem de leitura do MVP é para uma coluna.
            left = [b for b in page.blocks if b.kind == "text" and b.bbox[2] < page.width * .55]
            right = [b for b in page.blocks if b.kind == "text" and b.bbox[0] > page.width * .45]
            if any(abs(a.bbox[1] - b.bbox[1]) < 20 for a in left for b in right if a is not b):
                warnings.append(Warning(number, "Possíveis colunas: revise a ordem de leitura."))
            page.blocks.sort(key=lambda b: (round(b.bbox[1] / 3), b.bbox[0]))
            if progress:
                progress(len(doc) + number, len(doc) * 2)

    counts = Counter()
    for page in pages:
        counts.update({key for b in page.blocks if (key := repeated_key(b, page)) and key[0] == "topo"})
    repeats = {key for key, count in counts.items() if len(pages) >= 3 and count >= max(3, len(pages) * .7)}
    body = sizes.most_common(1)[0][0] if sizes else 12
    heading_sizes = sorted({line.size for page in pages for block in page.blocks for line in block.lines
                            if line.size >= body * 1.18}, reverse=True)
    for page in pages:
        kept = []
        for block in page.blocks:
            key = repeated_key(block, page)
            if key in repeats:
                decisions.append(f"Página {page.number}: removido {key[0]} repetido: {block.text}")
                continue
            kept.append(block)
        page.blocks = kept
    remove_recurring_footers(pages, decisions, check=check)
    vocabulary = word_inventory(pages)
    prepare_questions(pages, body, heading_sizes, outline, warnings, decisions, check=check)
    output = [f"# {escape(title)}", "[PDF original](original.pdf)"]
    rendering = QuestionRendering()
    for page in pages:
        check()
        page.blocks, changes = reconstruct_page(page, body, heading_sizes, outline, vocabulary)
        decisions.extend(changes)
        output.append(f"<!-- Página {page.number} -->")
        output.extend(serialize_blocks(page.blocks, rendering, escape, warnings))
    check()
    if initial_hash != file_hash(source):
        raise ValueError("O PDF foi alterado durante a conversão. Abra o arquivo novamente.")
    warnings.insert(0, Warning(0, "Conversão heurística: revise títulos, ordem, tabelas e fórmulas antes de exportar."))
    return ConversionResult(source, initial_hash, title, "\n\n".join(output) + "\n", workspace, pages, warnings, decisions, assets, filtered_images)


def make_crop(source, workspace, page, bbox):
    from uuid import uuid4
    asset = f"assets/p{page:04d}-recorte-{uuid4().hex[:10]}.png"
    render(Path(source), page, Path(workspace) / asset, bbox)
    return asset
