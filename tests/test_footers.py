"""Rodapés sintéticos e notas legítimas, sem usar documentos privados."""
import json

import pymupdf
import pytest
from PySide6.QtGui import QTextCursor

from pdf_obsidian.comparison import preview_document, unique_markers
from pdf_obsidian.converter import convert, file_hash, ConversionCancelled
from pdf_obsidian.exporter import export_document
from pdf_obsidian.footers import remove_recurring_footers
from pdf_obsidian.models import Block, Page, TextLine


def line(text, y, x=48, right=540, size=9, source=0, direction=(1, 0)):
    return TextLine(text, (x, y - size, right, y + 3), size, 'Helvetica', 0, y, source, direction)


def block(lines):
    return Block('text', '\n'.join(item.text for item in lines), 1,
                 (min(item.bbox[0] for item in lines), min(item.bbox[1] for item in lines),
                  max(item.bbox[2] for item in lines), max(item.bbox[3] for item in lines)),
                 lines[0].size, lines=lines)


def clean(groups):
    pages = [Page(index + 1, 595, 842, [block(items)]) for index, items in enumerate(groups)]
    decisions = []
    remove_recurring_footers(pages, decisions)
    return pages, decisions


@pytest.fixture
def footer_source(tmp_path):
    source = tmp_path / 'rodapes-sinteticos.pdf'
    with pymupdf.open() as doc:
        for number in range(1, 6):
            page = doc.new_page()
            page.insert_text((48, 90), 'QUESTOES DE CONCURSO', fontsize=20)
            page.insert_text((48, 650), f'{number:03}. (BANCA/PROVA/2025) Assinale a alternativa.', fontsize=12)
            page.insert_text((48, 772), 'a) Uma alternativa que deve permanecer.', fontsize=12)
            page.insert_text((48, 790), 'b) Outra alternativa que deve permanecer.', fontsize=12)
            page.insert_text((48, 815), f'{number} de 5\nexemplo.org', fontsize=9)
            # Mesmo operador PDF agrupa paginação e site em um bloco com duas linhas.
            grouped = [b for b in page.get_text('dict')['blocks'] if b.get('type') == 0
                       and any('exemplo.org' in s['text'] for l in b['lines'] for s in l['spans'])]
            assert len(grouped) == 1 and len(grouped[0]['lines']) == 2
        doc.save(source)
    return source


def test_page_number_and_site_in_one_pdf_block(footer_source, tmp_path):
    before = file_hash(footer_source)
    result = convert(footer_source, tmp_path / 'work')
    assert file_hash(footer_source) == before
    assert 'exemplo.org' not in result.markdown
    assert all(f'{n} de 5' not in result.markdown for n in range(1, 6))
    assert result.markdown.count('Questão ') == 5
    assert result.markdown.count('**a)** Uma alternativa') == 5
    assert result.markdown.count('**b)** Outra alternativa') == 5
    assert len(unique_markers(result.markdown)) == 5
    assert sum('rodape repetido' in item for item in result.decisions) == 10
    target = export_document(result, tmp_path, result.markdown + '\nMinha revisão.\n')
    final = next(target.glob('*.md')).read_text()
    assert 'exemplo.org' not in final and 'Minha revisão.' in final
    report = json.loads((target / 'conversao.json').read_text())
    assert sum('rodape repetido' in item for item in report['decisions']) == 10
    assert (target / 'original.pdf').read_bytes() == footer_source.read_bytes()


def test_partial_block_updates_text_geometry_size_and_keeps_images():
    pages, decisions = clean([[line('Conteúdo principal.', 650, size=12),
                              line('Editora exemplo', 790), line(f'{n} de 3', 815)] for n in range(1, 4)])
    for page in pages:
        remaining = page.blocks[0]
        assert remaining.text == 'Conteúdo principal.'
        assert len(remaining.lines) == 1
        assert remaining.bbox == (48, 638, 540, 653)
        assert remaining.size == 12
    assert len(decisions) == 6
    image = Block('image', 'Figura', 1, (50, 780, 100, 820), asset='assets/figura.png')
    for page in pages:
        page.blocks.append(image)
    remove_recurring_footers(pages, decisions)
    assert all(page.blocks[-1] is image for page in pages)
    assert len(decisions) == 6  # Reaplicar não registra remoções inexistentes.


@pytest.mark.parametrize('label', ['Nota: explicação importante.', 'Fonte: referência bibliográfica.',
    'Referências: material de apoio.', '[1] Uma nota explicativa.', '(1) Uma nota explicativa.',
    '1. Uma nota explicativa.', '* Uma nota explicativa.', '¹ Uma nota explicativa.',
    'a) Alternativa legítima.', 'II – Afirmativa legítima.'])
def test_repeated_notes_references_and_their_continuations_preserved(label):
    pages, decisions = clean([[line(label, 750), line('Continuação repetida que precisa permanecer.', 764),
                              line('https://referencia.org', 778), line('exemplo.org', 815)] for _ in range(3)])
    assert len(decisions) == 3
    for page in pages:
        text = page.blocks[0].text
        assert label in text and 'Continuação repetida' in text and 'https://referencia.org' in text
        assert 'exemplo.org' not in text


def test_fragmented_note_and_interleaved_page_number():
    pages = []
    for number in range(1, 4):
        items = [line('[1] Nota que começa acima da faixa.', 750, right=300),
                 line('Continuação da nota.', 764, right=300),
                 line(f'{number} de 3', 768, x=500, right=540),
                 line('Mais uma linha da nota.', 778, right=300),
                 line('exemplo.org', 815)]
        pages.append(Page(number, 595, 842, [block([item]) for item in items]))
    decisions = []
    remove_recurring_footers(pages, decisions)
    assert len(decisions) == 6
    assert all(len(page.blocks) == 3 for page in pages)
    assert all('Mais uma linha da nota.' in '\n'.join(b.text for b in page.blocks) for page in pages)


@pytest.mark.parametrize('marker', ['1', '1.', '[1]', '¹', '*', '†'])
def test_separate_small_note_marker(marker):
    pages, decisions = clean([[line(marker, 778, right=53, size=6),
                              line('Referência explicativa repetida.', 781, x=60, right=300),
                              line('Continuação explicativa.', 795, x=60, right=300),
                              line('exemplo.org', 825)] for _ in range(3)])
    assert len(decisions) == 3
    assert all(marker in page.blocks[0].text and 'Continuação explicativa.' in page.blocks[0].text for page in pages)


@pytest.mark.parametrize('count,total,expected', [(2, 2, 0), (2, 3, 0), (3, 3, 3), (3, 5, 0), (4, 5, 4)])
def test_recurrence_thresholds(count, total, expected):
    pages, decisions = clean([[line('exemplo.org' if n < count else f'Conteúdo único {n}', 810)] for n in range(total)])
    assert len(decisions) == expected


def test_duplicates_on_one_page_do_not_count_as_several_pages():
    _, decisions = clean([[line('exemplo.org', 780), line('exemplo.org', 800), line('exemplo.org', 820)],
                          [line('Conteúdo único', 810)], [line('Outro conteúdo único', 810)]])
    assert not decisions


def test_outside_footer_unique_and_uncertain_geometry_preserved():
    pages, decisions = clean([[line('Fim do conteúdo.', 760),  # Topo < 90%.
                              line(f'Nota única da página {n}.', 785),
                              line('Fora da página.', 850),
                              line('Texto rotacionado.', 815, direction=(0, 1)),
                              line('Rodapé recorrente', 830)] for n in range(3)])
    assert len(decisions) == 3
    for page in pages:
        assert 'Fim do conteúdo.' in page.blocks[0].text
        assert 'Nota única' in page.blocks[0].text
        assert 'Fora da página.' in page.blocks[0].text
        assert 'Texto rotacionado.' in page.blocks[0].text


@pytest.mark.parametrize('text', ['Página {n} de 3', 'page {n} of 3', 'p. {n}', '{n}/3', '{n}'])
def test_supported_pagination_normalization(text):
    pages, decisions = clean([[line(text.format(n=n), 815)] for n in range(1, 4)])
    assert len(decisions) == 3
    assert all(not page.blocks for page in pages)


def test_cancellation_during_footer_analysis():
    def cancel():
        raise ConversionCancelled()
    with pytest.raises(ConversionCancelled):
        remove_recurring_footers([Page(1, 595, 842)], [], check=cancel)


def test_preview_page_anchors_and_history_after_cleaning(app, footer_source, tmp_path):
    from PySide6.QtWidgets import QPlainTextEdit, QTextBrowser
    result = convert(footer_source, tmp_path / 'work')
    editor = QPlainTextEdit()
    browser = QTextBrowser()
    try:
        editor.setPlainText(result.markdown)
        editor.moveCursor(QTextCursor.End)
        editor.insertPlainText('\nRevisão pessoal.')
        browser.setDocument(preview_document(editor.toPlainText(), result.workspace, browser))
        browser.resize(600, 450)
        browser.show()
        app.processEvents()
        assert 'exemplo.org' not in browser.toPlainText()
        assert 'Questão 003' in browser.toPlainText()
        saved = editor.textCursor()
        browser.scrollToAnchor('pdf-page-3')
        assert browser.verticalScrollBar().value() > 0
        assert editor.textCursor().position() == saved.position()
        editor.undo()
        assert editor.toPlainText() == result.markdown
        editor.redo()
        assert editor.toPlainText().endswith('Revisão pessoal.')
    finally:
        browser.close()
        editor.close()
