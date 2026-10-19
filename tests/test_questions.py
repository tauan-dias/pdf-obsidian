"""Questões sintéticas; nenhum conteúdo do PDF pessoal é usado nas regressões."""
import json

import pymupdf
import pytest
from PySide6.QtGui import QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QFileDialog, QMessageBox

from pdf_obsidian.comparison import unique_markers
from pdf_obsidian.converter import convert, escape, file_hash
from pdf_obsidian.conversion_filters import deduplicate_text_blocks
from pdf_obsidian.exporter import export_document
from pdf_obsidian.layout import reconstruct_page, word_inventory
from pdf_obsidian.models import Block, Page, TextLine
from pdf_obsidian.questions import (QuestionRendering, key_pairs, prepare_questions, serialize_blocks)


def line(text, y, *, x=48, right=550, size=12, source=0):
    return TextLine(text, (x, y - size, right, y + 3), size, 'Helvetica', 0, y, source)


def organize(*groups):
    pages = [Page(n + 1, 595, 842, [Block('text', item.text, n + 1, item.bbox, item.size, lines=[item])
             for item in group]) for n, group in enumerate(groups)]
    warnings, decisions = [], []
    prepare_questions(pages, 12, [20], {}, warnings, decisions)
    state, output = QuestionRendering(), []
    for page in pages:
        page.blocks, _ = reconstruct_page(page, 12, [20], {}, word_inventory(pages))
        output.append(f'<!-- Página {page.number} -->')
        output.extend(serialize_blocks(page.blocks, state, escape, warnings))
    return '\n\n'.join(output), pages, warnings, decisions


@pytest.fixture
def question_source(tmp_path):
    source = tmp_path / 'exercicios-sinteticos.pdf'
    with pymupdf.open() as doc:
        def page(rows):
            p = doc.new_page()
            for text, y, size in rows:
                p.insert_text((48, y), text, fontsize=size)
            return p
        p = page([
            ('Conceitos', 80, 20),
            ('1. Primeiro passo de uma lista comum.', 120, 12),
            ('2. Segundo passo de uma lista comum.', 138, 12),
            ('A alternativa a) citada nesta frase deve permanecer no texto.', 175, 12),
            ('001. (BANCA/ANALISTA (SEDE)/', 250, 12),
            ('2025) Analise as afirmativas sobre um sistema ficticio.', 268, 12),
            ('I - O sistema permite consultas.', 305, 12),
            ('II - O sistema armazena registros.', 323, 12),
            ('Assinale a alternativa correta.', 355, 12),
            ('a) Uma alternativa longa que continua', 390, 12),
            ('nesta linha, sem criar outro item.', 408, 12),
            ('b) Outra alternativa.', 440, 12),
        ])
        p.insert_text((48, 249.9), '001.', fontsize=11)
        p.draw_rect(pymupdf.Rect(60, 500, 200, 560), color=(.2, .4, .6), fill=(.7, .8, .9))
        page([
            ('c) Alternativa que comeca na pagina seguinte.', 100, 12),
            ('Comentario: As afirmativas descrevem operacoes ficticias.', 140, 12),
            ('Letra b.', 180, 12),
            ('Revisao teorica', 240, 20),
            ('Uma referencia a alternativa a) dentro da explicacao.', 280, 12),
        ])
        page([
            ('QUESTOES DE CONCURSO', 80, 20),
            ('001. Assinale a alternativa correta.', 125, 12),
            ('a) Opcao inicial.', 155, 12),
            ('b) Opcao seguinte.', 173, 12),
            ('Questao 002 - Julgue a afirmativa.', 220, 12),
            ('O sistema permite preservar os registros.', 250, 12),
            ('Errado.', 290, 12),
        ])
        page([
            ('GABARITO', 80, 20),
            ('001. b', 120, 12),
            ('002. E', 140, 12),
        ])
        page([
            ('003. Anulada', 100, 12),
            ('004. C 005. d', 120, 12),
        ])
        page([
            ('GABARITO COMENTADO', 80, 20),
            ('001. (BANCA/ANALISTA/2025) Julgue o item.', 125, 12),
            ('Um sistema ficticio pode armazenar registros.', 143, 12),
            ('A explicacao conserva todos os exemplos e detalhes.', 190, 12),
            ('Certo.', 230, 12),
        ])
        doc.save(source)
    return source


def test_synthetic_conversion_structure_and_integrity(question_source, tmp_path):
    before = file_hash(question_source)
    result = convert(question_source, tmp_path / 'work')
    text = result.markdown
    assert file_hash(question_source) == before
    assert text.count('Questão 001') == 3  # Teoria, exercícios e comentários são seções distintas.
    assert text.count('Questão 002') == 1
    assert '**(BANCA/ANALISTA (SEDE)/ 2025)**' in text
    assert '**a)** Uma alternativa longa que continua nesta linha, sem criar outro item.' in text
    assert '**b)** Outra alternativa.\n\n![Figura' in text
    assert '<!-- Página 2 -->\n\n**c)** Alternativa' in text
    assert '**I -** O sistema permite consultas.' in text
    assert '**II -** O sistema armazena registros.' in text
    assert '**Comentario**\n\nAs afirmativas' in text
    assert '**Letra b.**' in text and '**Errado.**' in text and '**Certo.**' in text
    assert '1. Primeiro passo' in text and '2. Segundo passo' in text
    assert 'A alternativa a) citada' in text
    assert 'Uma referencia a alternativa a) dentro' in text
    assert text.count('| Questão | Resposta |') == 2
    assert '| 001 | b |\n| 002 | E |' in text
    assert '| 003 | Anulada |\n| 004 | C |\n| 005 | d |' in text
    assert len(unique_markers(text)) == 6
    assert all((result.workspace / asset.path).is_file() for asset in result.assets)
    assert any('número sobreposto ao prefixo' in decision for decision in result.decisions)
    assert any('Limite entre enunciado e comentário' in warning.message for warning in result.warnings)
    assert text.count('**Comentário**') == 0  # Sem inventar rótulo a partir de espaços/ícones.
    target = export_document(result, tmp_path, text, strip_page_markers=True)
    final = next(target.glob('*.md')).read_text()
    assert '<!-- Página' not in final
    assert final.count('Questão 001') == 3
    assert '**c)** Alternativa' in final
    assert (target / 'original.pdf').read_bytes() == question_source.read_bytes()
    assert any('organização de' in entry for entry in json.loads((target / 'conversao.json').read_text())['decisions'])


def test_context_metadata_geometry_and_parent_heading():
    text, pages, warnings, _ = organize([
        line('Capítulo', 70, size=20),
        line('008. (BANCA/ANALISTA (SEDE)/', 100),
        line('2025) Um enunciado longo que continua', 118, source=1),
        line('nesta linha.', 136, source=2),
        line('a) Uma alternativa longa que continua', 160),
        line('nesta outra linha.', 178),
        line('b) Outra alternativa.', 196),
        line('I – Uma afirmativa.', 225),
        line('II – Outra afirmativa.', 243),
        line('Comentário: Texto explicativo.', 280),
        line('Resposta: C', 310),
    ])
    assert '### Questão 008' in text
    assert '**(BANCA/ANALISTA (SEDE)/ 2025)**' in text
    assert 'Um enunciado longo que continua nesta linha.' in text
    assert '**a)** Uma alternativa longa que continua nesta outra linha.' in text
    assert '**I –** Uma afirmativa.' in text
    assert '**Comentário**\n\nTexto explicativo.' in text
    assert '**Resposta: C**' in text
    assert not warnings
    assert {b.role for b in pages[0].blocks} >= {'question_header', 'question_option', 'question_statement', 'question_comment', 'question_answer'}


def test_page_continuation_and_context_reset():
    text, _, _, _ = organize([
        line('Questão 01 — Assinale a opção.', 100),
        line('a) Uma opção.', 140),
        line('b) Alternativa longa', 158),
    ], [
        line('que continua na outra página.', 100),
        line('c) Outra opção.', 130),
        line('Novo capítulo', 200, size=20),
        line('a) Primeiro item comum.', 230),
        line('b) Segundo item comum.', 248),
    ])
    assert text.count('Questão 01') == 1
    assert '**b)** Alternativa longa\n\n<!-- Página 2 -->\n\nque continua' in text
    assert '**c)** Outra opção.' in text
    assert '**a)** Primeiro item comum.' not in text


@pytest.mark.parametrize('content', [
    '1. Primeiro passo.', '2. (um exemplo) sem metadados de prova.',
    '3. (2024) Ano de referência.', 'A alternativa a) aparece em uma frase.',
    'I – Texto teórico.', 'a) Lista fora de uma questão.',
])
def test_ordinary_content_is_not_a_question(content):
    text, _, warnings, _ = organize([line(content, 100)])
    assert ' Questão ' not in text
    assert '**a)**' not in text and '**I –**' not in text


def test_uncertain_metadata_labels_and_answer_key_preserved():
    text, _, warnings, _ = organize([
        line('Questão 001 – (BANCA/PROVA', 100),
        line('a) Uma opção isolada.', 140),
        line('c) Falta uma alternativa nesta sequência.', 160),
        line('GABARITO', 230, size=20),
        line('001. C', 270),
        line('002. conferir depois', 290),
    ])
    assert '(BANCA/PROVA' in text
    assert 'a) Uma opção isolada.' in text
    assert '**a)**' not in text
    assert '002. conferir depois' in text
    assert any('banca incompleta' in warning.message for warning in warnings)
    assert any('Sequência ou recuo' in warning.message for warning in warnings)
    assert any('gabarito ambígua' in warning.message for warning in warnings)


def test_label_sequence_and_geometry():
    text, _, warnings, _ = organize([
        line('Questão 001 — Assinale.', 100),
        line('a) Um item.', 130), line('b) Outro item.', 148),
        line('c) Texto de outra coluna.', 166, x=330),
        line('d) Sem precedente seguro.', 184),
    ])
    assert '**a)** Um item.' in text and '**b)** Outro item.' in text
    assert '**c)**' not in text and '**d)**' not in text
    assert any('recuo' in warning.message for warning in warnings)


@pytest.mark.parametrize('text,expected', [('01. C 02. e', [('01', 'C'), ('02', 'e')]),
    ('03. Anulada', [('03', 'Anulada')]), ('04. Certo.', [('04', 'Certo')]),
    ('05. C porque sim', []), ('texto 01. A', []), ('06. Z', [])])
def test_answer_key_is_only_complete_pairs(text, expected):
    assert key_pairs(text) == expected


def test_prefix_duplicate_requires_number_and_position():
    def raw(text, box):
        return {'type': 0, 'bbox': box, 'lines': [{'bbox': box,
                'spans': [{'text': text, 'size': 12, 'bbox': box}]}]}
    blocks = [raw('001.', (48, 90, 75, 104)),
              raw('001. (BANCA/2025) Assinale.', (48, 89.5, 400, 104.5)),
              raw('001.', (48, 120, 75, 134)),
              raw('002.', (48, 90, 75, 104)),
              raw('001.', (148, 90, 175, 104))]
    decisions = []
    kept = list(deduplicate_text_blocks(blocks, 1, decisions))
    assert len(kept) == 4 and len(decisions) == 1
    assert kept[0]['lines'][0]['spans'][0]['text'].startswith('001. (BANCA')


def test_preview_headings_table_and_existing_editor_history(app, question_source, tmp_path, monkeypatch):
    import time
    from pdf_obsidian.gui import Window
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *a: (str(question_source), 'PDF'))
    errors = []
    monkeypatch.setattr(QMessageBox, 'critical', lambda *a: errors.append(a[-1]))
    window = Window()
    window.show()
    try:
        window.open_pdf()
        deadline = time.monotonic() + 15
        while window.busy or window.result is None:
            app.processEvents()
            QTest.qWait(5)
            assert time.monotonic() < deadline
        original = window.editor.toPlainText()
        window.refresh_preview()
        assert 'Questão 001' in window.preview.toPlainText()
        document = window.preview.document()
        headings = []
        block = document.begin()
        while block.isValid():
            if block.blockFormat().headingLevel():
                headings.append((block.text(), block.blockFormat().headingLevel()))
            block = block.next()
        assert any(text == 'Questão 001' for text, _ in headings)
        assert document.find('Resposta').currentTable() is not None
        assert all(window.preview.document().find(f'Questão {n}').isNull() is False for n in ['001', '002'])
        window.editor.moveCursor(QTextCursor.End)
        window.editor.insertPlainText('\nMinha revisão pessoal.')
        window.tabs.setCurrentWidget(window.preview)
        app.processEvents()
        window.refresh_preview()
        assert 'Minha revisão pessoal.' in window.preview.toPlainText()
        window.editor.undo()
        assert window.editor.toPlainText() == original
        window.editor.redo()
        assert window.editor.toPlainText().endswith('Minha revisão pessoal.')
        assert not errors
    finally:
        window.editor.document().setModified(False)
        window.close()
        app.processEvents()


def test_unlisted_board_metadata_with_year_on_following_line():
    text, _, warnings, _ = organize([
        line('003. (INSTITUTO FICTÍCIO/ANALISTA/', 100),
        line('2025) Assinale a alternativa.', 118, source=1),
        line('a) Primeira opção que continua', 150),
        line('com recuo pendente.', 168, x=64),
        line('b) Outra opção.', 186),
    ])
    assert 'Questão 003' in text
    assert '**(INSTITUTO FICTÍCIO/ANALISTA/ 2025)**' in text
    assert '**a)** Primeira opção que continua com recuo pendente.' in text
    assert not warnings


@pytest.mark.parametrize('content', ['Questão 12345', 'Questão 1.2 do capítulo', 'Questão 01a: referência'])
def test_ambiguous_explicit_numbers_not_truncated(content):
    text, _, _, _ = organize([line(content, 100)])
    assert content in text
    assert '# Questão ' not in text


def test_explicit_title_and_metadata_on_next_line_with_font_change():
    text, _, warnings, _ = organize([
        line('Questão 001', 100, size=20),
        line('(INSTITUTO FICTÍCIO/PROVA/2025) Assinale a opção.', 118, source=1),
        line('a) Uma alternativa.', 150), line('b) Outra alternativa.', 168),
    ])
    assert '**(INSTITUTO FICTÍCIO/PROVA/2025)**' in text
    assert 'Questão 001' in text
    assert '**a)** Uma alternativa.' in text
    assert not warnings


def test_question_analysis_checks_cancellation():
    from pdf_obsidian.converter import ConversionCancelled
    item = line('Questão 001 – Enunciado.', 100)
    page = Page(1, 595, 842, [Block('text', item.text, 1, item.bbox, lines=[item])])
    def cancel():
        raise ConversionCancelled()
    with pytest.raises(ConversionCancelled):
        prepare_questions([page], 12, [20], {}, [], [], check=cancel)
