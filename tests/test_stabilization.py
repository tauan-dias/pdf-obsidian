"""Regressões de integridade, exclusivamente com documentos sintéticos."""
from pathlib import Path
from queue import Queue
from threading import Event

import pymupdf
import pytest
from PySide6.QtGui import QTextCursor, QTextDocument

from pdf_obsidian.comparison import preview_document, unique_markers
from pdf_obsidian.converter import convert, file_hash, make_crop
from pdf_obsidian.exporter import export_document, export_intact, export_manifest, export_signature
from pdf_obsidian.sessions import DocumentSession, ExportRecord
from pdf_obsidian.worker import run


def synthetic(path, rotation=0, cropped=False, tiny=False):
    with pymupdf.open() as doc:
        page = doc.new_page(width=842, height=595)
        page.insert_text((100, 150), 'Conteudo essencial para preservar.')
        box = pymupdf.Rect(650, 200, 657 if tiny else 790, 220 if tiny else 280)
        pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 80, 40), False)
        pix.set_rect(pix.irect, (255, 0, 0))
        page.insert_image(box, stream=pix.tobytes('png'), keep_proportion=False)
        if cropped:
            page.set_cropbox(pymupdf.Rect(50, 50, 820, 550))
        page.set_rotation(rotation)
        doc.save(path)
    return path


@pytest.mark.parametrize('rotation', (0, 90, 180, 270))
@pytest.mark.parametrize('cropped', (False, True))
def test_display_geometry_preserves_figure_and_crop(tmp_path, rotation, cropped):
    source = synthetic(tmp_path / 'rotacao.pdf', rotation, cropped)
    before = file_hash(source)
    result = convert(source, tmp_path / 'work')
    assert len(result.assets) == 1
    asset = result.assets[0]
    assert 'Conteudo essencial' in result.markdown
    crop = make_crop(source, result.workspace, 1, asset.bbox)
    for relative in (asset.path, crop):
        pix = pymupdf.Pixmap(str(result.workspace / relative))
        samples = pix.samples
        red = sum(samples[i] > 220 and samples[i + 1] < 30 and samples[i + 2] < 30
                  for i in range(0, len(samples), pix.n))
        assert red / (pix.width * pix.height) > .9
    assert file_hash(source) == before


def test_small_body_figure_is_not_discarded(tmp_path):
    result = convert(synthetic(tmp_path / 'pequeno.pdf', tiny=True), tmp_path / 'work')
    assert len(result.assets) == 1
    assert not result.filtered_images
    assert result.assets[0].path in result.markdown


@pytest.mark.parametrize('link_kind', ['file', 'directory', 'root', 'dangling'])
def test_export_rejects_linked_temporary_assets(tmp_path, link_kind):
    result = convert(synthetic(tmp_path / 'documento.pdf'), tmp_path / 'work')
    before = file_hash(result.source)
    external = tmp_path / 'external'
    external.mkdir()
    secret = external / 'private.txt'
    secret.write_text('Conteudo externo que nao deve ser publicado')
    assets = result.workspace / 'assets'
    if link_kind == 'root':
        assets.rename(result.workspace / 'assets-preserved')
        assets.symlink_to(external, target_is_directory=True)
    elif link_kind == 'directory':
        (assets / 'linked').symlink_to(external, target_is_directory=True)
    else:
        asset = result.workspace / result.assets[0].path
        asset.unlink()
        asset.symlink_to(secret if link_kind == 'file' else external / 'missing')
    vault = tmp_path / 'vault'
    vault.mkdir()
    with pytest.raises(ValueError, match='link simbólico'):
        export_document(result, vault)
    assert not list(vault.iterdir())
    assert file_hash(result.source) == before
    assert secret.read_text() == 'Conteudo externo que nao deve ser publicado'


@pytest.mark.parametrize('artifact', ('markdown', 'original.pdf', 'conversao.json', 'asset'))
@pytest.mark.parametrize('change', ('missing', 'modified', 'symlink'))
def test_republication_preserves_divergent_output(tmp_path, artifact, change):
    result = convert(synthetic(tmp_path / 'documento.pdf'), tmp_path / 'work')
    vault = tmp_path / 'vault'
    vault.mkdir()
    target = export_document(result, vault)
    record = ExportRecord(export_signature(result), target, export_manifest(target))
    assert export_intact(record, vault)
    (target / 'anotacao-do-usuario.txt').write_text('Preservar')
    assert export_intact(record, vault)
    path = next(target.glob('*.md')) if artifact == 'markdown' else (
        target / result.assets[0].path if artifact == 'asset' else target / artifact)
    original = path.read_bytes()
    path.unlink()
    if change == 'modified':
        path.write_bytes(b'Edicao externa')
    elif change == 'symlink':
        external = tmp_path / 'externo'
        external.write_bytes(original)
        path.symlink_to(external)
    assert not export_intact(record, vault)
    before = {p.relative_to(target): p.read_bytes() for p in target.rglob('*') if p.is_file()}
    commands, events = Queue(), Queue()
    commands.put(('session_export', 'token', 'session', 1, str(vault), result,
                  result.markdown, False, (), record))
    commands.put(('stop',))
    run(commands, events, Event())
    event = events.get_nowait()
    assert event[4] is True and event[7] is False
    new = Path(event[6])
    assert new != target and new.name.endswith('-2')
    assert (new / 'original.pdf').read_bytes() == result.source.read_bytes()
    assert before == {p.relative_to(target): p.read_bytes() for p in target.rglob('*') if p.is_file()}


def test_external_importados_is_blocked_without_writes(tmp_path):
    result = convert(synthetic(tmp_path / 'documento.pdf'), tmp_path / 'work')
    vault, outside = tmp_path / 'vault', tmp_path / 'outside'
    vault.mkdir(); outside.mkdir()
    (vault / 'Importados').symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match='fora do vault'):
        export_document(result, vault)
    assert not list(outside.iterdir())


def test_internal_importados_link_is_supported(tmp_path):
    result = convert(synthetic(tmp_path / 'documento.pdf'), tmp_path / 'work')
    vault = tmp_path / 'vault'
    vault.mkdir()
    (vault / 'destino').mkdir()
    (vault / 'Importados').symlink_to(vault / 'destino', target_is_directory=True)
    target = export_document(result, vault)
    assert target.resolve().is_relative_to(vault)


@pytest.mark.parametrize('wrapper', ('```\n%s\n```', '    %s', '---\nexample: |\n  %s\n---', '<div>\n%s\n</div>'))
def test_literal_page_comments_remain_in_preview(app, tmp_path, wrapper):
    literal = wrapper % '<!-- Página 1 -->'
    text = literal + '\n\n<!-- Página 1 -->\n\nTexto real.'
    markers = unique_markers(text)
    assert list(markers) == [1]
    assert markers[1].start() > len(literal)
    preview = preview_document(text, tmp_path)
    # Código deve continuar mostrando o comentário; HTML/YAML seguem a semântica Qt.
    if wrapper.startswith(('```', '    ')):
        assert '<!-- Página 1 -->' in preview.toPlainText()


def test_export_option_remains_dirty_after_text_undo(app, tmp_path):
    document = QTextDocument()
    document.setPlainText('Texto')
    session = DocumentSession(None, document)
    session.record_export(tmp_path, 'signature', tmp_path / 'absent', {})
    cursor = QTextCursor(document)
    cursor.insertText('Edicao')
    session.strip_markers = True
    document.undo()
    assert not document.isModified()
    assert session.modified
    session.strip_markers = False
    assert not session.modified


def test_destination_swap_during_copy_cannot_write_outside_or_redirect_cleanup(tmp_path, monkeypatch):
    import pdf_obsidian.exporter as exporter
    result = convert(synthetic(tmp_path / 'documento.pdf'), tmp_path / 'work')
    vault, outside = tmp_path / 'vault', tmp_path / 'outside'
    vault.mkdir()
    outside.mkdir()
    sentinel = outside / 'importante.txt'
    sentinel.write_text('Preservar')
    actual = exporter.shutil.copyfile
    swapped = False
    def swap(*args, **kwargs):
        nonlocal swapped
        if not swapped:
            swapped = True
            (vault / 'Importados').rename(vault / 'anterior')
            (vault / 'Importados').symlink_to(outside, target_is_directory=True)
        return actual(*args, **kwargs)
    monkeypatch.setattr(exporter.shutil, 'copyfile', swap)
    with pytest.raises(ValueError, match='fora do vault'):
        export_document(result, vault)
    assert list(outside.iterdir()) == [sentinel]
    assert sentinel.read_text() == 'Preservar'
    assert not list((vault / 'anterior').iterdir())


def test_margin_grouping_can_be_cancelled():
    from pdf_obsidian.conversion_filters import recurring_margins
    from pdf_obsidian.models import Page
    calls = 0
    def check():
        nonlocal calls
        calls += 1
        if calls == 5:
            raise RuntimeError('Cancelado')
    pages = [Page(i, 595, 842) for i in range(1, 101)]
    regions = [[(pymupdf.Rect(30, 10, 80, 30), 'image', 'same')] for _ in pages]
    with pytest.raises(RuntimeError, match='Cancelado'):
        recurring_margins(pages, regions, check=check)
    assert calls == 5


@pytest.mark.parametrize('rotation', (0, 90, 180, 270))
def test_rotated_span_spacing_preserves_words(rotation):
    from collections import Counter
    from pdf_obsidian.layout import extract_text_block
    from pdf_obsidian.pdf import displayed_text
    with pymupdf.open() as doc:
        page = doc.new_page()
        page.set_rotation(rotation)
        spans = [dict(text='Primeira', size=12, bbox=(10, 10, 50, 22), origin=(10, 20)),
                 dict(text='palavra', size=12, bbox=(55, 10, 95, 22), origin=(55, 20))]
        data = {'blocks': [dict(bbox=(10, 10, 95, 22), lines=[dict(
            bbox=(10, 10, 95, 22), dir=(1, 0), spans=spans)])]}
        transformed = displayed_text(page, data)
        block = extract_text_block(transformed['blocks'][0], 1, 0, Counter())
        assert block.text == 'Primeira palavra'


def test_manifest_is_captured_before_publication_becomes_visible(tmp_path, monkeypatch):
    import pdf_obsidian.exporter as exporter
    result = convert(synthetic(tmp_path / 'documento.pdf'), tmp_path / 'work')
    vault = tmp_path / 'vault'
    vault.mkdir()
    actual = exporter.export_document
    def external_edit_after_publish(*args, **kwargs):
        target = actual(*args, **kwargs)
        next(target.glob('*.md')).unlink()
        return target
    monkeypatch.setattr(exporter, 'export_document', external_edit_after_publish)
    commands, events = Queue(), Queue()
    commands.put(('session_export', 'token', 'session', 1, str(vault), result,
                  result.markdown, False, (), None))
    commands.put(('stop',))
    run(commands, events, Event())
    event = events.get_nowait()
    assert event[4] is True
    record = ExportRecord(event[5], Path(event[6]), event[8])
    assert not export_intact(record, vault)
    assert any(name.endswith('.md') for name in record.manifest)
