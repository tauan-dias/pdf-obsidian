"""Revisão e restauração das figuras omitidas pelo filtro de margens."""
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QListWidget,
                              QListWidgetItem, QLabel, QPushButton, QDialogButtonBox)

from .restoration import restoration_edit

class FilteredImagesDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.setPalette(window.palette())
        self.setAutoFillBackground(True)
        self.window = window
        self.setWindowTitle('Imagens filtradas')
        self.resize(660, 480)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        title = QLabel("Revisar imagens filtradas")
        title.setObjectName("section")
        layout.addWidget(title)
        description = QLabel('Elementos recorrentes nas margens foram omitidos.\nRestaurar insere a figura ao final do trecho da página, antes do próximo marcador.')
        description.setWordWrap(True)
        layout.addWidget(description)
        self.items = QListWidget()
        self.items.setAccessibleName("Imagens recorrentes omitidas nas margens")
        self.items.setIconSize(QSize(120, 64))
        self.items.setSpacing(6)
        self.items.setWordWrap(True)
        for item in window.result.filtered_images:
            pixmap = QPixmap(str(window.result.workspace / item.asset))
            thumbnail = pixmap.scaled(120, 64, Qt.AspectRatioMode.KeepAspectRatio,
                                      Qt.TransformationMode.SmoothTransformation)
            row = QListWidgetItem(QIcon(thumbnail), f'Página {item.page} — {item.reason}')
            row.setData(Qt.ItemDataRole.UserRole, item)
            row.setSizeHint(QSize(540, 84))
            self.items.addItem(row)
        layout.addWidget(self.items, 1)
        self.message = QLabel()
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        actions = QHBoxLayout()
        self.show_page = QPushButton('Mostrar no PDF')
        self.restore = QPushButton('Restaurar imagem')
        self.restore.setObjectName('primary')
        actions.addWidget(self.show_page)
        actions.addStretch()
        actions.addWidget(self.restore)
        layout.addLayout(actions)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.button(QDialogButtonBox.StandardButton.Close).setText("Fechar")
        close.rejected.connect(self.reject)
        layout.addWidget(close)
        self.show_page.clicked.connect(self.navigate)
        self.restore.clicked.connect(self.restore_current)
        self.items.currentRowChanged.connect(self.refresh)
        window.editor.textChanged.connect(self.refresh)
        self.finished.connect(lambda _: window.editor.textChanged.disconnect(self.refresh))
        self.items.setCurrentRow(0)
        self.refresh()

    def current(self):
        item = self.items.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def refresh(self, *_):
        item = self.current()
        available = item is not None and self.window.result is not None and self.window.operation in (None, 'render')
        self.show_page.setEnabled(available)
        if not available:
            self.restore.setEnabled(False)
            return
        try:
            restoration_edit(self.window.result, self.window.editor.toPlainText(), item)
        except ValueError as exc:
            self.message.setText(str(exc))
            self.restore.setEnabled(False)
        else:
            self.message.setText('A restauração pode ser desfeita e refeita no editor.')
            self.restore.setEnabled(True)

    def navigate(self):
        item = self.current()
        if item and self.window.operation in (None, 'render'):
            self.window.set_pdf_visible(True)
            self.window.request_page(item.page)

    def restore_current(self):
        item = self.current()
        if item:
            try:
                self.window.restore_filtered_image(item)
            except ValueError as exc:
                self.message.setText(str(exc))
            self.refresh()
