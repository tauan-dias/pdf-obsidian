"""Local presentation resources shared by Quick and Widgets; no document state."""
from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QObject, Property, Signal, Slot, Qt, QEvent
from PySide6.QtGui import QColor, QFontDatabase, QGuiApplication, QImage, QPainter, QIcon, QPixmap
from PySide6.QtQuick import QQuickImageProvider
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication, QStyle, QMessageBox

from .tokens import COLORS

ASSETS = Path(__file__).with_name('assets')
ICON_NAMES = {
    'document': 'file-text', 'stack': 'files', 'open': 'folder-open', 'export': 'folder-output',
    'previous': 'chevron-left', 'next': 'chevron-right', 'chevron': 'chevron-down',
    'minus': 'minus', 'plus': 'plus', 'more': 'ellipsis', 'warning': 'triangle-alert',
    'error': 'circle-x', 'image': 'image', 'check': 'check', 'success': 'circle-check',
    'bold': 'bold', 'italic': 'italic', 'link': 'link', 'bullet': 'list', 'ordered': 'list-ordered',
    'quote': 'quote', 'align': 'text-align-start', 'left': 'text-align-start',
    'center': 'text-align-center', 'right': 'text-align-end', 'justify': 'text-align-justify',
    'undo': 'undo-2', 'redo': 'redo-2', 'close': 'x', 'arrow': 'arrow-right',
    'shield': 'shield-check', 'crop': 'scan', 'fit_page': 'maximize', 'fit_width': 'move-horizontal',
    'hide_pdf': 'panel-left-close', 'show_pdf': 'panel-left-open', 'info': 'info',
    'loading': 'loader-circle', 'remove': 'trash', 'style': 'type',
}


def load_fonts():
    """Register once per application, retaining native fallbacks on resource failure."""
    app = QGuiApplication.instance()
    if hasattr(app, '_pdf_obsidian_fonts'):
        return app._pdf_obsidian_fonts
    for path in sorted((ASSETS / 'fonts').glob('*.ttf')):
        QFontDatabase.addApplicationFont(str(path))
    families = set(QFontDatabase.families())
    native = app.font().family()
    mono = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).family()
    result = ('Geist' if 'Geist' in families else native,
              'Geist Mono' if 'Geist Mono' in families else mono)
    app._pdf_obsidian_fonts = result
    return result


class VisualSettings(QObject):
    reducedMotionChanged = Signal()

    def __init__(self, parent):
        super().__init__(parent)
        self._reduced = (isinstance(parent, QApplication) and
                         parent.style().styleHint(QStyle.StyleHint.SH_Widget_Animation_Duration) == 0)
        parent.installEventFilter(self)

    def eventFilter(self, watched, event):
        # Keep the native message-box behavior, buttons and accessibility intact;
        # replace only its normally colored standard symbol when it is shown.
        if event.type() == QEvent.Type.Show and isinstance(watched, QMessageBox):
            names = {QMessageBox.Icon.Information: 'info', QMessageBox.Icon.Warning: 'warning',
                     QMessageBox.Icon.Critical: 'error', QMessageBox.Icon.Question: 'warning'}
            name = names.get(watched.icon())
            if name:
                watched.setIconPixmap(QPixmap.fromImage(icon_image(name, COLORS['text'], 32, 32)))
        return super().eventFilter(watched, event)

    @Property(bool, notify=reducedMotionChanged)
    def reducedMotion(self):
        return self._reduced

    @Slot(bool)
    def setReducedMotion(self, value):
        if self._reduced != value:
            self._reduced = value
            self.reducedMotionChanged.emit()


def visual_settings():
    app = QGuiApplication.instance()
    if not hasattr(app, '_pdf_obsidian_visuals'):
        app._pdf_obsidian_visuals = VisualSettings(app)
    return app._pdf_obsidian_visuals


@lru_cache(maxsize=256)
def icon_image(name, color, width=40, height=40):
    """Rasterize only bundled SVGs. Cache is bounded and contains no document content."""
    name = ICON_NAMES.get(name, 'file-text')
    svg = (ASSETS / 'icons' / (name + '.svg')).read_bytes()
    svg = svg.replace(b'currentColor', QColor(color).name().encode('ascii'))
    image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    renderer = QSvgRenderer(svg)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    return image


def tool_icon(name, color=None):
    image = icon_image(name, color or COLORS['muted']).copy()
    pixmap = QPixmap.fromImage(image)
    pixmap.setDevicePixelRatio(2)
    return QIcon(pixmap)


class IconProvider(QQuickImageProvider):
    def __init__(self):
        super().__init__(QQuickImageProvider.ImageType.Image)

    def requestImage(self, image_id, size, requested_size):
        name, _, color = image_id.partition('/')
        width = max(1, min(256, requested_size.width() if requested_size.width() > 0 else 40))
        height = max(1, min(256, requested_size.height() if requested_size.height() > 0 else 40))
        tint = QColor('#' + color)
        return icon_image(name, tint.name() if tint.isValid() else COLORS['text'], width, height).copy()


def install_icons(engine):
    engine.addImageProvider('ui', IconProvider())
