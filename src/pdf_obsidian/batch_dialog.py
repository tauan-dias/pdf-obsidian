"""Preparação e resumo do lote, com acesso à revisão no editor existente."""
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QSignalBlocker
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                              QTreeWidget, QTreeWidgetItem, QHeaderView, QFileDialog,
                              QProgressBar, QMessageBox, QWidget)

from .appearance import AdaptiveRow, COLORS


class BatchDialog(QDialog):
    def __init__(self, window, preparing=False):
        super().__init__(window)
        self.window = window
        self.batch = window.batch
        self.preparing = preparing
        self.paths = []
        self.refreshing = False
        self.rows = {}
        self.setWindowTitle('Converter em lote' if preparing else 'Documentos e resumo do lote')
        self.setWindowModality(Qt.WindowModal)
        self.setPalette(window.palette())
        self.setAutoFillBackground(True)
        self.resize(880, 580)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        self.title = QLabel("Preparar conversão" if preparing else "Documentos da sessão")
        self.title.setObjectName("brand")
        layout.addWidget(self.title)
        self.description = QLabel('Selecione os PDFs. A conversão não exporta arquivos; você poderá revisar os resultados antes de salvar.')
        self.description.setWordWrap(True)
        layout.addWidget(self.description)
        self.tree = QTreeWidget()
        self.tree.setAccessibleName("Documentos e estados da conversão")
        self.tree.setAlternatingRowColors(True)
        self.tree.setHeaderLabels(['Documento', 'Estado', 'Avisos'])
        self.tree.header().setStretchLastSection(False)
        self.tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.tree.setColumnWidth(1, 240)
        self.tree.setRootIsDecorated(False)
        layout.addWidget(self.tree, 1)
        self.details = QLabel()
        self.details.setWordWrap(True)
        self.details.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.details)
        self.progress = QProgressBar()
        layout.addWidget(self.progress)
        self.message = QLabel()
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        footer = AdaptiveRow()
        row = footer.row
        self.add = QPushButton('Adicionar PDFs…')
        self.remove = QPushButton('Remover da lista')
        self.review = QPushButton('Revisar')
        self.start = QPushButton('Iniciar conversão')
        self.start.setObjectName('primary')
        self.export = QPushButton('Exportar selecionados…')
        self.export.setObjectName('primary')
        self.cancel = QPushButton('Cancelar')
        self.close_button = QPushButton('Fechar')
        secondary = QHBoxLayout()
        primary = QHBoxLayout()
        for button in (self.add, self.remove, self.review):
            secondary.addWidget(button)
        for button in (self.cancel, self.close_button, self.start, self.export):
            primary.addWidget(button)
        for group in (secondary, primary):
            container = QWidget()
            container.setLayout(group)
            group.setContentsMargins(0, 0, 0, 0)
            row.addWidget(container)
        self.details.setObjectName("muted")
        self.add.setObjectName("secondary")
        layout.addWidget(footer)
        self.add.clicked.connect(self.add_files)
        self.remove.clicked.connect(self.remove_current)
        self.review.clicked.connect(self.review_current)
        self.start.clicked.connect(self.start_batch)
        self.export.clicked.connect(self.export_selected)
        self.cancel.clicked.connect(self.batch.cancel)
        self.close_button.clicked.connect(self.reject)
        self.tree.itemChanged.connect(self.item_changed)
        self.tree.itemSelectionChanged.connect(self.update_details)
        self.tree.itemDoubleClicked.connect(lambda *_: self.review_current())
        self.batch.progress_changed.connect(self.update_progress)
        self.refresh()

    def add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, 'Adicionar PDFs ao lote', '', 'PDF (*.pdf *.PDF)')
        self.paths = list(dict.fromkeys([*self.paths, *(str(Path(path).resolve()) for path in paths)]))
        self.refresh()

    def current_id(self):
        row = self.tree.currentItem()
        return row.data(0, Qt.UserRole) if row else None

    def remove_current(self):
        key = self.current_id()
        if self.preparing:
            if key in self.paths:
                self.paths.remove(key)
        elif not self.batch.running:
            for item in self.batch.items:
                if item.id == key:
                    item.included = False
        self.refresh()

    def start_batch(self):
        if self.batch.start(self.paths):
            self.preparing = False
            self.setWindowTitle('Documentos e resumo do lote')
            self.refresh()

    def review_current(self):
        if self.batch.running or self.preparing:
            return
        key = self.current_id()
        session = next((item.session for item in self.batch.items if item.id == key), None)
        if session is None:
            session = self.window.sessions.get(key)
        if session:
            self.accept()
            self.window.activate_session(session.id)
            self.window.activateWindow()
            self.window.editor.setFocus()

    def export_selected(self):
        vault = QFileDialog.getExistingDirectory(self, 'Escolher pasta do vault para os documentos selecionados')
        if vault:
            try:
                self.batch.export_selected(vault)
            except ValueError as exc:
                QMessageBox.critical(self, 'Não foi possível exportar', str(exc))
        self.refresh()

    def item_changed(self, row, column):
        if self.refreshing or self.batch.running or self.preparing or column != 0:
            return
        key = row.data(0, Qt.UserRole)
        for item in self.batch.items:
            if item.id == key and item.session:
                item.included = row.checkState(0) == Qt.Checked
        # Atualizar os controles depois de concluir a interação do checkbox.
        QTimer.singleShot(0, self, self.refresh)

    def refresh(self):
        if self.refreshing:
            return
        self.refreshing = True
        try:
            with QSignalBlocker(self.tree):
                self.refresh_rows()
            self.refresh_controls()
        finally:
            self.refreshing = False
        self.update_details()

    def refresh_rows(self):
        if self.preparing:
            rows = [(path, Path(path).name, 'Pendente', '', None) for path in self.paths]
        else:
            rows = []
            batch_sessions = {item.session.id for item in self.batch.items if item.session}
            for item in self.batch.items:
                state = item.status
                if item.session and item.session.document.isModified():
                    state += ' · Não salvo'
                if item.export_status:
                    state += ' · ' + item.export_status
                rows.append((item.id, item.source.name, state,
                             str(len(item.session.result.warnings)) if item.session else '', item))
            for session in self.window.sessions.values():
                if session.id not in batch_sessions:
                    state = 'Fora do lote' + (' · Não salvo' if session.document.isModified() else '')
                    rows.append((session.id, session.result.source.name, state,
                                 str(len(session.result.warnings)), None))
        keys = {key for key, *_ in rows}
        for key in self.rows.keys() - keys:
            row = self.rows.pop(key)
            self.tree.takeTopLevelItem(self.tree.indexOfTopLevelItem(row))
        for index, (key, name, state, warnings, item) in enumerate(rows):
            row = self.rows.get(key)
            if row is None:
                row = QTreeWidgetItem()
                row.setData(0, Qt.UserRole, key)
                self.rows[key] = row
                self.tree.insertTopLevelItem(index, row)
            elif self.tree.indexOfTopLevelItem(row) != index:
                self.tree.takeTopLevelItem(self.tree.indexOfTopLevelItem(row))
                self.tree.insertTopLevelItem(index, row)
            for column, value in enumerate((name, state, warnings)):
                row.setText(column, value)
            source = item.source if item else self.window.sessions[key].result.source if key in self.window.sessions else key
            row.setToolTip(0, str(source))
            row.setToolTip(1, state + ('\n' + item.message if item and item.message else ''))
            failed = item and (item.status == 'Falhou' or item.export_status == 'Falhou')
            row.setForeground(1, QBrush(QColor(COLORS['accent'])) if failed else QBrush())
            flags = row.flags() & ~Qt.ItemIsUserCheckable
            if item and item.session and not self.batch.running:
                flags |= Qt.ItemIsUserCheckable
            if flags != row.flags():
                row.setFlags(flags)
            if item and item.session:
                row.setCheckState(0, Qt.Checked if item.included else Qt.Unchecked)
            else:
                row.setData(0, Qt.CheckStateRole, None)
        if self.tree.currentItem() is None and self.tree.topLevelItemCount():
            self.tree.setCurrentItem(self.tree.topLevelItem(0))

    def refresh_controls(self):
        running = self.batch.running
        if self.preparing:
            description = 'Selecione os PDFs. A conversão não exporta arquivos; você poderá revisar os resultados antes de salvar.'
        elif running:
            description = ('Aguarde a conversão para revisar os documentos. Nenhum arquivo será exportado nesta etapa.'
                           if self.batch.mode == 'convert' else 'Salvando os documentos selecionados. As edições serão preservadas se houver uma falha.')
        else:
            description = 'Marque os documentos para exportar. Desmarcar preserva a conversão e as edições. Selecione um arquivo e clique em Revisar.'
        self.title.setText("Preparar conversão" if self.preparing else
                           "Convertendo documentos" if running and self.batch.mode == 'convert' else
                           "Exportando documentos" if running else "Revisar e exportar")
        self.description.setText(description)
        self.add.setVisible(self.preparing)
        self.start.setVisible(self.preparing)
        self.start.setEnabled(bool(self.paths) and not self.window.busy)
        self.add.setEnabled(not running)
        self.remove.setText('Remover da lista' if self.preparing else 'Excluir da exportação')
        self.remove.setEnabled(not running and bool(self.current_id()))
        self.review.setVisible(not self.preparing)
        self.export.setVisible(not self.preparing)
        count = sum(bool(item.session and item.included) for item in self.batch.items)
        self.export.setText(f'Exportar selecionados ({count})…')
        self.export.setEnabled(count > 0 and not self.window.busy and self.window.worker.is_alive())
        self.cancel.setVisible(running)
        self.cancel.setEnabled(not self.batch.cancel_requested)
        self.close_button.setEnabled(not running)
        self.progress.setVisible(running)
        self.update_progress()
        self.message.setText(self.batch.message if not self.preparing else f'{len(self.paths)} arquivo(s) selecionado(s).')

    def update_progress(self):
        current, total = self.batch.progress
        self.progress.setRange(0, total)
        self.progress.setValue(current)

    def update_details(self):
        if self.refreshing:
            return
        key = self.current_id()
        item = next((item for item in self.batch.items if item.id == key), None)
        session = item.session if item else self.window.sessions.get(key)
        text = str(item.source) if item else str(session.result.source) if session else str(key or '')
        if item:
            text += ('\n' + item.message) if item.message else ''
            text += ('\nSaída: ' + item.target) if item.target else ''
        self.details.setText(text)
        self.review.setEnabled(not self.preparing and not self.batch.running and session is not None
                               and self.window.operation in (None, 'render'))
        self.remove.setEnabled(not self.batch.running and bool(key) and (self.preparing or bool(item and item.session)))

    def reject(self):
        if self.batch.running:
            self.batch.cancel()
        else:
            super().reject()

    def closeEvent(self, event):
        if self.batch.running:
            self.batch.cancel()
            event.ignore()
        else:
            super().closeEvent(event)
