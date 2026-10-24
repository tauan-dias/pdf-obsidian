"""Widget progress presentation, including a stationary reduced-motion busy state."""
from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QProgressBar

from .tokens import COLORS
from .visuals import visual_settings


class OperationProgress(QProgressBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        visual_settings().reducedMotionChanged.connect(self.update)

    def paintEvent(self, event):
        if not (visual_settings().reducedMotion and self.minimum() == self.maximum() == 0):
            return super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QColor(COLORS['border']))
        painter.setBrush(QColor(COLORS['raised']))
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        painter.drawRoundedRect(rect, 4, 4)
        painter.setBrush(QColor(COLORS['muted']))
        painter.drawRoundedRect(QRectF(rect.left() + 2, rect.top() + 2,
                                      rect.width() * .3, max(1, rect.height() - 4)), 3, 3)
