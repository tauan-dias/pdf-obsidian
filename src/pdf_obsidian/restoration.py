"""Preparação conservadora de restaurações, sem dependência de interface Qt."""
from .markdown import analyse_markdown, PAGE_COMMENT


def restoration_edit(result, markdown, filtered):
    """Preparar inserção localizada, sem interpretar exemplos como marcadores."""
    analysis = analyse_markdown(markdown, (asset.path for asset in result.assets))
    if any(image.asset == filtered.asset for image in analysis.image_occurrences):
        raise ValueError('Esta imagem já está incorporada no documento.')
    markers, offset = [], 0
    for index, line in enumerate(markdown.splitlines(keepends=True)):
        match = PAGE_COMMENT.fullmatch(line.rstrip('\r\n'))
        if match and index not in analysis.protected_lines and int(match[1]) <= len(result.pages):
            markers.append((int(match[1]), offset, offset + len(line)))
        offset += len(line)
    matches = [marker for marker in markers if marker[0] == filtered.page]
    if len(matches) != 1:
        raise ValueError('Marcador da página ausente ou duplicado. Corrija o marcador ou use um recorte manual no PDF.')
    marker = matches[0]
    following = next((item for item in markers if item[1] > marker[1]), None)
    position = following[1] if following else len(markdown)
    asset = next(asset for asset in result.assets if asset.path == filtered.asset)
    insertion = '\n\n' + asset.generated_markdown + '\n\n'
    updated = markdown[:position] + insertion + markdown[position:]
    if not any(image.asset == filtered.asset for image in analyse_markdown(updated).images):
        raise ValueError('O fim desta página contém uma estrutura Markdown incompleta. Corrija-a ou use um recorte manual no PDF.')
    return position, insertion
