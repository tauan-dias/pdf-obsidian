"""Estrutura de exercícios por evidência textual e geometria, sem interpretar respostas."""
from collections import Counter
from dataclasses import dataclass
import re
import unicodedata

from .layout import _role
from .models import Warning

EXPLICIT = re.compile(r'^Quest(?:ão|ao)\s+(\d{1,4})(?!\d|\.\d)(?=\s|[.):–—-]|$)(?:\s*[.):–—-])?\s*(.*)$', re.I)
NUMBERED = re.compile(r'^(\d{1,4})[.)]\s*(\S.*)$')
OPTION = re.compile(r'^([a-zA-Z])[.)]\s+\S')
ROMAN = re.compile(r'^(I|II|III|IV|V|VI|VII|VIII|IX|X|XI|XII|XIII|XIV|XV|XVI|XVII|XVIII|XIX|XX)\s*[–—−.)-]\s+\S')
ROMANS = ('I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X',
          'XI', 'XII', 'XIII', 'XIV', 'XV', 'XVI', 'XVII', 'XVIII', 'XIX', 'XX')
COMMENT = re.compile(r'^(Coment[áa]rios?|Resolu[çc][ãa]o|Solu[çc][ãa]o)(?:\s*:\s*(.*)|\s*)$', re.I)
ANSWER = re.compile(r'^(?:(?:Certo|Errado)|Letra\s+[a-z]|(?:Gabarito|Resposta)\s*:\s*(?:[a-e]|Certo|Errado|Anulad[ao]))\.?$', re.I)
KEY_PAIR = re.compile(r'(\d{1,4})[.)]\s*(Certo|Errado|Anulad[ao]|[a-eA-E]|[–—-])\.?(?=\s|$)', re.I)


def normalized(text):
    return unicodedata.normalize('NFKD', text.replace('\ufeff', '')).encode('ascii', 'ignore').decode().strip().casefold()


def question_prefix(text):
    match = EXPLICIT.match(text) or NUMBERED.match(text)
    return (match[1], match[2]) if match else None


def metadata_end(text):
    """Fecho do primeiro parêntese, incluindo nomes de órgãos com parênteses."""
    if not text.startswith('('):
        return None
    depth = 0
    for index, char in enumerate(text):
        depth += (char == '(') - (char == ')')
        if depth == 0:
            return index + 1
    return None


def key_pairs(text):
    pairs = list(KEY_PAIR.finditer(text))
    if not pairs:
        return []
    previous = 0
    for pair in pairs:
        if text[previous:pair.start()].strip():
            return []
        previous = pair.end()
    return [(pair[1], pair[2]) for pair in pairs] if not text[previous:].strip() else []


def warn(warnings, page, message):
    if not any(item.page == page and item.message == message for item in warnings):
        warnings.append(Warning(page, message))


def _metadata_evidence(text):
    end = metadata_end(text)
    metadata = text[:end] if end else text
    return bool(('/' in metadata and re.search(r'\b(?:19|20)\d{2}\b', metadata))
                or re.search(r'\b(?:CESPE|CEBRASPE|FGV|VUNESP|FCC|QUADRIX|BANCA|ESAF|CESGRANRIO|FUNIVERSA|COMPEC|CETRO)\b', metadata, re.I))


def _question_start(entries, index, question_section):
    _, line = entries[index]
    if EXPLICIT.match(line.text):
        return True
    match = NUMBERED.match(line.text)
    if not match:
        return False
    remainder = match[2]
    if remainder.startswith('('):
        # Metadados podem atravessar vários blocos; não aceitar qualquer lista entre parênteses.
        sample = remainder
        for _, following in entries[index + 1:index + 7]:
            next_prefix = NUMBERED.match(following.text)
            if metadata_end(sample) is not None or EXPLICIT.match(following.text) or (
                    next_prefix and next_prefix[2].startswith('(')):
                break
            sample += ' ' + following.text
        return _metadata_evidence(sample)
    return question_section and (len(match[1]) >= 3 or bool(re.search(
        r'\b(?:julgue|assinale|analise|considere|qual|quais|marque)\b', remainder, re.I)))


def prepare_questions(pages, body_size, heading_sizes, outline, warnings, decisions, check=None):
    """Anotar linhas antes de reconstruí-las; contextos podem atravessar páginas."""
    from .reading_order import regions
    entries = [(page, line) for page in pages
               for group in regions(page.blocks, page.width)
               for line in sorted(
                   (line for block in group if block.kind == 'text' for line in block.lines),
                   key=lambda line: (round(line.bbox[1] / 3), line.bbox[0]))]
    segments, active = [], None
    question_section = answer_key = False
    counts = Counter()
    for index, (page, line) in enumerate(entries):
        if check and index % 128 == 0:
            check()
        if abs(line.direction[0] - 1) > .01 or abs(line.direction[1]) > .01:
            continue
        name = normalized(line.text).rstrip(':').strip()
        role, _ = _role(line, body_size, heading_sizes, outline)
        special_section = name in ('gabarito', 'gabarito resumido', 'gabarito oficial',
            'gabarito comentado', 'questoes', 'questoes de concurso', 'exercicios', 'questoes comentadas')
        # Um início de questão explícito pode ter fonte grande; ele não é uma seção.
        start = _question_start(entries, index, question_section)
        if not start and (role == 'heading' or special_section):
            active = None
            question_section = name in ('questoes', 'questoes de concurso', 'exercicios',
                                         'gabarito comentado', 'questoes comentadas')
            answer_key = name in ('gabarito', 'gabarito resumido', 'gabarito oficial')
            if special_section and role != 'heading':
                line.role = 'exam_section'
            continue
        if answer_key:
            if key_pairs(line.text):
                line.role = 'answer_key'
                counts[page.number, 'gabarito'] += len(key_pairs(line.text))
            elif NUMBERED.match(line.text):
                line.role = 'question_unresolved'
                warn(warnings, page.number, 'Entrada de gabarito ambígua; texto preservado para revisão.')
            continue
        if start:
            line.role = 'question_header'
            active = [(page, line)]
            segments.append(active)
            counts[page.number, 'questões'] += 1
            continue
        if active is not None:
            active.append((page, line))
        elif NUMBERED.match(line.text) and NUMBERED.match(line.text)[2].startswith('('):
            line.role = 'question_unresolved'
            warn(warnings, page.number, 'Possível questão sem identificação suficiente; texto preservado para revisão.')

    for segment in segments:
        if check:
            check()
        page, first = segment[0]
        metadata = question_prefix(first.text)[1]
        separate_metadata = not metadata and len(segment) > 1 and segment[1][1].text.startswith('(') and _metadata_evidence(
            ' '.join(line.text for _, line in segment[1:7]))
        if separate_metadata or (metadata.startswith('(') and metadata_end(metadata) is None):
            previous = first
            for following_page, line in segment[1:7]:
                if (OPTION.match(line.text) or ROMAN.match(line.text) or COMMENT.match(line.text)
                        or ANSWER.match(line.text) or abs(line.bbox[0] - first.bbox[0]) > first.size * 4
                        or (following_page == page and line.baseline - previous.baseline > first.size * 2)):
                    break
                line.role = 'question_metadata'
                metadata = (metadata + ' ' + line.text).strip()
                previous, page = line, following_page
                if metadata_end(metadata) is not None:
                    break
            if metadata_end(metadata) is None:
                warn(warnings, segment[0][0].number, 'Identificação da banca incompleta; conteúdo preservado para revisão.')

        candidates = {'question_option': [], 'question_statement': []}
        explicit_comment = False
        for page, line in segment[1:]:
            if line.role:
                continue
            if COMMENT.match(line.text):
                line.role = 'question_comment'
                explicit_comment = True
            elif ANSWER.fullmatch(line.text):
                line.role = 'question_answer'
                explicit_comment = True
            elif not explicit_comment:
                roman = ROMAN.match(line.text)
                option = OPTION.match(line.text)
                if roman or option:
                    kind = 'question_statement' if roman else 'question_option'
                    label = ROMANS.index(roman[1]) + 1 if roman else ord(option[1].lower()) - ord('a') + 1
                    candidates[kind].append((page, line, label))
        for kind, items in candidates.items():
            previous = 0
            for index, (page, line, label) in enumerate(items):
                following = items[index + 1][2] if index + 1 < len(items) else None
                aligned = first.bbox[0] - line.size * .6 <= line.bbox[0] <= first.bbox[0] + line.size * 4
                if aligned and ((label == 1 and following == 2) or (previous and label == previous + 1)):
                    line.role = kind
                    previous = label
                else:
                    line.role = 'question_unresolved'
                    warn(warnings, page.number, 'Sequência ou recuo de alternativas/afirmativas ambíguo; texto preservado para revisão.')
        for (previous_page, previous), (page, line) in zip(segment, segment[1:]):
            if (previous_page == page and previous.role not in ('question_header', 'question_metadata')
                    and line.role is None and line.baseline - previous.baseline > line.size * 3
                    and page.height * .1 <= previous.bbox[1] <= line.bbox[1] < page.height * .9):
                warn(warnings, page.number, 'Limite entre enunciado e comentário sem identificação textual; separação original preservada.')

    for (page, kind), count in sorted(counts.items()):
        decisions.append(f'Página {page}: organização de {count} {kind}.')


@dataclass
class QuestionRendering:
    section_level: int = 1


def serialize_blocks(blocks, state, escape, warnings):
    """Emitir Markdown comum, mantendo imagens e páginas em suas posições."""
    output, pending_key = [], []

    def flush_key():
        if pending_key:
            output.append('| Questão | Resposta |\n| --- | --- |\n' + '\n'.join(
                f'| {escape(number)} | {escape(answer)} |' for number, answer in pending_key))
            pending_key.clear()

    for block in blocks:
        if block.role == 'answer_key':
            pending_key.extend(key_pairs(block.text))
            continue
        flush_key()
        if block.kind in ('recognized_table', 'recognized_formula'):
            output.append(block.text)
        elif block.kind == 'image':
            output.append(f'![{block.text} — página {block.page}]({block.asset})')
        elif block.heading_level or block.role == 'exam_section':
            state.section_level = min(6, block.heading_level + 1) if block.heading_level else 2
            output.append('#' * state.section_level + ' ' + escape(block.text))
        elif block.role == 'question_header':
            number, content = question_prefix(block.text)
            output.append('#' * min(6, state.section_level + 1) + f' Questão {number}')
            source_metadata = ' '.join(line.text for line in block.lines
                                       if line.role in ('question_header', 'question_metadata'))
            source_content = question_prefix(source_metadata)[1]
            end = metadata_end(content) if metadata_end(source_content) else None
            if end:
                output.append('**' + escape(content[:end]) + '**')
                if content[end:].strip():
                    output.append(escape(content[end:].strip()))
            elif content:
                output.append(escape(content))
                if content.startswith('('):
                    warn(warnings, block.page, 'Identificação da banca não pôde ser separada integralmente nesta página; texto preservado.')
        elif block.role in ('question_option', 'question_statement'):
            match = ROMAN.match(block.text) if block.role == 'question_statement' else OPTION.match(block.text)
            # O rótulo inclui o delimitador e os espaços são normalizados na extração.
            end = match.end() - 1
            label = block.text[:end].rstrip()
            output.append('**' + escape(label) + '** ' + escape(block.text[end:].lstrip()))
        elif block.role == 'question_answer':
            output.append('**' + escape(block.text) + '**')
        elif block.role == 'question_comment':
            match = COMMENT.match(block.text)
            output.append('**' + escape(match[1]) + '**')
            if match[2]:
                output.append(escape(match[2]))
        elif block.role in ('question_unresolved', 'question_metadata'):
            output.append(escape(block.text))
        else:
            lines = []
            for line in block.text.splitlines():
                bullet = re.match(r'^(?:[•●▪]|[-*])\s+(.*)', line)
                ordered = re.match(r'^(\d+)[.)]\s+(.*)', line)
                if bullet:
                    lines.append('- ' + escape(bullet[1]))
                elif ordered:
                    lines.append(ordered[1] + '. ' + escape(ordered[2]))
                else:
                    lines.append(escape(line))
            output.append('\n'.join(lines))
    flush_key()
    return output
