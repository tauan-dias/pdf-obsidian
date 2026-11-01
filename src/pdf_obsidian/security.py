"""Limites compartilhados para entradas não confiáveis."""
import math

MAX_PIXELS = 24_000_000


def check_raster(width, height, scale):
    values = (width, height, scale)
    if any(not math.isfinite(v) or v <= 0 for v in values):
        raise ValueError('Dimensões de imagem inválidas.')
    # Rasterizadores arredondam cada borda para fora.
    if (math.ceil(width * scale) + 2) * (math.ceil(height * scale) + 2) > MAX_PIXELS:
        raise ValueError('Imagem excede o limite seguro de 24 milhões de pixels.')
