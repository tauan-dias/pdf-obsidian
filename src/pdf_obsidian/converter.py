from collections import Counter
from contextlib import ExitStack
from hashlib import sha256
from pathlib import Path
import re
import unicodedata

from .models import AssetInfo, Block, Page, Warning, ConversionResult, FilteredImage
from .layout import extract_text_block, reconstruct_page, word_inventory
from .pdf import open_pdf, render
from .security import check_raster
from .recognition import ConversionOptions, RecognitionClient, resource_status, resource_directory
from .recognition_merge import merge_recognition
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


def raster_has_detail(page, rect):
    """Skip recognition of uniformly colored images, never remove their assets.

    A tiny visual probe avoids loading OCR for flat placeholders/ornaments on
    otherwise digital documents. It is not a classifier or an image filter.
    """
    import pymupdf
    scale = min(1., 128 / max(1., rect.width, rect.height))
    pixmap = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), clip=rect, alpha=False)
    samples = pixmap.samples
    if len(samples) < 3:
        return False
    return any(max(samples[channel::3]) - min(samples[channel::3]) >= 8 for channel in range(3))


def convert(source: Path, workspace: Path, progress=None, cancelled=None, *, options=None, stage=None):
    options = options or ConversionOptions()
    if not isinstance(options, ConversionOptions):
        raise TypeError("Opções de conversão inválidas.")
    source, workspace = Path(source).resolve(), Path(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "assets").mkdir(exist_ok=True)
    pages, warnings, decisions, assets = [], [], [], []
    sizes = Counter()
    page_regions, filtered_images = [], []
    recognition = dict(mode=options.ocr_mode, languages=['pt', 'en'], device='cpu',
                       image_policy='preserve', versions={}, pages=[], peak_bytes=0)
    client = None
    ocr_root = resource_directory()


    def check():
        if cancelled and cancelled():
            raise ConversionCancelled()

    check()
    initial_hash = file_hash(source)
    with ExitStack() as stack:
        doc = stack.enter_context(open_pdf(source))
        title = source.stem
        outline = {item[1].strip().casefold(): item[0] for item in doc.get_toc() if item[1].strip()}
        for index, pdf_page in enumerate(doc):
            check()
            number = index + 1
            page = Page(number, pdf_page.rect.width, pdf_page.rect.height)
            # TEXT evita carregar bytes de todas as imagens no resultado de extração.
            import pymupdf
            from .pdf import displayed_text
            data = displayed_text(pdf_page, pdf_page.get_text("dict", flags=pymupdf.TEXTFLAGS_TEXT, sort=True))
            for source_block, raw in enumerate(deduplicate_text_blocks(data["blocks"], number, decisions)):
                if raw.get("type") != 0:
                    continue
                block = extract_text_block(raw, number, source_block, sizes)
                if block:
                    page.blocks.append(block)
            if not page.blocks:
                warnings.append(Warning(number, "Sem texto extraível nesta página; confira a imagem ou utilize um recorte."))

            regions = []
            for block in page.blocks:
                if any(symbol in block.text for symbol in "∫∑√≈≠∞"):
                    regions.append((block.bbox, "formula", None))
                    warnings.append(Warning(number, "Possível fórmula preservada como imagem; confira o recorte."))
            # Tabelas reconhecidas são rasterizadas; não transcrever sua geometria como parágrafos.
            try:
                from .pdf import displayed_tables
                for bbox in displayed_tables(pdf_page):
                    regions.append((bbox, "table", None))
            except Exception:
                warnings.append(Warning(number, "Não foi possível analisar tabelas nesta página."))
            for info in pdf_page.get_image_info(hashes=True):
                regions.append((tuple(pymupdf.Rect(info["bbox"]) * pdf_page.rotation_matrix), "image", info["digest"].hex()))
            # Desenhos vetoriais próximos são agrupados pela própria biblioteca.
            try:
                drawings = pdf_page.get_drawings()
                regions.extend((tuple(rect * pdf_page.rotation_matrix), "figure", vector_signature(rect, drawings)
                                if margin_zone(rect * pdf_page.rotation_matrix, page.height) else None)
                               for rect in pdf_page.cluster_drawings(drawings=drawings))
            except Exception:
                warnings.append(Warning(number, "Revise figuras vetoriais nesta página."))
            accepted = []
            for bbox, kind, digest in regions:
                check()
                rect = pymupdf.Rect(bbox) & pdf_page.rect
                if rect.is_empty or rect.is_infinite:
                    continue
                if any((rect & old).get_area() >= rect.get_area() * .85 for old, _, _ in accepted):
                    continue
                accepted.append((rect, kind, digest))
            pages.append(page)
            page_regions.append(accepted)
            if progress:
                progress(number, len(doc) * 2)

        filtered = recurring_margins(pages, page_regions, check=check)
        for page, accepted in zip(pages, page_regions):
            check()
            number = page.number
            pdf_page = doc[number - 1]
            native_blocks = list(page.blocks)
            # Only raster/structured regions not excluded by the authorized margin
            # filter are candidates. Pure native pages never load OCR models.
            from .native_tables import extract as extract_native_tables
            try:
                native_tables = (extract_native_tables(pdf_page, page.blocks)
                                 if any(kind == "table" for _, kind, _ in accepted) else {})
            except Exception:
                native_tables = {}
            candidates = [tuple(rect) for i, (rect, kind, _digest) in enumerate(accepted)
                          if (number, i) not in filtered and tuple(rect) not in native_tables and (kind in ('table', 'formula')
                              or kind == 'image' and raster_has_detail(pdf_page, rect))]
            attempt = options.ocr_mode == 'auto' and bool(candidates)
            # Uma imagem de fundo pode ter camada de texto: evitar duplicar a página inteira.
            for region_index, (rect, kind, digest) in enumerate(accepted):
                check()
                omission = filtered.get((number, region_index))
                covered = [b for b in page.blocks if
                           (pymupdf.Rect(b.bbox) & rect).get_area() >= pymupdf.Rect(b.bbox).get_area() * .8]
                if kind == "image" and rect.get_area() > pdf_page.rect.get_area() * .8 and covered and not attempt:
                    warnings.append(Warning(number, "Imagem de fundo com camada de texto; revise a página e faça recortes se necessário."))
                    continue
                if kind != "image" and not omission:
                    for block in covered:
                        page.blocks.remove(block)
                name = f"p{number:04d}-fig{region_index + 1:03d}.png"
                asset = f"assets/{name}"
                check_raster(rect.width, rect.height, 150 / 72)
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
                if kind == "table" and tuple(rect) in native_tables:
                    page.blocks.append(Block("recognized_table", native_tables[tuple(rect)], number, tuple(rect), role="recognized"))
                    decisions.append(f"Página {number}: tabela nativa extraída, com recorte preservado.")
                if kind == "table":
                    warnings.append(Warning(number, "Tabela preservada como imagem; confira os limites do recorte."))
            if attempt:
                check()
                available, reason, manifest = resource_status(ocr_root)
                record = dict(page=number, status='unavailable', added_blocks=0, duration_seconds=0,
                              regions=[list(box) for box in candidates])
                if available:
                    recognition['versions'] = manifest.get('versions', {})
                    recognition['sources'] = manifest.get('sources', [])
                    if stage:
                        stage(f'Página {number} de {len(doc)} · reconhecendo texto, tabelas e fórmulas…')
                    try:
                        if client is None:
                            client = RecognitionClient(ocr_root, workspace)
                            stack.callback(client.close)
                        directory = workspace / 'ocr'
                        directory.mkdir(exist_ok=True)
                        image_path = directory / f'page-{number:04d}.png'
                        # Limit page raster size, preserving geometry by returning
                        # page-point coordinates from the isolated image pipeline.
                        dpi = min(216, 72 * (12_000_000 / max(1, page.width * page.height)) ** .5)
                        check_raster(page.width, page.height, dpi / 72)
                        pdf_page.get_pixmap(matrix=pymupdf.Matrix(dpi / 72, dpi / 72), alpha=False).save(image_path)
                        recognized, elapsed = client.recognize(image_path, number, page.width, page.height, check,
                            formula_regions=[tuple(rect) for rect, kind, _ in accepted if kind == 'formula'])
                        count = merge_recognition(page, recognized, native_blocks, candidates, decisions, warnings)
                        record.update(status='recognized' if count else 'no_additions', added_blocks=count,
                                      duration_seconds=round(elapsed, 3))
                        recognition['peak_bytes'] = max(recognition['peak_bytes'], client.peak_bytes)
                        if count:
                            warnings[:] = [warning for warning in warnings if not (
                                warning.page == number and warning.message.startswith('Sem texto extraível'))]
                    except ConversionCancelled:
                        raise
                    except Exception as exc:
                        record.update(status='failed', error=str(exc)[:2000])
                        warnings.append(Warning(number, 'Falha no OCR; extração direta e imagens preservadas. ' + str(exc)[:500]))
                        if client:
                            client.close()
                    finally:
                        if client:
                            recognition['peak_bytes'] = max(recognition['peak_bytes'], client.peak_bytes)
                        if stage:
                            stage(f'Página {number} de {len(doc)} · finalizando extração…')
                else:
                    warnings.append(Warning(number, reason + ' Extração direta e imagens preservadas.'))
                recognition['pages'].append(record)
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
    from .reading_order import regions
    for page in pages:
        groups = regions(page.blocks, page.width)
        if len(groups) > 1:
            page.blocks = [block for group in groups for block in group]
            warnings[:] = [w for w in warnings if not (
                w.page == page.number and w.message == "Possíveis colunas: revise a ordem de leitura.")]
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
    warnings.sort(key=lambda warning: warning.page)
    warnings.insert(0, Warning(0, "Conversão heurística: revise títulos, ordem, tabelas e fórmulas antes de exportar."))
    return ConversionResult(source, initial_hash, title, "\n\n".join(output) + "\n", workspace, pages, warnings, decisions, assets, filtered_images, recognition)


def make_crop(source, workspace, page, bbox):
    from uuid import uuid4
    asset = f"assets/p{page:04d}-recorte-{uuid4().hex[:10]}.png"
    render(Path(source), page, Path(workspace) / asset, bbox)
    return asset
