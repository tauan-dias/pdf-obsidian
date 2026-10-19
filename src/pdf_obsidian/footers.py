"""Limpeza de texto recorrente no rodapé, protegendo notas e referências."""
from collections import Counter
from dataclasses import replace
import re

from .layout import _same_style, union_bbox


PAGINATION = re.compile(r'(?:(?:p[aá]gina|page|p\.)\s*)?\d+(?:\s*(?:/|de|of)\s*\d+)?', re.I)
NOTE_START = re.compile(
    r'^(?:(?:notas?|fontes?|refer[eê]ncias?|bibliografia)\b|'
    r'(?:\[\d{1,3}\]|\(\d{1,3}\)|\d{1,3}[.)]?|[¹²³⁴⁵⁶⁷⁸⁹⁰]+|[*†‡]+)\s+\S|'
    r'[a-zA-Z][.)]\s+\S|[IVXLCDM]+\s*[–—−.)-]\s+\S)', re.I)


def _key(line, page):
    if (line.bbox[1] < page.height * .9 or line.bbox[3] > page.height
            or line.bbox[0] < 0 or line.bbox[2] > page.width
            or abs(line.direction[0] - 1) > .01 or abs(line.direction[1]) > .01):
        return None
    text = re.sub(r'\s+', ' ', line.text.replace('\ufeff', '')).strip().casefold()
    return '#pagina' if PAGINATION.fullmatch(text) else text or None


def _protected_lines(page):
    """Acompanhar notas fragmentadas sem proteger paginação em outra coluna.

    URLs contíguas a uma nota continuam sendo referência; linhas separadas por
    espaço maior, estilo ou coluna são avaliadas independentemente.
    """
    lines = sorted((line for block in page.blocks if block.kind == 'text' for line in block.lines),
                   key=lambda line: (round(line.bbox[1] / 3), line.bbox[0]))
    protected = set()
    anchors = {id(line) for line in lines if NOTE_START.match(line.text)
               and not PAGINATION.fullmatch(line.text.strip())}
    # Marcadores pequenos podem vir em uma linha separada do texto da nota.
    marker = re.compile(r'(?:\[\d{1,3}\]|\(\d{1,3}\)|\d{1,3}[.)]?|[¹²³⁴⁵⁶⁷⁸⁹⁰]+|[*†‡]+)')
    for line in lines:
        if not marker.fullmatch(line.text.strip()):
            continue
        mates = [following for following in lines if following is not line
                 and not PAGINATION.fullmatch(following.text.strip())
                 and abs(following.baseline - line.baseline) <= max(line.size, following.size) * .8
                 and line.bbox[2] - 1 <= following.bbox[0] <= line.bbox[2] + following.size * 3]
        if mates:
            protected.add(id(line))
            anchors.update(id(following) for following in mates)
        elif not PAGINATION.fullmatch(line.text.strip()):
            protected.add(id(line))
    chains = []
    for line in lines:
        chains = [(anchor, previous) for anchor, previous in chains
                  if line.baseline - previous.baseline <= max(previous.size, line.size) * 1.8]
        if id(line) in anchors:
            protected.add(id(line))
            chains.append((line, line))
        elif not PAGINATION.fullmatch(line.text.strip()):
            for index, (anchor, previous) in enumerate(chains):
                if (_same_style(previous, line)
                        and previous.size * .4 < line.baseline - previous.baseline
                        and abs(line.bbox[0] - anchor.bbox[0]) <= line.size * 4):
                    protected.add(id(line))
                    chains[index] = anchor, line
                    break

    return protected


def remove_recurring_footers(pages, decisions, check=None):
    """Remover linhas, mantendo os demais componentes dos blocos e das páginas."""
    protected = []
    counts = Counter()
    for page in pages:
        if check:
            check()
        safe = _protected_lines(page)
        protected.append(safe)
        counts.update({_key(line, page) for block in page.blocks if block.kind == 'text'
                       for line in block.lines if id(line) not in safe} - {None})
    repeats = {key for key, count in counts.items() if count >= max(3, len(pages) * .7)}
    for page, safe in zip(pages, protected):
        if check:
            check()
        kept = []
        for block in page.blocks:
            if block.kind != 'text' or not block.lines:
                kept.append(block)
                continue
            lines = []
            for line in block.lines:
                if id(line) not in safe and _key(line, page) in repeats:
                    decisions.append(f'Página {page.number}: removido rodape repetido: {line.text}')
                else:
                    lines.append(line)
            if len(lines) == len(block.lines):
                kept.append(block)
            elif lines:
                weights = Counter()
                for line in lines:
                    weights[line.size] += len(line.text)
                kept.append(replace(block, text='\n'.join(line.text for line in lines), lines=lines,
                                    bbox=union_bbox(line.bbox for line in lines), size=weights.most_common(1)[0][0]))
        page.blocks = kept
