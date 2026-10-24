"""Tokens locais compartilhados entre os dois adaptadores Qt, sem eval."""
import json
from pathlib import Path

_source = (Path(__file__).parent / 'qml/components/Tokens.js').read_text()
COLORS = json.loads(_source.split('var colors =', 1)[1].split(';', 1)[0])
METRICS = json.loads(_source.split('var metrics =', 1)[1].split(';', 1)[0])

REVIEW_METRICS = json.loads(_source.split('var reviewMetrics =', 1)[1].split(';', 1)[0])
