"""Identidade escura e ícones vetoriais locais, sem dependências externas."""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPalette, QPen, QPixmap
from PySide6.QtWidgets import QCheckBox, QStyle, QStyleOptionButton, QLabel, QWidget, QBoxLayout


# Semantic tokens shared by widgets, palettes and presentation code.
from .tokens import COLORS, METRICS

SPACING = tuple(METRICS["spacing"])
CONTROL_HEIGHT = METRICS["controlHeight"]


class AdaptiveRow(QWidget):
    """Reflow groups without recreating controls or losing their state."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.row = QBoxLayout(QBoxLayout.Direction.LeftToRight, self)
        self.row.setContentsMargins(0, 0, 0, 0)
        self.row.setSpacing(8)

    def minimumSizeHint(self):
        size = super().minimumSizeHint()
        widths = [self.row.itemAt(i).widget().minimumSizeHint().width()
                  for i in range(self.row.count())
                  if self.row.itemAt(i).widget() is not None
                  and not self.row.itemAt(i).widget().isHidden()]
        size.setWidth(max(widths, default=0))
        return size

    def resizeEvent(self, event):
        super().resizeEvent(event)
        widgets = [self.row.itemAt(i).widget() for i in range(self.row.count())]
        visible = [w for w in widgets if w is not None and not w.isHidden()]
        needed = sum(w.minimumSizeHint().width() for w in visible) + max(0, len(visible) - 1) * self.row.spacing()
        direction = (QBoxLayout.Direction.TopToBottom if self.width() < needed
                     else QBoxLayout.Direction.LeftToRight)
        if self.row.direction() != direction:
            self.row.setDirection(direction)


class ElidedLabel(QLabel):
    """Keep the accessible full title while drawing within available space."""
    def minimumSizeHint(self):
        size = super().minimumSizeHint()
        size.setWidth(0)
        return size

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setFont(self.font())
        painter.setPen(self.palette().color(QPalette.ColorRole.WindowText))
        painter.drawText(self.contentsRect(), Qt.AlignmentFlag.AlignVCenter,
                         self.fontMetrics().elidedText(self.text(), Qt.TextElideMode.ElideMiddle,
                                                       self.contentsRect().width()))


class CheckBox(QCheckBox):
    """Indicador com marca explícita sobre a superfície escura."""
    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.isChecked():
            return
        option = QStyleOptionButton()
        self.initStyleOption(option)
        rect = self.style().subElementRect(QStyle.SubElement.SE_CheckBoxIndicator, option, self)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(COLORS["on_accent"]), 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(QPointF(rect.left() + 3, rect.top() + 7), QPointF(rect.left() + 6, rect.top() + 10))
        painter.drawLine(QPointF(rect.left() + 6, rect.top() + 10), QPointF(rect.left() + 11, rect.top() + 4))
        painter.end()


def tool_icon(name, color=None):
    """Ícones de traço uniforme, desenhados em alta densidade pelo Qt."""
    color = color or COLORS["muted"]
    pixmap = QPixmap(40, 40)
    pixmap.setDevicePixelRatio(2)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor(color), 1.5, Qt.PenStyle.SolidLine,
                        Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))

    def line(x1, y1, x2, y2):
        painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))

    if name in ("left", "center", "right", "justify"):
        for index, y in enumerate((4, 8, 12, 16)):
            width = 14 if index % 2 == 0 or name == "justify" else 9
            x = 3 if name in ("left", "justify") else (17 - width if name == "right" else (20 - width) / 2)
            line(x, y, x + width, y)
    elif name in ("bullet", "ordered"):
        for index, y in enumerate((5, 10, 15)):
            line(8, y, 17, y)
            if name == "bullet":
                painter.drawEllipse(QPointF(3.5, y), .7, .7)
            else:
                font = painter.font()
                font.setPixelSize(6)
                painter.setFont(font)
                painter.drawText(QRectF(1, y - 4, 5, 7), Qt.AlignmentFlag.AlignCenter, str(index + 1))
    elif name == "quote":
        for x in (3, 11):
            painter.drawRoundedRect(QRectF(x, 4, 5, 6), 1, 1)
            line(x + 5, 10, x + 1, 15)
    elif name == "link":
        painter.save()
        painter.translate(10, 10)
        painter.rotate(-40)
        painter.drawRoundedRect(QRectF(-3, -8, 6, 9), 3, 3)
        painter.drawRoundedRect(QRectF(-3, -1, 6, 9), 3, 3)
        painter.restore()
    elif name == "open":
        line(3, 7, 3, 4)
        line(3, 4, 8, 4)
        line(8, 4, 10, 7)
        line(10, 7, 17, 7)
        line(17, 7, 17, 9)
        painter.drawPolygon([QPointF(2, 9), QPointF(18, 9), QPointF(15, 16), QPointF(4, 16)])
    elif name == "export":
        line(10, 3, 10, 12)
        line(6, 7, 10, 3)
        line(14, 7, 10, 3)
        line(3, 12, 3, 17)
        line(3, 17, 17, 17)
        line(17, 17, 17, 12)
    elif name in ("previous", "next"):
        x, tip = (12, 7) if name == "previous" else (8, 13)
        line(x, 4, tip, 10)
        line(tip, 10, x, 16)
    elif name == "more":
        for x in (4, 10, 16):
            painter.drawEllipse(QPointF(x, 10), .7, .7)
    elif name == "document":
        painter.drawRoundedRect(QRectF(4, 2, 12, 16), 1, 1)
        for y in (7, 11, 15):
            line(7, y, 13, y)
    elif name in ("fit_width", "fit_page"):
        painter.drawRoundedRect(QRectF(4, 3, 12, 14), 1, 1)
        if name == "fit_width":
            line(1, 10, 19, 10)
            line(1, 10, 4, 7)
            line(1, 10, 4, 13)
            line(19, 10, 16, 7)
            line(19, 10, 16, 13)
        else:
            painter.drawRect(QRectF(7, 6, 6, 8))
    painter.end()
    return QIcon(pixmap)


def apply_theme(window):
    c = COLORS
    palette = QPalette()
    roles = {
        QPalette.Window: "background", QPalette.Base: "surface",
        QPalette.AlternateBase: "raised", QPalette.Button: "surface",
        QPalette.WindowText: "text", QPalette.Text: "text", QPalette.ButtonText: "text",
        QPalette.Highlight: "selection", QPalette.HighlightedText: "text",
        QPalette.Link: "accent", QPalette.ToolTipBase: "raised", QPalette.ToolTipText: "text",
        QPalette.PlaceholderText: "muted",
    }
    for role, token in roles.items():
        palette.setColor(role, QColor(c[token]))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        palette.setColor(QPalette.Disabled, role, QColor(c["disabled"]))
    window.setPalette(palette)
    window.setStyleSheet(f"""
        QMainWindow, QDialog {{ background: {c['background']}; }}
        QWidget {{ color: {c['text']}; }}
        QWidget#previewTools, QWidget#editorTools {{ background: {c['surface']}; }}
        QWidget#panel {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 8px; }}
        QWidget#header {{ background: {c['background']}; }}
        QWidget#welcomeCard {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 10px; }}
        QLabel#brand {{ font-size: 24px; font-weight: 600; }}
        QLabel#section {{ font-weight: 600; }}
        QLabel#muted {{ color: {c['muted']}; }}
        QLabel#eyebrow {{ color: {c['accent']}; font-weight: 600; }}
        QFrame#separator {{ background: {c['border']}; border: 0; }}
        QPushButton, QToolButton {{ background: transparent; border: 1px solid transparent;
            border-radius: 6px; padding: 5px 8px; min-height: 20px; }}
        QPushButton#secondary {{ background: {c['raised']}; border-color: {c['border']}; }}
        QWidget#editorTools QToolButton {{ padding: 3px; }}
        QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{ background: {c['raised']};
            border: 1px solid {c['border']}; border-radius: 6px; padding: 5px 8px; min-height: 20px; }}
        QPushButton:hover, QToolButton:hover {{ background: {c['hover']}; }}
        QPushButton:pressed, QToolButton:pressed {{ background: {c['selection']}; }}
        QPushButton:checked, QToolButton:checked {{ background: {c['selection']}; color: {c['accent']}; }}
        QPushButton:focus, QToolButton:focus, QComboBox:focus, QSpinBox:focus,
        QDoubleSpinBox:focus, QLineEdit:focus, QPlainTextEdit:focus, QTextBrowser:focus,
        QTreeWidget:focus, QListWidget:focus, QCheckBox:focus {{ border: 1px solid {c['accent']}; }}
        QCheckBox:disabled, QLabel:disabled, QPushButton:disabled, QToolButton:disabled {{ color: {c['disabled']}; }}
        QPushButton#primary {{ background: {c['accent']}; color: {c['on_accent']}; font-weight: 600; padding: 7px 14px; }}
        QPushButton#primary:hover {{ background: #ff9286; }}
        QPushButton#primary:pressed {{ background: #e66c5f; }}
        QPushButton#primary:focus {{ border: 1px solid {c['text']}; }}
        QPushButton#primary:disabled {{ background: {c['raised']}; color: {c['disabled']}; }}
        QPlainTextEdit, QTextBrowser {{ background: {c['canvas']}; border: 1px solid transparent; border-radius: 6px; padding: 16px; }}
        QPlainTextEdit#markdownEditor {{ font-family: monospace; }}
        QListWidget, QTreeWidget {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 6px; }}
        QListWidget::item {{ padding: 8px; border-radius: 4px; }}
        QTreeWidget {{ alternate-background-color: {c['raised']}; }}
        QTreeWidget::item {{ min-height: 36px; padding: 0 8px; }}
        QListWidget::item:hover, QTreeWidget::item:hover {{ background: {c['hover']}; }}
        QListWidget::item:selected, QTreeWidget::item:selected {{ background: {c['selection']}; color: {c['text']}; }}
        QHeaderView::section {{ background: {c['raised']}; color: {c['muted']}; border: 0;
            border-bottom: 1px solid {c['border']}; padding: 10px 8px; }}
        QTabWidget::pane {{ border: 0; padding-top: 8px; }}
        QTabBar::tab {{ padding: 8px 14px; margin-right: 4px; color: {c['muted']}; border-bottom: 2px solid transparent; }}
        QTabBar::tab:selected {{ color: {c['text']}; border-bottom-color: {c['accent']}; }}
        QTabBar::tab:hover {{ background: {c['hover']}; }}
        QTabBar::tab:focus {{ border-bottom-color: {c['accent']}; }}
        QSplitter::handle {{ background: {c['background']}; }}
        QSplitter::handle:hover {{ background: {c['border']}; }}
        QScrollArea#pdfCanvas {{ background: {c['canvas']}; border: 0; border-radius: 6px; }}
        QScrollArea#pdfCanvas > QWidget > QLabel {{ background: {c['canvas']}; color: {c['muted']}; }}
        QProgressBar {{ background: {c['raised']}; color: {c['text']}; border: 1px solid {c['border']};
            border-radius: 5px; text-align: center; min-height: 20px; max-height: 24px; }}
        QProgressBar::chunk {{ background: {c['selection']}; border-radius: 4px; }}
        QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
        QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
        QScrollBar::handle {{ background: #50535b; border-radius: 3px; min-height: 28px; min-width: 28px; }}
        QScrollBar::handle:hover {{ background: #737782; }}
        QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
        QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
        QCheckBox {{ spacing: 8px; padding: 3px; border: 1px solid transparent; border-radius: 4px; }}
        QCheckBox::indicator {{ width: 14px; height: 14px; border: 1px solid #858995; border-radius: 3px; background: {c['raised']}; }}
        QCheckBox::indicator:disabled {{ background: {c['raised']}; border-color: {c['border']}; }}
        QCheckBox::indicator:checked {{ background: {c['accent']}; border-color: {c['accent']}; image: none; }}
        QToolButton#warningsToggle {{ color: {c['muted']}; text-align: left; }}
        QToolButton#warningsToggle:checked {{ color: {c['text']}; background: {c['raised']}; }}
        QMenu {{ background: {c['raised']}; border: 1px solid {c['border']}; border-radius: 8px; padding: 6px; }}
        QMenu::item {{ padding: 7px 24px 7px 12px; border-radius: 4px; }}
        QMenu::item:selected {{ background: {c['hover']}; }}
        QMenu::item:disabled {{ color: {c['disabled']}; }}
        QMenu::separator {{ height: 1px; background: {c['border']}; margin: 4px; }}
        QToolTip {{ color: {c['text']}; background: {c['raised']}; border: 1px solid {c['border']}; padding: 6px; }}
        QStatusBar {{ color: {c['muted']}; }}
    """)
