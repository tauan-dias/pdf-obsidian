"""Prévia Markdown com seleção visual de incorporações de imagens locais."""
from collections import defaultdict
from pathlib import Path
import posixpath
from urllib.parse import unquote

from PySide6.QtCore import QRectF, Qt, QUrl, Signal
from PySide6.QtGui import QColor, QKeySequence, QPainter, QPen, QShortcut, QTextDocument
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QTextBrowser, QVBoxLayout, QWidget

from .appearance import CheckBox as QCheckBox, COLORS
from .markdown import analyse_markdown


class ImagePreview(QTextBrowser):
    selection_changed = Signal()
    selection_issue = Signal(str)
    remove_requested = Signal()
    undo_requested = Signal()
    redo_requested = Signal()

    def __init__(self):
        super().__init__()
        self.setOpenExternalLinks(False)
        self.setOpenLinks(False)
        self.images = {}
        self.targets = {}
        self.selected_images = set()
        self.interaction_available = False
        self.toolbar = QWidget(self)
        self.toolbar.setAutoFillBackground(True)
        self.toolbar.setObjectName("previewTools")
        layout = QVBoxLayout(self.toolbar)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(4)
        top = QHBoxLayout()
        self.selection_mode = QCheckBox("Selecionar imagens")
        self.selection_mode.setToolTip("Ative e clique nas imagens da prévia para marcar ou desmarcar. Depois, remova as selecionadas.")
        self.selection_count = QLabel("0 selecionadas")
        self.undo_button = QPushButton("Desfazer")
        self.redo_button = QPushButton("Refazer")
        top.addWidget(self.undo_button)
        top.addWidget(self.redo_button)
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        top.addWidget(separator)
        top.addWidget(self.selection_mode)
        top.addStretch()
        top.addWidget(self.selection_count)
        layout.addLayout(top)
        actions = QHBoxLayout()
        self.selection_actions = []
        self.remove_button = QPushButton("Remover selecionadas")
        self.clear_button = QPushButton("Limpar seleção")
        self.undo_button.setToolTip("Desfazer edição (Ctrl+Z)")
        self.redo_button.setToolTip("Refazer edição (Ctrl+Shift+Z ou Ctrl+Y)")
        for button in (self.remove_button, self.clear_button):
            actions.addWidget(button)
            if button in (self.remove_button, self.clear_button):
                self.selection_actions.append(button)
        actions.addStretch()
        layout.addLayout(actions)
        self.selection_mode.toggled.connect(self.mode_changed)
        self.clear_button.clicked.connect(self.clear_image_selection)
        self.remove_button.clicked.connect(self.remove_requested)
        self.undo_button.clicked.connect(self.undo_requested)
        self.redo_button.clicked.connect(self.redo_requested)
        self.shortcuts = []
        for keys, signal in ((("Ctrl+Z",), self.undo_requested),
                             (("Ctrl+Shift+Z", "Ctrl+Y"), self.redo_requested)):
            shortcut = QShortcut(self)
            shortcut.setKeys([QKeySequence(key) for key in keys])
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(signal)
            self.shortcuts.append(shortcut)
        self.position_toolbar()
        self.setMinimumWidth(self.toolbar.minimumSizeHint().width() + self.frameWidth() * 2
                             + self.verticalScrollBar().sizeHint().width())
        self.mode_changed(False)
        self.set_interaction_available(False)
        self.undo_button.setEnabled(False)
        self.redo_button.setEnabled(False)

    def position_toolbar(self):
        if not hasattr(self, "toolbar"):
            return
        height = self.toolbar.sizeHint().height()
        if self.viewportMargins().top() != height:
            self.setViewportMargins(0, height, 0, 0)
        frame = self.frameWidth()
        self.toolbar.setGeometry(frame, frame, max(1, self.viewport().width()), height)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.position_toolbar()

    def configure_images(self, markdown, workspace, assets):
        self.clear_image_selection()
        self.images.clear()
        self.targets.clear()
        analysis = analyse_markdown(markdown, (asset.path for asset in assets))
        source = defaultdict(list)
        for image in analysis.image_occurrences:
            source[image.asset].append(image)
        rendered = defaultdict(list)
        block = self.document().begin()
        while block.isValid():
            it = block.begin()
            while not it.atEnd():
                fragment = it.fragment()
                if fragment.charFormat().isImageFormat():
                    fmt = fragment.charFormat().toImageFormat()
                    url = QUrl(fmt.name())
                    if url.isRelative():
                        asset = posixpath.normpath(unquote(url.path()))
                    elif url.isLocalFile():
                        try:
                            asset = Path(url.toLocalFile()).relative_to(workspace).as_posix()
                        except ValueError:
                            asset = None
                    else:
                        asset = None
                    for position in range(fragment.position(), fragment.position() + fragment.length()):
                        self.images[position] = fmt
                        if asset is not None:
                            rendered[asset].append(position)
                it += 1
            block = block.next()
        for asset, positions in rendered.items():
            # Em caso de divergência entre os parsers, não adivinhar a ocorrência.
            if len(positions) != len(source[asset]):
                continue
            for position, image in zip(positions, source[asset]):
                if image.paragraph is not None:
                    self.targets[position] = (asset, image.occurrence)
        self.viewport().update()

    def set_interaction_available(self, available):
        self.interaction_available = available
        self.selection_mode.setEnabled(available)
        count = len(self.selected_images)
        self.remove_button.setEnabled(available and count > 0)
        self.clear_button.setEnabled(available and count > 0)
        self.selection_count.setText(f"{count} selecionada" if count == 1 else f"{count} selecionadas")

    def mode_changed(self, checked):
        for button in self.selection_actions:
            button.setVisible(checked)
        self.selection_count.setVisible(checked)
        self.toolbar.layout().activate()
        self.position_toolbar()
        if not checked:
            self.clear_image_selection()
        self.viewport().update()

    def clear_image_selection(self):
        if self.selected_images:
            self.selected_images.clear()
            self.set_interaction_available(self.interaction_available)
            self.selection_changed.emit()
        self.viewport().update()

    def image_rect(self, position):
        """Limites reais da imagem em coordenadas do viewport, incluindo rolagem."""
        fmt = self.images.get(position)
        if fmt is None:
            return QRectF()
        block = self.document().findBlock(position)
        layout = block.layout()
        offset = position - block.position()
        line = layout.lineForTextPosition(offset)
        if not line.isValid():
            return QRectF()
        start = line.cursorToX(offset)[0]
        end = line.cursorToX(offset + 1)[0]
        resource = self.document().resource(QTextDocument.ResourceType.ImageResource, QUrl(fmt.name()))
        native_width = resource.width() if hasattr(resource, "width") else 16
        native_height = resource.height() if hasattr(resource, "height") else 16
        width = fmt.width() or native_width
        height = fmt.height() or (native_height * width / max(1, native_width))
        if fmt.height() and not fmt.width():
            width = native_width * height / max(1, native_height)
        if end > start:
            width = end - start
        origin = self.document().documentLayout().blockBoundingRect(block).topLeft()
        return QRectF(origin.x() + start - self.horizontalScrollBar().value(),
                      origin.y() + line.y() + line.ascent() - height - self.verticalScrollBar().value(),
                      width, height)

    def image_at(self, point):
        cursor = self.cursorForPosition(point.toPoint() if hasattr(point, "toPoint") else point)
        for position in (cursor.position(), cursor.position() - 1):
            if position in self.images and self.image_rect(position).contains(point):
                return position
        return None

    def mousePressEvent(self, event):
        if (self.interaction_available and self.selection_mode.isChecked()
                and event.button() == Qt.MouseButton.LeftButton):
            position = self.image_at(event.position())
            if position is not None:
                key = self.targets.get(position)
                if key is None:
                    self.selection_issue.emit("Esta imagem não pôde ser associada a uma incorporação isolada. Você pode removê-la pelo editor Markdown.")
                else:
                    if key in self.selected_images:
                        self.selected_images.remove(key)
                    else:
                        self.selected_images.add(key)
                    self.set_interaction_available(self.interaction_available)
                    self.selection_changed.emit()
                    self.viewport().update()
                event.accept()
                return
        super().mousePressEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.selected_images:
            return
        painter = QPainter(self.viewport())
        color = QColor(COLORS["accent"])
        painter.setPen(QPen(color, 2))
        for number, position in enumerate(sorted(pos for pos, key in self.targets.items()
                                                  if key in self.selected_images), start=1):
            rect = self.image_rect(position)
            if not rect.intersects(QRectF(self.viewport().rect())):
                continue
            painter.drawRect(rect.adjusted(1, 1, -1, -1))
            badge = QRectF(rect.left() + 2, rect.top() + 2, 22, 22)
            painter.fillRect(badge, color)
            painter.setPen(QColor(COLORS["on_accent"]))
            painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, str(number))
            painter.setPen(QPen(color, 2))
        painter.end()
