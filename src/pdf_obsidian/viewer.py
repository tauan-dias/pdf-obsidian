"""Controles e geometria do visualizador, sem acesso direto ao PDF."""
from PySide6.QtCore import QEvent, QRect, QSize, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDoubleSpinBox, QHBoxLayout, QLabel, QPushButton, QRubberBand,
    QScrollArea, QSpinBox, QVBoxLayout, QWidget,
)


from .appearance import tool_icon, COLORS


class PageView(QLabel):
    selected = Signal(tuple)

    def __init__(self):
        super().__init__(f"<div style='font-size:20px;color:{COLORS['text']};'>Seu PDF começa aqui</div>"
                         "<br>Abra um documento para comparar o original<br>com o Markdown, lado a lado.")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.band = QRubberBand(QRubberBand.Shape.Rectangle, self)
        self.original = None
        self.page_rect = None
        self.origin = None
        self.selection_enabled = False
        self.setMinimumSize(1, 1)

    def set_selection_enabled(self, enabled):
        self.selection_enabled = enabled
        if not enabled:
            self.origin = None
            self.band.hide()

    def clear_page(self):
        self.original = self.page_rect = self.origin = None
        self.band.hide()
        self.clear()
        self.setText("Carregando página…")

    def show_page(self, path, rect, size=None):
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            raise ValueError("Não foi possível carregar a imagem da página.")
        self.original = pixmap
        self.page_rect = rect
        self.resize_image(size or pixmap.size())

    def resize_image(self, size: QSize):
        if self.original is None:
            return
        self.band.hide()
        self.origin = None
        self.setPixmap(self.original.scaled(
            size, Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        ))
        # O widget coincide com a imagem. A centralização pertence ao QScrollArea,
        # para que margens externas nunca sejam interpretadas como conteúdo do PDF.
        self.setFixedSize(size)

    def selection_bbox(self, selection: QRect):
        rect = selection.normalized().intersected(self.rect())
        if self.page_rect is None or rect.width() < 5 or rect.height() < 5:
            return None
        x0, y0, x1, y1 = self.page_rect
        sx, sy = (x1 - x0) / self.width(), (y1 - y0) / self.height()
        return (x0 + rect.x() * sx, y0 + rect.y() * sy,
                x0 + (rect.x() + rect.width()) * sx,
                y0 + (rect.y() + rect.height()) * sy)

    def mousePressEvent(self, event):
        if (self.selection_enabled and self.original is not None
                and event.button() == Qt.MouseButton.LeftButton):
            self.setFocus()
            self.origin = event.position().toPoint()
            self.band.setGeometry(QRect(self.origin, self.origin))
            self.band.show()

    def mouseMoveEvent(self, event):
        if self.origin is not None:
            self.band.setGeometry(QRect(self.origin, event.position().toPoint()).normalized())

    def mouseReleaseEvent(self, event):
        if self.origin is None or event.button() != Qt.MouseButton.LeftButton:
            return
        selection = QRect(self.origin, event.position().toPoint()).normalized()
        self.band.hide()
        self.origin = None
        bbox = self.selection_bbox(selection)
        if bbox is not None:
            self.selected.emit(bbox)


class PageScrollArea(QScrollArea):
    viewport_resized = Signal()

    def __init__(self):
        super().__init__()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.viewport().installEventFilter(self)

    def eventFilter(self, watched, event):
        if watched is self.viewport() and event.type() == QEvent.Type.Resize:
            self.viewport_resized.emit()
        return super().eventFilter(watched, event)


class PDFPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("panel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        title = QLabel("PDF original")
        title.setObjectName("section")
        layout.addWidget(title)
        navigation = QHBoxLayout()
        self.previous = QPushButton()
        self.previous.setIcon(tool_icon("previous"))
        self.next = QPushButton()
        self.next.setIcon(tool_icon("next"))
        self.page_number = QSpinBox()
        self.page_number.setAccessibleName("Página do PDF")
        self.page_number.setPrefix("Página ")
        self.page_number.setSuffix(" de 0")
        self.page_number.setKeyboardTracking(False)
        self.page_number.setToolTip("Ir à página: digite o número e confirme com Enter.")
        self.previous.setToolTip("Página anterior (Alt+Esquerda)")
        self.next.setToolTip("Próxima página (Alt+Direita)")
        for widget in (self.previous, self.page_number, self.next):
            navigation.addWidget(widget)
        navigation.addStretch()
        layout.addLayout(navigation)
        zoom = QHBoxLayout()
        self.zoom_out = QPushButton()
        self.zoom_out.setIcon(tool_icon("minus"))
        self.zoom_out.setAccessibleName("Diminuir zoom")
        self.zoom_in = QPushButton()
        self.zoom_in.setIcon(tool_icon("plus"))
        self.zoom_in.setAccessibleName("Aumentar zoom")
        self.zoom_out.setFixedWidth(34)
        self.zoom_in.setFixedWidth(34)
        self.zoom = QDoubleSpinBox()
        self.zoom.setMinimumWidth(90)
        self.zoom.setAccessibleName("Zoom do PDF")
        # Ajustes automáticos podem ficar fora da faixa do zoom manual.
        self.zoom.setRange(.1, 10000)
        self.zoom.setDecimals(1)
        self.zoom.setSingleStep(25)
        self.zoom.setValue(100)
        self.zoom.setSuffix("%")
        self.zoom.setKeyboardTracking(False)
        self.zoom.setToolTip("Zoom manual: 25% a 300%, relativo a 100 dpi.")
        self.fit_width = QPushButton("↔")
        self.fit_page = QPushButton()
        self.fit_width.setText("")
        self.fit_width.setIcon(tool_icon("fit_width"))
        self.fit_page.setIcon(tool_icon("fit_page"))
        for button in (self.fit_width, self.fit_page):
            button.setCheckable(True)
        self.zoom_out.setToolTip("Diminuir zoom (Ctrl+− no painel do PDF)")
        self.zoom_in.setToolTip("Aumentar zoom (Ctrl++ no painel do PDF)")
        self.fit_page.setToolTip("Ajustar à página")
        self.previous.setAccessibleName("Página anterior")
        self.next.setAccessibleName("Próxima página")
        self.fit_page.setAccessibleName("Ajustar à página")
        self.fit_width.setAccessibleName("Ajustar à largura")
        self.fit_width.setToolTip("Ajustar à largura (Ctrl+0 no painel do PDF)")
        for widget in (self.zoom_out, self.zoom, self.zoom_in, self.fit_width, self.fit_page):
            zoom.addWidget(widget)
        zoom.addStretch()
        layout.addLayout(zoom)
        self.page_view = PageView()
        hint = QLabel("Arraste uma região para inserir um recorte no editor.")
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        self.scroll = PageScrollArea()
        self.scroll.setObjectName("pdfCanvas")
        self.scroll.setWidget(self.page_view)
        self.scroll.setWidgetResizable(True)
        layout.addWidget(self.scroll, 1)
        layout.addWidget(hint)
