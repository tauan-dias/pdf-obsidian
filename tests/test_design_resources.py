"""Offline asset packaging and shared icon rendering regressions."""
import hashlib
import json

from PySide6.QtCore import QSize
from PySide6.QtGui import QFontDatabase

from pdf_obsidian.tokens import COLORS
from pdf_obsidian.visuals import ASSETS, ICON_NAMES, IconProvider, icon_image, load_fonts


def test_bundled_assets_match_recorded_versions_and_hashes():
    manifest = json.loads((ASSETS / 'manifest.json').read_text())
    files = {str(p.relative_to(ASSETS)) for p in ASSETS.rglob('*') if p.is_file() and p.name != 'manifest.json'}
    assert files == set(manifest['sha256'])
    for name, digest in manifest['sha256'].items():
        assert hashlib.sha256((ASSETS / name).read_bytes()).hexdigest() == digest
    assert 'SIL OPEN FONT LICENSE' in (ASSETS / 'fonts/OFL.txt').read_text()
    assert 'ISC License' in (ASSETS / 'icons/LICENSE').read_text()


def test_offline_fonts_have_required_weights_and_italics(app):
    assert load_fonts() == ('Geist', 'Geist Mono')
    for family in load_fonts():
        styles = QFontDatabase.styles(family)
        assert any('Italic' in style for style in styles)
        assert any('Medium' in style for style in styles)
        assert any('SemiBold' in style for style in styles)


def test_all_shared_icons_render_in_requested_monochrome_color(app):
    for name in ICON_NAMES:
        image = icon_image(name, '#f5f5f5', 40, 40)
        assert not image.isNull()
        pixels = [image.pixelColor(x, y) for y in range(40) for x in range(40)]
        opaque = [p for p in pixels if p.alpha() > 240]
        assert opaque, name
        assert all(p.red() == p.green() == p.blue() for p in opaque), name
    result = IconProvider().requestImage('link/f5f5f5', QSize(), QSize(36, 36))
    assert result.size() == QSize(36, 36)


def test_control_indicators_meet_non_text_contrast():
    def luminance(value):
        channel = int(value[1:3], 16) / 255
        return channel / 12.92 if channel <= .04045 else ((channel + .055) / 1.055) ** 2.4
    for background in ('background', 'surface'):
        assert (luminance(COLORS['controlBorder']) + .05) / (luminance(COLORS[background]) + .05) >= 3


def test_widgets_standard_message_icons_are_monochrome_without_changing_buttons(app):
    from PySide6.QtWidgets import QMessageBox
    from pdf_obsidian.visuals import visual_settings
    visual_settings()
    for kind in (QMessageBox.Icon.Information, QMessageBox.Icon.Warning, QMessageBox.Icon.Critical, QMessageBox.Icon.Question):
        box = QMessageBox(kind, 'Estado sintético', 'Mensagem preservada.', QMessageBox.StandardButton.Ok)
        button = box.button(QMessageBox.StandardButton.Ok)
        try:
            box.show()
            app.processEvents()
            image = box.iconPixmap().toImage()
            assert not image.isNull()
            assert box.button(QMessageBox.StandardButton.Ok) is button
            assert box.text() == 'Mensagem preservada.'
            pixels = [image.pixelColor(x, y) for x in range(image.width()) for y in range(image.height())]
            assert any(p.alpha() > 0 for p in pixels)
            assert all(p.red() == p.green() == p.blue() for p in pixels if p.alpha() > 240)
        finally:
            box.close()
            box.deleteLater()
