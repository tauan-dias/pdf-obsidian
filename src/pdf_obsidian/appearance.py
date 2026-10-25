"""Identidade escura e ícones vetoriais locais, sem dependências externas."""
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPalette, QPen, QFontDatabase
from PySide6.QtWidgets import QCheckBox, QStyle, QStyleOptionButton, QLabel, QWidget, QBoxLayout, QApplication


# Semantic tokens shared by widgets, palettes and presentation code.
from .tokens import COLORS, METRICS
from .visuals import tool_icon, load_fonts

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



def apply_theme(window):
    c = COLORS
    interface, mono = load_fonts()
    native = QApplication.font()
    baseline = QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont)
    native_pixels = native.pixelSize() if native.pixelSize() > 0 else native.pointSizeF() * 96 / 72
    baseline_pixels = baseline.pixelSize() if baseline.pixelSize() > 0 else baseline.pointSizeF() * 96 / 72
    scale = max(.75, native_pixels / max(1, baseline_pixels))
    font = window.font()
    font.setFamily(interface)
    font.setPixelSize(round(METRICS['bodySize'] * scale))
    window.setFont(font)
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
        QPushButton, QToolButton, QComboBox, QSpinBox, QDoubleSpinBox, QMenu {{ font-size: {round(METRICS['labelSize'] * scale)}px; }}
        QWidget#previewTools, QWidget#editorTools {{ background: {c['background']}; }}
        QWidget#panel {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 8px; }}
        QWidget#header {{ background: {c['background']}; }}
        QWidget#welcomeCard {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 10px; }}
        QLabel#brand {{ font-size: {round(METRICS['titleSize'] * scale)}px; font-weight: 600; }}
        QLabel#section {{ font-weight: 600; }}
        QLabel#muted {{ color: {c['muted']}; }}
        QLabel#formLabel {{ color: {c['muted']}; font-size: {round(METRICS['labelSize'] * scale)}px; font-weight: 500; }}
        QLabel#eyebrow {{ color: {c['accent']}; font-weight: 600; }}
        QFrame#separator {{ background: {c['border']}; border: 0; }}
        QPushButton {{ background: {c['surface']}; border: 1px solid {c['controlBorder']}; border-radius: 6px; padding: 5px 10px; min-height: 20px; }}
        QToolButton {{ background: transparent; border: 1px solid transparent;
            border-radius: 6px; padding: 5px 8px; min-height: 20px; }}
        QToolButton::menu-indicator {{ image: none; width: 0; }}
        QPushButton#secondary {{ background: {c['raised']}; border-color: {c['controlBorder']}; }}
        QWidget#toolGroup {{ background: {c['surface']}; border: 1px solid {c['controlBorder']}; border-radius: 6px; }}
        QWidget#editorTools QToolButton {{ padding: 3px; background: transparent; border-color: transparent; }}
        QWidget#editorTools QToolButton:hover {{ background: {c['hover']}; border-color: transparent; }}
        QWidget#editorTools QToolButton:focus {{ border: 2px solid {c['accent']}; }}
        QWidget#editorTools QToolButton:disabled {{ border-color: transparent; }}
        QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{ background: {c['raised']};
            border: 1px solid {c['controlBorder']}; border-radius: 6px; padding: 5px 8px; min-height: 20px; }}
        QPushButton:hover, QToolButton:hover {{ background: {c['hover']}; }}
        QPushButton:pressed, QToolButton:pressed {{ background: {c['selection']}; }}
        QPushButton:checked, QToolButton:checked {{ background: {c['selection']}; color: {c['accent']}; }}
        QPushButton:focus, QToolButton:focus, QComboBox:focus, QSpinBox:focus,
        QDoubleSpinBox:focus, QLineEdit:focus, QPlainTextEdit:focus, QTextBrowser:focus,
        QTreeWidget:focus, QListWidget:focus, QCheckBox:focus {{ border: 2px solid {c['accent']}; }}
        QCheckBox:disabled, QLabel:disabled, QPushButton:disabled, QToolButton:disabled {{ color: {c['disabled']}; }}
        QPushButton#primary {{ background: {c['accent']}; color: {c['on_accent']}; font-weight: 600; padding: 4px 14px; border: 2px solid transparent; }}
        QPushButton#primary:hover {{ background: {c['accentHover']}; }}
        QPushButton#primary:pressed {{ background: {c['accentPressed']}; }}
        QPushButton#primary:focus {{ background: {c['background']}; color: {c['text']}; border: 2px solid {c['text']}; }}
        QPushButton#primary:disabled {{ background: {c['raised']}; color: {c['disabled']}; }}
        QPlainTextEdit, QTextBrowser {{ background: {c['canvas']}; border: 1px solid transparent; border-radius: 6px; padding: 16px; }}
        QPlainTextEdit#markdownEditor {{ font-family: "{mono}"; font-size: {round(METRICS["editorSize"] * scale)}px; }}
        QListWidget, QTreeWidget {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 6px; }}
        QListWidget::item {{ padding: 8px; border-radius: 4px; }}
        QTreeWidget {{ alternate-background-color: {c['surface']}; }}
        QTreeWidget::item {{ min-height: 40px; padding: 0 8px; border-bottom: 1px solid {c['border']}; }}
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
        QProgressBar::chunk {{ background: {c['muted']}; border-radius: 4px; }}
        QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
        QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
        QScrollBar::handle {{ background: {c['selection']}; border-radius: 3px; min-height: 28px; min-width: 28px; }}
        QScrollBar::handle:hover {{ background: {c['disabled']}; }}
        QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
        QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
        QCheckBox {{ spacing: 8px; padding: 3px; border: 1px solid transparent; border-radius: 4px; }}
        QCheckBox::indicator {{ width: 14px; height: 14px; border: 1px solid {c['muted']}; border-radius: 3px; background: {c['raised']}; }}
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
