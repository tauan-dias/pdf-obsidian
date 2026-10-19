"""Regressões sintéticas de sobreposição, margens e recuperação."""
import json
import time
from collections import Counter

import pymupdf
import pytest
from PySide6.QtGui import QTextCursor, QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QFileDialog, QMessageBox

from pdf_obsidian.converter import convert, file_hash
from pdf_obsidian.conversion_filters import (deduplicate_text_blocks, recurring_margins,
                                             vector_signature)
from pdf_obsidian.exporter import export_document
from pdf_obsidian.filtered_images import FilteredImagesDialog, restoration_edit
from pdf_obsidian.gui import Window
from pdf_obsidian.layout import extract_text_block
from pdf_obsidian.models import Page


@pytest.fixture
def margin_source(tmp_path):
    source = tmp_path / 'margens.pdf'
    pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 60, 20), False)
    pixmap.set_rect(pixmap.irect, (20, 80, 160))
    with pymupdf.open() as doc:
        for n in range(5):
            page = doc.new_page()
            page.insert_image(pymupdf.Rect(40, 20, 100, 40), stream=pixmap.tobytes('png'))
            page.draw_rect(pymupdf.Rect(280, 20, 330, 45), color=(.2, .3, .5), fill=(.5, .6, .8))
            page.insert_text((284, 34), f'Logo {n+1}', fontsize=8)
            page.insert_text((50, 110), 'Titulo repetido', fontsize=20)
            page.insert_text((50, 110), 'Titulo repetido', fontsize=20)
            page.insert_text((50, 150), f'Conteudo essencial da pagina {n+1}.', fontsize=12)
            page.insert_image(pymupdf.Rect(50, 200, 110, 220), stream=pixmap.tobytes('png'))
            page.draw_rect(pymupdf.Rect(280, 200, 330, 225), color=(.2, .3, .5), fill=(.5, .6, .8))
            # Outra identidade aparece uma única vez na margem.
            if n == 0:
                page.draw_circle((400, 35), 10, color=(1, 0, 0))
        doc.save(source)
    return source


def test_overlaid_titles_and_conservative_filter(margin_source, tmp_path):
    before = file_hash(margin_source)
    result = convert(margin_source, tmp_path / 'work')
    assert file_hash(margin_source) == before
    assert len(result.filtered_images) == 10
    assert {asset.origin for asset in result.assets if asset.path in {item.asset for item in result.filtered_images}} == {'raster', 'vector'}
    assert result.markdown.count('Titulo repetido') == 5  # Uma ocorrência legítima por página.
    assert result.markdown.count('Logo') == 5  # Texto sob o vetor filtrado é preservado.
    assert len([d for d in result.decisions if 'linha sobreposta' in d]) == 5
    assert all(item.asset not in result.markdown for item in result.filtered_images)
    assert all((result.workspace / asset.path).exists() for asset in result.assets)
    assert len([asset for asset in result.assets if asset.bbox[1] > 100]) == 10
    unique = [asset for asset in result.assets if asset.bbox[0] > 380]
    assert len(unique) == 1 and unique[0].path in result.markdown


def test_dedup_tolerance_unicode_partial_and_direction():
    def raw(text, dx=0, direction=(1., 0.)):
        bbox = (10 + dx, 10., 100 + dx, 25.)
        return {'type': 0, 'bbox': bbox, 'lines': [{'bbox': bbox, 'dir': direction,
            'spans': [{'text': text, 'size': 12., 'bbox': bbox}]}]}
    originals = [raw('Ação  e revisão'), raw('Ação e revisão', .9), raw('Ação e revisão', 2),
                 raw('Ação'), raw('Ação e revisão', direction=(0., 1.))]
    decisions = []
    blocks = list(deduplicate_text_blocks(originals, 1, decisions))
    assert len(blocks) == 4 and len(decisions) == 1
    sizes = Counter()
    for block in blocks:
        extract_text_block(block, 1, 0, sizes)
    assert sizes[12.] == sum(len(block['lines'][0]['spans'][0]['text'].strip()) for block in blocks)
    assert len(originals[0]['lines']) == 1


@pytest.mark.parametrize('count,total,expected', [(2, 2, 0), (2, 3, 0), (3, 3, 3), (3, 5, 0), (4, 5, 4)])
def test_filter_frequency(count, total, expected):
    pages = [Page(n + 1, 600, 800) for n in range(total)]
    regions = [[(pymupdf.Rect(30, 20, 90, 40), 'image', 'same')] if n < count else [] for n in range(total)]
    assert len(recurring_margins(pages, regions)) == expected


@pytest.mark.parametrize('kind,digest,rect', [
    ('table', 'same', (30, 20, 90, 40)),
    ('formula', 'same', (30, 20, 90, 40)),
    ('image', None, (30, 20, 90, 40)),
    ('image', 'same', (30, 70, 90, 90)),  # Cruza o limite de 10%.
    ('figure', 'same', (30, 200, 90, 220)),
])
def test_uncertain_body_and_detected_regions_preserved(kind, digest, rect):
    pages = [Page(n + 1, 600, 800) for n in range(3)]
    assert not recurring_margins(pages, [[(pymupdf.Rect(rect), kind, digest)] for _ in pages])


def test_position_size_identity_and_footer():
    pages = [Page(n + 1, 600, 800) for n in range(3)]
    def regions(rects, digests=None):
        return [[(pymupdf.Rect(rect), 'image', digest)] for rect, digest in zip(rects, digests or ['same'] * 3)]
    base = (30, 20, 90, 40)
    assert not recurring_margins(pages, regions([base, base, (34, 20, 94, 40)]))
    assert not recurring_margins(pages, regions([base, base, (30, 20, 94, 40)]))
    assert not recurring_margins(pages, regions([base] * 3, ['a', 'a', 'b']))
    assert len(recurring_margins(pages, regions([(30, 740, 90, 760)] * 3))) == 3
    assert len(recurring_margins(pages, regions([base, (33, 20, 93, 40), base]))) == 3
    # Sem agrupamento transitivo: extremos separados por mais de 0,5%.
    assert not recurring_margins(pages, regions([base, (33, 20, 93, 40), (36, 20, 96, 40)]))
    repeated_same_page = [[(pymupdf.Rect(base), 'image', 'same')] * 4, [], []]
    assert not recurring_margins(pages, repeated_same_page)


def test_vector_signature_translation_and_style():
    with pymupdf.open() as doc:
        signatures = []
        for dx, color in [(0, (1, 0, 0)), (20, (1, 0, 0)), (0, (0, 1, 0))]:
            page = doc.new_page()
            rect = pymupdf.Rect(30 + dx, 20, 90 + dx, 40)
            page.draw_rect(rect, color=color)
            signatures.append(vector_signature(rect, page.get_drawings()))
    assert signatures[0] == signatures[1] != signatures[2]


def test_restoration_and_export(margin_source, tmp_path):
    result = convert(margin_source, tmp_path / 'work')
    item = result.filtered_images[0]
    exported = export_document(result, tmp_path)
    assert not (exported / item.asset).exists()
    entry = json.loads((exported / 'conversao.json').read_text())['filtered_images'][0]
    assert not entry['incorporated'] and not entry['file_exported']
    markdown = result.markdown.replace('Conteudo', '💡 Conteudo', 1)
    position, insertion = restoration_edit(result, markdown, item)
    updated = markdown[:position] + insertion + markdown[position:]
    assert updated.index(item.asset) < updated.index('<!-- Página 2 -->')
    assert '💡 Conteudo' in updated
    with pytest.raises(ValueError, match='já está'):
        restoration_edit(result, updated, item)
    exported = export_document(result, tmp_path, updated)
    assert (exported / item.asset).exists()
    entry = json.loads((exported / 'conversao.json').read_text())['filtered_images'][0]
    assert entry['incorporated'] and entry['referenced'] and entry['file_exported']
    for text in (markdown.replace('<!-- Página 1 -->', ''), markdown + '\n<!-- Página 1 -->'):
        with pytest.raises(ValueError, match='ausente ou duplicado'):
            restoration_edit(result, text, item)
    # Exemplos de marcadores e incorporações em código não contam.
    example = f'```md\n<!-- Página 1 -->\n![Exemplo]({item.asset})\n```\n\n' + markdown
    restoration_edit(result, example, item)
    last = result.filtered_images[-1]
    with pytest.raises(ValueError, match='incompleta'):
        restoration_edit(result, markdown + '\n```md\nExemplo sem fechamento', last)


@pytest.fixture
def filtered_window(app, margin_source, monkeypatch):
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *a: (str(margin_source), 'PDF'))
    monkeypatch.setattr(QMessageBox, 'question', lambda *a: QMessageBox.Yes)
    errors = []
    monkeypatch.setattr(QMessageBox, 'critical', lambda *a: errors.append(a[-1]))
    window = Window()
    window.show()
    def wait():
        deadline = time.monotonic() + 15
        while window.busy or window.result is None:
            app.processEvents()
            QTest.qWait(5)
            if time.monotonic() > deadline:
                pytest.fail('Conversão não terminou.')
        app.processEvents()
    try:
        window.open_pdf()
        wait()
        yield window, wait
        assert not errors
    finally:
        window.editor.document().setModified(False)
        window.close()
        app.processEvents()


def test_review_restore_history_and_navigation(filtered_window, app):
    window, wait = filtered_window
    assert not window.filtered_button.isHidden()
    dialog = FilteredImagesDialog(window)
    try:
        dialog.show()
        app.processEvents()
        assert dialog.palette().color(QPalette.Window) == window.palette().color(QPalette.Window)
        assert dialog.items.count() == 10
        assert not dialog.items.item(0).icon().isNull()
        before = window.editor.toPlainText()
        window.editor.selectAll()
        saved = window.editor.textCursor()
        item = dialog.current()
        dialog.restore.click()
        assert item.asset in window.editor.toPlainText()
        assert not dialog.restore.isEnabled()
        assert window.editor.textCursor().selectedText().replace('\u2029', '\n').startswith(before[:40])
        assert window.editor.document().isModified()
        window.editor.undo()
        assert window.editor.toPlainText() == before
        assert dialog.restore.isEnabled()
        window.editor.redo()
        assert item.asset in window.editor.toPlainText()
        assert not dialog.restore.isEnabled()
        window.set_manual_zoom(125)
        wait()
        window.set_pdf_visible(False)
        dialog.items.setCurrentRow(4)
        cursor = window.editor.textCursor()
        dialog.show_page.click()
        wait()
        assert not window.pdf_panel.isHidden()
        assert window.displayed_page == dialog.current().page
        assert window.zoom_percent == 125
        assert window.editor.textCursor().anchor() == cursor.anchor()
        assert window.editor.textCursor().position() == cursor.position()
        # Bloqueio recuperável quando o marcador é editado.
        window.editor.setPlainText(before.replace(f'<!-- Página {dialog.current().page} -->', ''))
        assert not dialog.restore.isEnabled()
        assert 'ausente ou duplicado' in dialog.message.text()
    finally:
        dialog.close()
        dialog.deleteLater()


def test_cancel_before_rasterization(margin_source, tmp_path):
    from pdf_obsidian.converter import ConversionCancelled
    events = []
    def progress(current, total):
        events.append((current, total))
    with pytest.raises(ConversionCancelled):
        convert(margin_source, tmp_path / 'cancelled', progress,
                lambda: bool(events and events[-1][0] >= 5))
    assert events[-1] == (5, 10)
    assert not list((tmp_path / 'cancelled' / 'assets').iterdir())


def test_restore_after_alt_edit_and_last_page(margin_source, tmp_path):
    result = convert(margin_source, tmp_path / 'work')
    item = result.filtered_images[-1]
    position, insertion = restoration_edit(result, result.markdown, item)
    assert position == len(result.markdown)
    text = result.markdown + insertion.replace('Figura', 'Descrição editada')
    with pytest.raises(ValueError, match='já está'):
        restoration_edit(result, text, item)
    referenced = result.markdown + f'\n[Consultar]({item.asset})\n'
    restoration_edit(result, referenced, item)
    target = export_document(result, tmp_path, referenced)
    entry = json.loads((target / 'conversao.json').read_text())['filtered_images'][-1]
    assert not entry['incorporated'] and entry['referenced'] and entry['file_exported']


def test_review_can_restore_then_remove_manually(filtered_window):
    from pdf_obsidian.cleanup import build_manual_cleanup_plan
    window, _ = filtered_window
    item = window.result.filtered_images[0]
    before = window.editor.toPlainText()
    cursor = window.editor.textCursor()
    cursor.setPosition(4)
    cursor.setPosition(10, QTextCursor.KeepAnchor)
    window.editor.setTextCursor(cursor)
    selected = cursor.selectedText()
    window.restore_filtered_image(item)
    assert window.editor.textCursor().selectedText() == selected
    plan = build_manual_cleanup_plan(window.result, window.editor.toPlainText(), [(item.asset, 0)])
    window.apply_cleanup_plan(plan, window.strip_page_markers)
    assert item.asset not in window.editor.toPlainText()
    window.editor.undo()
    assert item.asset in window.editor.toPlainText()
    window.editor.undo()
    assert window.editor.toPlainText() == before
