"""Regiões conservadoras para leitura de duas colunas."""
def regions(items, width):
    items = list(items)
    ordered = sorted(items, key=lambda b: (round(b.bbox[1] / 3), b.bbox[0]))
    if any(abs(line.direction[0] - 1) > .01 or abs(line.direction[1]) > .01
           for item in items for line in getattr(item, 'lines', ())):
        return [ordered]
    separators = [b for b in ordered if b.bbox[2] - b.bbox[0] >= width * .65]
    others = [b for b in ordered if b not in separators]
    if separators and others and not any(
            a.bbox[1] < b.bbox[3] and b.bbox[1] < a.bbox[3]
            for a in separators for b in others):
        bands, remaining, found_columns = [], others, False
        for separator in separators:
            band = [b for b in remaining if b.bbox[3] <= separator.bbox[1]]
            groups = regions(band, width)
            found_columns |= len(groups) > 1
            bands.extend(group for group in groups if group)
            bands.append([separator])
            remaining = [b for b in remaining if b not in band]
        groups = regions(remaining, width)
        found_columns |= len(groups) > 1
        bands.extend(group for group in groups if group)
        if found_columns:
            return bands
    def evidence(group):
        return sum(len(getattr(b, 'lines', ())) or 1
                   for b in group if getattr(b, 'kind', 'text') == 'text')
    edges = sorted({b.bbox[0] for b in items} | {b.bbox[2] for b in items})
    candidates = []
    for low, high in zip(edges, edges[1:]):
        if high - low < width * .04:
            continue
        midpoint = (low + high) / 2
        left = [b for b in items if b.bbox[2] <= midpoint]
        right = [b for b in items if b.bbox[0] >= midpoint]
        if evidence(left) < 3 or evidence(right) < 3:
            continue
        overlap = min(max(b.bbox[3] for b in left), max(b.bbox[3] for b in right)) - max(
            min(b.bbox[1] for b in left), min(b.bbox[1] for b in right))
        if overlap > 0:
            candidates.append((left, right))
    if len(candidates) != 1:
        return [ordered]
    left, right = candidates[0]
    spanning = [b for b in ordered if b not in left and b not in right]
    # Um elemento transversal sobreposto a texto torna a interpretação incerta.
    if any(a.bbox[1] < b.bbox[3] and b.bbox[1] < a.bbox[3]
           for a in spanning for b in left + right):
        return [ordered]
    result = []
    remaining = left + right
    for separator in spanning:
        band = [b for b in remaining if b.bbox[3] <= separator.bbox[1]]
        for column in (left, right):
            group = sorted((b for b in band if b in column), key=lambda b: b.bbox[1])
            if group:
                result.append(group)
        remaining = [b for b in remaining if b not in band]
        result.append([separator])
    for column in (left, right):
        group = sorted((b for b in remaining if b in column), key=lambda b: b.bbox[1])
        if group:
            result.append(group)
    return result
