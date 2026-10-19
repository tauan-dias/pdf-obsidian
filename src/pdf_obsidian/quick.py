"""Frontend Qt Quick. Documentos/históricos pertencem ao Python, não às cenas."""
from collections import defaultdict
from pathlib import Path
import multiprocessing as mp
import posixpath
import sys
from urllib.parse import unquote
from uuid import uuid4

from PySide6.QtCore import QObject, Property, QTimer, QUrl, Signal, Slot, Qt
from PySide6.QtGui import QFont, QFontDatabase, QImage, QTextCursor, QTextDocument
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickImageProvider
from PySide6.QtWidgets import QApplication, QFileDialog

from .application import ApplicationController
from .batch import BatchHooks
from .cleanup import build_manual_cleanup_plan
from .comparison import preview_document, unique_markers
from .formatting import format_text, link_label
from .markdown import analyse_markdown, utf16_position
from .quick_models import RowsModel
from .tokens import METRICS
from .sessions import DocumentSession
from .models import AssetInfo


def python_position(text, position):
    return len(text.encode('utf-16-le')[:position * 2].decode('utf-16-le'))


class PageProvider(QQuickImageProvider):
    """Possui apenas o bitmap ativo; nunca abre PDFs na thread de interface."""
    def __init__(self):
        super().__init__(QQuickImageProvider.ImageType.Image)
        self.image = QImage()

    def requestImage(self, image_id, size, requested_size):
        result = self.image.copy()
        size.setWidth(result.width())
        size.setHeight(result.height())
        return result


class QuickController(QObject):
    changed = Signal()
    fontChanged = Signal()
    dialogRequested = Signal(str, str, str)
    closeApproved = Signal()
    viewRestored = Signal('QVariantMap')
    selectionRequested = Signal(int, int)
    followRequested = Signal(int, int)
    pdfReplacing = Signal()
    previewReplacing = Signal()
    previewRebuilt = Signal()
    linkRequested = Signal(str)
    snapshotRequested = Signal()
    documentsRequested = Signal()
    batchPreparationRequested = Signal()

    def __init__(self, parent=None, *, application=None):
        super().__init__(parent)
        self.application = application or ApplicationController(self, tagged_operations=True)
        QApplication.instance().fontChanged.connect(self.fontChanged)
        native = QApplication.font()
        self._base_font_pixels = native.pixelSize() if native.pixelSize() > 0 else native.pointSizeF() * 96 / 72
        available = {family.casefold(): family for family in QFontDatabase.families()}
        def local_family(candidates, fallback):
            return next((available[name.casefold()] for name in candidates if name.casefold() in available), fallback)
        self._interface_family = local_family(('Inter', 'Adwaita Sans', 'Cantarell', 'Noto Sans'), native.family())
        self._editor_family = local_family(('JetBrains Mono', 'JetBrainsMono Nerd Font Mono', 'Adwaita Mono', 'Noto Sans Mono'),
            QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).family())
        self.sessions = {}
        self._texts = {}
        self.active = None
        self.editor = self.preview = None
        self._text_scale = 1.0
        self._preview_visible = False
        self._preview_doc = None
        self._empty = QTextDocument(self)
        self._empty_preview = QTextDocument(self)
        self._filtered_open = False
        self._filtered_visible = set()
        self._filtered_cache = {}
        self._filtered_queue = []
        self._filtered_inflight = None
        self._pending = None
        self._selection = (0, 0)
        self._link_snapshot = None
        self._message = ''
        self._image_url = ''
        self._page = 1
        self._displayed_page = 0
        self._zoom = 100
        self._zoom_mode = 'width'
        self._viewport = (450, 600)
        self._page_rect = None
        self._render_id = 0
        self._desired = None
        self._inflight = None
        self._queued = None
        self._crop = None
        self._export = None
        self._selected = set()
        self._images = {}
        self._native_images = {}
        self._selection_mode = False
        self._preview_dirty = False
        self._closing = False
        self.provider = PageProvider()
        self.pending_paths = []
        self.pending_documents = RowsModel(('key', 'name'), self)
        self.documents = RowsModel(('key', 'name', 'status', 'detail', 'included', 'ready', 'external'), self)
        self.image_model = RowsModel(('key', 'position', 'selected'), self)
        self.filtered = RowsModel(('key', 'page', 'reason', 'thumbnail', 'restorable', 'issue'), self)
        self.batch = self.application.attach_batch(BatchHooks(lambda: True, self.snapshot, self.create_session))
        self.batch.changed.connect(self.batch_changed)
        self.batch.progress_changed.connect(self.changed)
        self.application.stateChanged.connect(self.changed)
        self.application.workerAvailabilityChanged.connect(self.changed)
        self.application.conversionCompleted.connect(self.receive)
        self.application.operationFailed.connect(self.failed)
        self.application.conversionCancelled.connect(self.conversion_cancelled)
        self.application.workerFailed.connect(self.worker_failed)
        self.application.renderCompleted.connect(self.render_finished)
        self.application.cropCompleted.connect(self.crop_finished)
        self.application.sessionExportCompleted.connect(self.export_finished)
        self.application.filteredReviewCompleted.connect(self.filtered_review_finished)
        self.render_timer = QTimer(self)
        self.render_timer.setSingleShot(True)
        self.render_timer.setInterval(160)
        self.render_timer.timeout.connect(self.request_render)
        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.setInterval(280)
        self.preview_timer.timeout.connect(self.refresh_preview)
        self.preview_resize_timer = QTimer(self)
        self.preview_resize_timer.setSingleShot(True)
        self.preview_resize_timer.setInterval(80)
        self.preview_resize_timer.timeout.connect(self.scale_preview_images)
        self.filtered_timer = QTimer(self)
        self.filtered_timer.setSingleShot(True)
        self.filtered_timer.setInterval(30)
        self.filtered_timer.timeout.connect(self.dispatch_filtered_review)

    @Property(QFont, notify=fontChanged)
    def nativeFont(self):
        font = QApplication.font()
        font.setFamily(self._interface_family)
        return font

    @Property(float, constant=True)
    def baseFontPixels(self):
        return self._base_font_pixels

    @Property(str, constant=True)
    def editorFontFamily(self):
        return self._editor_family

    @Property(QObject, constant=True)
    def worker(self):
        return self.application

    @Property(QObject, constant=True)
    def pendingModel(self):
        return self.pending_documents

    @Property(int, notify=changed)
    def pendingCount(self):
        return len(self.pending_paths)

    @Property(QObject, constant=True)
    def documentModel(self):
        return self.documents

    @Property(QObject, constant=True)
    def imageModel(self):
        return self.image_model

    @Property(QObject, constant=True)
    def filteredModel(self):
        return self.filtered

    @Property(bool, notify=changed)
    def hasDocument(self):
        return self.active is not None

    @Property(bool, notify=changed)
    def editable(self):
        return self.active is not None and not self.application.busy

    @Property(str, notify=changed)
    def title(self):
        return self.active.result.title if self.active else ''

    @Property(str, notify=changed)
    def documentPath(self):
        return str(self.active.result.source) if self.active else ''

    @Property(bool, notify=changed)
    def modified(self):
        return bool(self.active and self.active.document.isModified())

    @Property(bool, notify=changed)
    def canUndo(self):
        return bool(self.editable and self.active.document.isUndoAvailable())

    @Property(bool, notify=changed)
    def canRedo(self):
        return bool(self.editable and self.active.document.isRedoAvailable())

    @Property(str, notify=changed)
    def message(self):
        return self._message

    @Property(str, notify=changed)
    def pdfImage(self):
        return self._image_url

    @Property(int, notify=changed)
    def page(self):
        return self._page

    @Property(int, notify=changed)
    def pageCount(self):
        return len(self.active.result.pages) if self.active else 0

    @Property(int, notify=changed)
    def zoom(self):
        return self._zoom

    @Property(str, notify=changed)
    def zoomMode(self):
        return self._zoom_mode

    @Property(bool, notify=changed)
    def rendering(self):
        return self._inflight is not None

    @Property(int, notify=changed)
    def documentCount(self):
        return self.documents.rowCount()

    @Property(bool, notify=changed)
    def batchRunning(self):
        return self.batch.running

    @Property(bool, notify=changed)
    def batchCancelling(self):
        return self.batch.running and self.batch.cancel_requested

    @Property(str, notify=changed)
    def batchMessage(self):
        return self.batch.message

    @Property(int, notify=changed)
    def batchCurrent(self):
        return self.batch.progress[0]

    @Property(int, notify=changed)
    def batchTotal(self):
        return self.batch.progress[1]

    @Property(int, notify=changed)
    def selectedDocuments(self):
        return sum(bool(item.session and item.included) for item in self.batch.items)

    @Property(int, notify=changed)
    def selectedImages(self):
        return len(self._selected)

    @Property(bool, notify=changed)
    def previewReady(self):
        return self.editable and not self._preview_dirty

    @Property(bool, notify=changed)
    def previewPending(self):
        return self._preview_dirty

    @Property(bool, notify=changed)
    def selectionMode(self):
        return self._selection_mode

    @Property(bool, notify=changed)
    def stripMarkers(self):
        return bool(self.active and self.active.strip_markers)

    @Property('QVariantList', notify=changed)
    def warnings(self):
        return [{'page': w.page, 'message': w.message} for w in self.active.result.warnings] if self.active else []

    @Property(int, notify=changed)
    def filteredCount(self):
        return len(self.active.result.filtered_images) if self.active else 0

    def notify(self, message):
        self._message = message
        self.changed.emit()

    def conversion_cancelled(self):
        self.notify('Conversão cancelada.')
        if self._closing:
            self._closing = False
            self.requestClose()

    def failed(self, message):
        self._crop = None
        self.dialogRequested.emit('Falha no processamento', message, 'info')
        self.changed.emit()

    def worker_failed(self):
        self.filtered_timer.stop()
        self._filtered_inflight = None
        self._filtered_queue.clear()
        self._export = self._crop = self._inflight = self._queued = None
        self.dialogRequested.emit('Processo indisponível', 'O processo de PDF terminou. Os documentos concluídos foram preservados. Salve seu texto e reabra a aplicação.', 'info')
        self.changed.emit()

    @Slot(float)
    def setTextScale(self, scale):
        self._text_scale = max(0.75, scale)
        for session in self.sessions.values():
            font = session.document.defaultFont()
            font.setPixelSize(round(METRICS["editorSize"] * self._text_scale))
            session.document.setDefaultFont(font)
        if self.active:
            self._preview_dirty = True
            if self._preview_visible:
                self.preview_timer.start()
            self.changed.emit()

    @Slot(QObject, QObject)
    def attach(self, editor, preview):
        self.editor, self.preview = editor, preview
        editor.property('textDocument').setTextDocument(self._empty)
        if self.active:
            self.install_document()

    def create_session(self, result):
        document = QTextDocument(self)
        font = QFont(self._editor_family)
        font.setPixelSize(round(METRICS["editorSize"] * self._text_scale))
        document.setDefaultFont(font)
        document.setPlainText(result.markdown)
        document.setModified(True)
        session = DocumentSession(result, document)
        self.sessions[session.id] = session
        self._texts[session.id] = document.toPlainText()
        document.contentsChanged.connect(lambda: self.document_changed(session))
        document.modificationChanged.connect(self.changed)
        document.undoAvailable.connect(self.changed)
        document.redoAvailable.connect(self.changed)
        self.sync_documents()
        return session

    def document_changed(self, session):
        text = session.document.toPlainText()
        if text == self._texts.get(session.id):
            return  # Qt Quick also emits contentsChanged when laying out the document.
        self._texts[session.id] = text
        if session is self.active:
            self._selected.clear()
            self.sync_images()
            self._preview_dirty = True
            if self._preview_visible:
                self.preview_timer.start()
            if self._filtered_open:
                self.sync_filtered()
            self.changed.emit()

    def receive(self, result):
        previous = list(self.sessions.values()) if not self.batch.items else []
        session = self.create_session(result)
        self.activate(session.id)
        for old in previous:
            self.sessions.pop(old.id, None)
            self._texts.pop(old.id, None)
            old.document.deleteLater()
        self.sync_documents()
        self.notify('Documento convertido. Revise o Markdown antes de salvar.')
        if self._closing:
            self._closing = False
            self.requestClose()

    def snapshot(self):
        self.snapshotRequested.emit()
        if self.active and self.editor:
            position = self.editor.property('cursorPosition')
            start, end = self.editor.property('selectionStart'), self.editor.property('selectionEnd')
            anchor = end if position == start else start
            self.active.view.update(anchor=anchor, cursor=position, page=self._page,
                zoom=self._zoom, zoomMode=self._zoom_mode, selected=list(self._selected),
                selectionMode=self._selection_mode)

    @Slot('QVariantMap')
    def saveView(self, state):
        if self.active:
            self.active.view.update(state)

    @Slot(str)
    def activate(self, session_id):
        if self.application.busy or session_id not in self.sessions:
            return
        self.snapshot()
        self.preview_timer.stop()
        self.render_timer.stop()
        self.active = self.sessions[session_id]
        state = self.active.view
        self._page = state.get('page', 1)
        self._zoom, self._zoom_mode = state.get('zoom', 100), state.get('zoomMode', 'width')
        self.calculate_zoom()
        self._selected = set(map(tuple, state.get('selected', [])))
        self._selection_mode = state.get('selectionMode', False)
        self._displayed_page = 0
        self._image_url = ''
        self.provider.image = QImage()
        self._desired = None
        self._queued = None
        self._filtered_open = False
        self._filtered_visible.clear()
        self._filtered_queue.clear()
        self.filtered.sync([])
        self.install_document()
        self.changed.emit()
        self.render_timer.start()
        self.viewRestored.emit(state)

    def install_document(self):
        if not self.editor:
            return
        self.editor.property('textDocument').setTextDocument(self.active.document)
        old, self._preview_doc = self._preview_doc, None
        self.preview.property('textDocument').setTextDocument(self._empty_preview)
        if old:
            old.deleteLater()
        self._images.clear()
        self._native_images.clear()
        self.sync_images()
        self._preview_dirty = True
        if self._preview_visible or self.active.view.get('tab') == 1:
            self.preview_timer.start(30)
        state = self.active.view
        self.selectionRequested.emit(state.get('anchor', 0), state.get('cursor', 0))

    def sync_documents(self):
        rows = []
        batch_sessions = set()
        for item in self.batch.items:
            session = item.session
            if session:
                batch_sessions.add(session.id)
            rows.append(dict(key=session.id if session else item.id, name=item.source.name,
                status=item.export_status or item.status, detail=item.message,
                included=item.included, ready=session is not None, external=False))
        for session in self.sessions.values():
            if session.id not in batch_sessions:
                rows.append(dict(key=session.id, name=session.result.source.name, status='Fora do lote',
                    detail='', included=False, ready=True, external=True))
        self.documents.sync(rows)
        self.changed.emit()

    def batch_changed(self):
        self.sync_documents()
        if self._closing and not self.batch.running:
            self._closing = False
            self.requestClose()

    @Slot(str, bool)
    def include(self, key, included):
        if self.application.busy:
            return
        for item in self.batch.items:
            if item.session and item.session.id == key:
                item.included = included
        self.sync_documents()

    def confirm(self, text, action):
        if self._pending:
            return
        self._pending = action
        self.dialogRequested.emit('Descartar alterações?', text, 'confirm')

    @Slot(bool)
    def answer(self, accepted):
        action, self._pending = self._pending, None
        if accepted and action:
            action()

    @Slot()
    def openPdf(self):
        if self.application.busy or not self.application.workerAvailable:
            return
        def choose():
            path, _ = QFileDialog.getOpenFileName(None, 'Abrir PDF', '', 'Documentos PDF (*.pdf)')
            if path:
                self.application.start_conversion(path)
        # Existing batch documents remain available; otherwise replace only on success.
        if not self.batch.items and any(s.document.isModified() for s in self.sessions.values()):
            self.confirm('As alterações dos documentos abertos serão descartadas ao substituir o documento.', choose)
        else:
            choose()

    @Slot()
    def newBatch(self):
        if self.application.busy or not self.application.workerAvailable:
            return
        def choose():
            paths, _ = QFileDialog.getOpenFileNames(None, 'Converter em lote', '', 'Documentos PDF (*.pdf)')
            if not paths:
                return
            self.pending_paths = list(dict.fromkeys(str(Path(p).resolve()) for p in paths))
            self.sync_pending()
            self.batchPreparationRequested.emit()
        if any(i.session and i.session.document.isModified() for i in self.batch.items):
            self.confirm('O lote anterior será substituído, incluindo os documentos desmarcados com alterações não salvas.', choose)
        else:
            choose()

    def sync_pending(self):
        self.pending_documents.sync([dict(key=p, name=Path(p).name) for p in self.pending_paths])
        self.changed.emit()

    @Slot()
    def addPending(self):
        if self.application.busy:
            return
        paths, _ = QFileDialog.getOpenFileNames(None, 'Adicionar PDFs ao lote', '', 'Documentos PDF (*.pdf)')
        self.pending_paths = list(dict.fromkeys([*self.pending_paths, *(str(Path(p).resolve()) for p in paths)]))
        self.sync_pending()

    @Slot(str)
    def removePending(self, path):
        if path in self.pending_paths:
            self.pending_paths.remove(path)
            self.sync_pending()

    @Slot()
    def beginBatch(self):
        if self.application.busy or not self.pending_paths:
            return
        ids = {i.session.id for i in self.batch.items if i.session}
        if self.active and self.active.id in ids:
            self.snapshot()
            if self.editor:
                self.editor.property('textDocument').setTextDocument(self._empty)
            self.active = None
            self._image_url = ''
            self._desired = self._queued = None
            self.provider.image = QImage()
        for key in ids:
            session = self.sessions.pop(key, None)
            if session:
                self._texts.pop(session.id, None)
                session.document.deleteLater()
        paths, self.pending_paths = self.pending_paths, []
        self.batch.start(paths)
        self.sync_pending()
        self.documentsRequested.emit()

    @Slot()
    def cancelBatch(self):
        self.batch.cancel()

    @Slot()
    def exportBatch(self):
        if not self.application.busy and self.selectedDocuments:
            vault = QFileDialog.getExistingDirectory(None, 'Escolher pasta do vault')
            if vault:
                try:
                    self.batch.export_selected(vault)
                except Exception as exc:
                    self.failed(str(exc))

    @Slot()
    def exportCurrent(self):
        if not self.editable or not self.application.workerAvailable:
            return
        vault = QFileDialog.getExistingDirectory(None, 'Escolher pasta do vault')
        if vault:
            self.start_export(vault)

    def start_export(self, vault):
        if not self.editable or not self.application.workerAvailable or not Path(vault).is_dir():
            return False
        session = self.active
        token = uuid4().hex
        self._export = (token, session.id, session.document.revision(), str(Path(vault).resolve()))
        self.application.set_state(True, 'export')
        self.application.runtime.commands.put(('session_export', *self._export[:3], self._export[3],
            session.result, session.document.toPlainText(), session.strip_markers, tuple(session.removals),
            session.exports.get(self._export[3])))
        return True

    def export_finished(self, event):
        token, session_id, revision, ok, value, target, unchanged = event
        if not self._export or tuple(event[:3]) != self._export[:3]:
            return
        vault = self._export[3]
        self._export = None
        self.application.set_state(False, '')
        session = self.sessions.get(session_id)
        if ok:
            if session and session.document.revision() == revision:
                session.record_export(vault, value, target)
            title = 'Documento já salvo' if unchanged else 'Documento salvo'
            self.dialogRequested.emit(title, 'Arquivos gravados em:\n' + target, 'info')
        else:
            self.failed(value)
        self.sync_documents()

    @Slot(bool)
    def setStripMarkers(self, value):
        if self.editable and self.active.strip_markers != value:
            self.active.strip_markers = value
            self.active.document.setModified(True)
            self.changed.emit()

    @Slot()
    def shutdown(self):
        self.render_timer.stop()
        self.preview_timer.stop()
        self.preview_resize_timer.stop()
        self.filtered_timer.stop()
        self.application.shutdown()

    @Slot()
    def release_scene(self):
        self.shutdown()
        self.editor = self.preview = None

    @Slot()
    def requestClose(self):
        if self.batch.running:
            self._closing = True
            self.batch.cancel()
            self.notify('Aguardando o encerramento do lote…')
            return
        if self.application.operation == 'convert':
            self._closing = True
            self.application.cancelConversion()
            return
        if self.application.busy and self.application.workerAvailable:
            self.notify('Aguarde a operação terminar antes de fechar.')
            return
        def close():
            self.render_timer.stop()
            self.preview_timer.stop()
            self.preview_resize_timer.stop()
            self.application.shutdown()
            self.closeApproved.emit()
        if any(s.document.isModified() for s in self.sessions.values()):
            self.confirm('Há documentos com alterações não salvas. Fechar descarta todos os documentos da sessão.', close)
        else:
            close()

    @Slot(int, int, int)
    def rememberSelection(self, start, end, position):
        self._selection = (end if position == start else start, position)

    def selection(self):
        if self.editor:
            pos = self.editor.property('cursorPosition')
            a, b = self.editor.property('selectionStart'), self.editor.property('selectionEnd')
            return (b if pos == a else a), pos
        return self._selection

    @Slot(str, 'QVariant')
    def format(self, command, value=None):
        if not self.editable:
            return
        text = self.active.document.toPlainText()
        anchor, position = self.selection()
        start, end = sorted((python_position(text, anchor), python_position(text, position)))
        if command == 'link':
            try:
                label = link_label(text, start, end)
            except ValueError as exc:
                self.notify(str(exc))
                return
            self._link_snapshot = (self.active.id, self.active.document.revision(), anchor, position)
            self.linkRequested.emit(label)
            return
        try:
            edit = format_text(text, start, end, command, value)
            self.replace(edit.start, edit.end, edit.text)
            updated = self.active.document.toPlainText()
            a, b = edit.selection_start, edit.selection_end
            if anchor > position:
                a, b = b, a
            self.selectionRequested.emit(utf16_position(updated, a), utf16_position(updated, b))
            self.notify('Formatação aplicada.')
        except ValueError as exc:
            self.notify(str(exc))

    @Slot(str, str)
    def insertLink(self, label, destination):
        state, self._link_snapshot = self._link_snapshot, None
        if not state or not self.editable or (self.active.id, self.active.document.revision()) != state[:2]:
            return
        self.selectionRequested.emit(state[2], state[3])
        text = self.active.document.toPlainText()
        start, end = sorted((python_position(text, state[2]), python_position(text, state[3])))
        try:
            edit = format_text(text, start, end, 'link', (label, destination.strip()))
            self.replace(edit.start, edit.end, edit.text)
            updated = self.active.document.toPlainText()
            a, b = edit.selection_start, edit.selection_end
            if state[2] > state[3]:
                a, b = b, a
            self.selectionRequested.emit(utf16_position(updated, a), utf16_position(updated, b))
        except ValueError as exc:
            self.notify(str(exc))

    def replace(self, start, end, value):
        doc = self.active.document
        text = doc.toPlainText()
        if text[start:end] == value:
            return
        cursor = QTextCursor(doc)
        cursor.beginEditBlock()
        cursor.setPosition(utf16_position(text, start))
        cursor.setPosition(utf16_position(text, end), QTextCursor.MoveMode.KeepAnchor)
        cursor.insertText(value)
        cursor.endEditBlock()

    @Slot()
    def undo(self):
        if self.editable:
            self.active.document.undo()

    @Slot()
    def redo(self):
        if self.editable:
            self.active.document.redo()

    @Slot(bool)
    def setPreviewVisible(self, visible):
        self._preview_visible = visible
        if visible and self.active and self._preview_dirty:
            self.preview_timer.start(30)
        elif not visible:
            self.preview_timer.stop()

    def refresh_preview(self):
        self.preview_timer.stop()
        if not self.active or not self.preview:
            return
        self.previewReplacing.emit()
        old = self._preview_doc
        doc = preview_document(self.active.document.toPlainText(), self.active.result.workspace, self)
        font = QFont(self._interface_family)
        font.setPixelSize(round(METRICS["previewSize"] * self._text_scale))
        doc.setDefaultFont(font)
        self._preview_doc = doc
        self._native_images = {}
        self.scale_preview_images()
        self.preview.property('textDocument').setTextDocument(doc)
        if old:
            old.deleteLater()
        self._preview_dirty = False
        self.map_images()
        self.changed.emit()
        self.previewRebuilt.emit()

    @Slot()
    def previewResized(self):
        self.preview_resize_timer.start()

    def scale_preview_images(self):
        doc = self._preview_doc
        if not doc or not self.preview:
            return
        available = max(1, self.preview.width() - 2 * doc.documentMargin())
        block = doc.begin()
        updates = []
        while block.isValid():
            it = block.begin()
            while not it.atEnd():
                fragment = it.fragment()
                if fragment.charFormat().isImageFormat():
                    fmt = fragment.charFormat().toImageFormat()
                    pos = fragment.position()
                    if pos not in self._native_images:
                        resource = doc.resource(QTextDocument.ResourceType.ImageResource, QUrl(fmt.name()))
                        nw = resource.width() if hasattr(resource, 'width') else 16
                        nh = resource.height() if hasattr(resource, 'height') else 16
                        width = fmt.width() or nw
                        height = fmt.height() or nh * width / max(1, nw)
                        if fmt.height() and not fmt.width():
                            width = nw * height / max(1, nh)
                        self._native_images[pos] = (width, height)
                    width, height = self._native_images[pos]
                    scale = min(1, available / max(1, width))
                    if abs(fmt.width() - width * scale) > .1 or abs(fmt.height() - height * scale) > .1:
                        fmt.setWidth(width * scale)
                        fmt.setHeight(height * scale)
                        updates.append((pos, fmt))
                it += 1
            block = block.next()
        for pos, fmt in updates:
            cursor = QTextCursor(doc)
            cursor.setPosition(pos)
            cursor.movePosition(QTextCursor.MoveOperation.NextCharacter, QTextCursor.MoveMode.KeepAnchor)
            cursor.setCharFormat(fmt)

    def sync_images(self):
        prefix = self.active.id if self.active else ''
        self.image_model.sync([dict(key=f'{prefix}:{pos}', position=pos, selected=key in self._selected)
                               for pos, key in self._images.items()])

    def map_images(self):
        self._images = {}
        if not self._preview_doc or not self.active:
            return
        source, rendered = defaultdict(list), defaultdict(list)
        analysis = analyse_markdown(self.active.document.toPlainText(), (a.path for a in self.active.result.assets))
        for image in analysis.image_occurrences:
            source[image.asset].append(image)
        block = self._preview_doc.begin()
        while block.isValid():
            it = block.begin()
            while not it.atEnd():
                fragment = it.fragment()
                if fragment.charFormat().isImageFormat():
                    url = QUrl(fragment.charFormat().toImageFormat().name())
                    asset = None
                    if url.isRelative():
                        asset = posixpath.normpath(unquote(url.path()))
                    elif url.isLocalFile():
                        try:
                            asset = Path(url.toLocalFile()).relative_to(self.active.result.workspace).as_posix()
                        except ValueError:
                            pass
                    if asset:
                        for pos in range(fragment.position(), fragment.position() + fragment.length()):
                            rendered[asset].append(pos)
                it += 1
            block = block.next()
        for asset, positions in rendered.items():
            if len(positions) == len(source[asset]):
                for pos, image in zip(positions, source[asset]):
                    if image.paragraph is not None:
                        self._images[pos] = (asset, image.occurrence)
        self.sync_images()

    @Slot(bool)
    def setSelectionMode(self, value):
        self._selection_mode = value
        if not value:
            self._selected.clear()
        self.sync_images()
        self.changed.emit()

    @Slot()
    def clearImages(self):
        self._selected.clear()
        self.sync_images()
        self.changed.emit()

    @Slot(int)
    def toggleImage(self, position):
        if not self.previewReady or not self._selection_mode:
            return
        key = self._images.get(position)
        if key is None:
            self.notify('Imagem sem incorporação isolada. Edite esta referência no Markdown.')
            return
        if key in self._selected:
            self._selected.remove(key)
        else:
            self._selected.add(key)
        self.sync_images()
        self.changed.emit()

    @Slot(result='QVariantList')
    def imageTargets(self):
        return [{'position': pos, 'selected': key in self._selected} for pos, key in self._images.items()]

    @Slot()
    def removeImages(self):
        if not self.previewReady or not self._selected:
            return
        try:
            doc = self.active.document
            text = doc.toPlainText()
            anchor, position = self.selection()
            saved = QTextCursor(doc)
            saved.setPosition(anchor)
            saved.setPosition(position, QTextCursor.MoveMode.KeepAnchor)
            plan = build_manual_cleanup_plan(self.active.result, text, self._selected)
            cursor = QTextCursor(doc)
            cursor.beginEditBlock()
            for removal in reversed(plan.removals):
                cursor.setPosition(utf16_position(text, removal.start))
                cursor.setPosition(utf16_position(text, removal.end), QTextCursor.MoveMode.KeepAnchor)
                cursor.removeSelectedText()
            cursor.endEditBlock()
            self.selectionRequested.emit(saved.anchor(), saved.position())
            self.active.removals.extend(plan.removals)
            self._selected.clear()
            self.notify('Imagens removidas. Desfazer recupera as incorporações.')
        except ValueError as exc:
            self.notify(str(exc))

    @Slot()
    def openFiltered(self):
        self._filtered_open = True
        self.sync_filtered()

    @Slot()
    def closeFiltered(self):
        self._filtered_open = False
        self._filtered_visible.clear()
        self._filtered_queue.clear()
        self.filtered_timer.stop()

    def sync_filtered(self):
        if not self.active or not self._filtered_open:
            return
        session = self.active
        revision = session.document.revision()
        self._filtered_queue = [key for key in self._filtered_queue if key[:2] == (session.id, revision)]
        rows = []
        for i, item in enumerate(session.result.filtered_images):
            key = (session.id, revision, i)
            issue = self._filtered_cache.get(key, 'Verificando…')
            rows.append(dict(key=str(i), page=item.page, reason=item.reason,
                thumbnail=QUrl.fromLocalFile(str(session.result.workspace / item.asset)).toString(),
                restorable=key in self._filtered_cache and not issue, issue=issue))
        self.filtered.sync(rows)
        for index in self._filtered_visible.copy():
            self.reviewFiltered(index)

    @Slot(int)
    def reviewFiltered(self, index):
        if not self._filtered_open or not self.active or not 0 <= index < self.filteredCount:
            return
        self._filtered_visible.add(index)
        key = (self.active.id, self.active.document.revision(), index)
        if key not in self._filtered_cache and key not in self._filtered_queue:
            if self._filtered_inflight is None or self._filtered_inflight[1:] != key:
                self._filtered_queue.append(key)
                self.filtered_timer.start()

    def dispatch_filtered_review(self):
        if not self._filtered_open or not self.active or self._filtered_inflight or not self._filtered_queue:
            return
        if not self.application.workerAvailable:
            return
        # Give conversion/export/crop and the current PDF page priority over review.
        if self.application.busy or self.rendering or self.render_timer.isActive():
            self.filtered_timer.start()
            return
        key = self._filtered_queue.pop(0)
        current = (self.active.id, self.active.document.revision())
        if key[:2] != current:
            self.filtered_timer.start()
            return
        self._filtered_inflight = (uuid4().hex, *key)
        self.application.runtime.commands.put(('review_filtered', *self._filtered_inflight,
            self.active.result, self.active.document.toPlainText()))

    def filtered_review_finished(self, event):
        token, session_id, revision, index, issue = event
        if self._filtered_inflight != tuple(event[:4]):
            return
        self._filtered_inflight = None
        if self.active and (session_id, revision) == (self.active.id, self.active.document.revision()):
            # Only the current revision is retained; stale answers never enable Restore.
            self._filtered_cache = {k: v for k, v in self._filtered_cache.items()
                                    if k[:2] == (session_id, revision)}
            self._filtered_cache[(session_id, revision, index)] = issue
            self.sync_filtered()
        if self._filtered_queue:
            self.filtered_timer.start()

    @Slot(int)
    def restoreImage(self, index):
        if not self.editable or not 0 <= index < self.filteredCount:
            return
        from .restoration import restoration_edit
        try:
            anchor, position = self.selection()
            offset, text = restoration_edit(self.active.result, self.active.document.toPlainText(), self.active.result.filtered_images[index])
            saved = QTextCursor(self.active.document)
            saved.setPosition(anchor)
            saved.setPosition(position, QTextCursor.MoveMode.KeepAnchor)
            self.replace(offset, offset, text)
            self.selectionRequested.emit(saved.anchor(), saved.position())
            self.sync_filtered()
            self.notify('Imagem restaurada. Você pode desfazer a inserção.')
        except ValueError as exc:
            self.notify(str(exc))

    @Slot(int)
    def goPage(self, page):
        if not self.editable or not self.pageCount:
            return
        self._desired = None
        self._page = max(1, min(page, self.pageCount))
        self.calculate_zoom()
        self.render_timer.start()
        self.changed.emit()

    @Slot(int)
    def setZoom(self, percent):
        if not self.editable:
            return
        self._desired = None
        self._zoom = max(25, min(300, percent))
        self._zoom_mode = 'manual'
        self.render_timer.start()
        self.changed.emit()

    @Slot(str)
    def fit(self, mode):
        if self.editable and mode in ('width', 'page'):
            self._desired = None
            self._zoom_mode = mode
            self.calculate_zoom()
            self.render_timer.start()
            self.changed.emit()

    @Slot(float, float)
    def viewport(self, width, height):
        if (width, height) != self._viewport and width > 0 and height > 0:
            self._viewport = (width, height)
            if self._zoom_mode != 'manual':
                self.calculate_zoom()
                self._desired = None
                self.render_timer.start()
                self.changed.emit()

    def calculate_zoom(self):
        if self.active and self._zoom_mode != 'manual':
            page = self.active.result.pages[self._page - 1]
            dpi = (self._viewport[0] - 24) / page.width * 72
            if self._zoom_mode == 'page':
                dpi = min(dpi, (self._viewport[1] - 24) / page.height * 72)
            self._zoom = round(max(25, min(300, dpi)))

    def request_render(self):
        if not self.active or not self.application.workerAvailable:
            return
        result = self.active.result
        self.calculate_zoom()
        self._render_id += 1
        path = self.application.runtime.root / f'page-{self._render_id}.png'
        request = (self._render_id, str(result.source), self._page, self._zoom, str(path))
        self._desired = (self.active.id, self._render_id)
        self._queued = request
        self.dispatch_render()

    def dispatch_render(self):
        if self._inflight is None and self._queued:
            self._inflight, self._queued = self._queued, None
            self.application.dispatch_render(self._inflight)
            self.changed.emit()

    def render_finished(self, kind, args):
        request_id = args[0]
        if self._inflight is None or request_id != self._inflight[0]:
            return
        request, self._inflight = self._inflight, None
        current = self.active and self._desired == (self.active.id, request_id)
        if kind == 'rendered':
            _, page, path, rect = args
            if current:
                image = QImage(path)
                if not image.isNull():
                    self.pdfReplacing.emit()
                    self.provider.image = image
                    self._image_url = f'image://pdf/{request_id}'
                    self._displayed_page = page
                    self._page_rect = rect
                    self.follow_page()
            Path(path).unlink(missing_ok=True)
        elif current:
            self._page = self._displayed_page or 1
            self.calculate_zoom()
            self.notify('Não foi possível renderizar a página: ' + str(args[1]))
        self.changed.emit()
        self.dispatch_render()

    @Slot()
    def follow_page(self):
        if not self.active:
            return
        text = self.active.document.toPlainText()
        marker = unique_markers(text).get(self._page)
        if marker:
            pos = utf16_position(text, marker.start())
            preview_pos = 0
            if self._preview_doc:
                block = self._preview_doc.begin()
                while block.isValid():
                    it = block.begin()
                    while not it.atEnd():
                        frag = it.fragment()
                        if f'pdf-page-{self._page}' in frag.charFormat().anchorNames():
                            preview_pos = frag.position()
                        it += 1
                    block = block.next()
            self.followRequested.emit(pos, preview_pos)
        else:
            self.notify('Marcador da página ausente ou duplicado; acompanhamento indisponível.')

    @Slot(float, float, float, float)
    def crop(self, x, y, width, height):
        if not self.editable or self._page != self._displayed_page or self.rendering or not self._page_rect:
            return
        if width <= 0 or height <= 0 or x < 0 or y < 0 or x + width > 1.001 or y + height > 1.001:
            return
        rect = self._page_rect
        x0, y0, x1, y1 = rect
        box = (x0 + x * (x1 - x0), y0 + y * (y1 - y0),
               x0 + (x + width) * (x1 - x0), y0 + (y + height) * (y1 - y0))
        anchor, position = self.selection()
        cursor = QTextCursor(self.active.document)
        cursor.setPosition(position)
        self._crop = (self.active.id, self.active.document.revision(), cursor, box, self._page)
        if not self.application.start_crop(self.active.result.source, self.active.result.workspace, self._page, box):
            self._crop = None

    def crop_finished(self, asset):
        state, self._crop = self._crop, None
        if not state or not self.active or (self.active.id, self.active.document.revision()) != state[:2]:
            return
        session = self.active
        page = session.result.pages[state[4] - 1]
        embedding = f"![Recorte da página {state[4]}]({asset})"
        session.result.assets.append(AssetInfo(asset, 'manual', 'manual', state[4], state[3],
            (page.width, page.height), generated_markdown=embedding))
        cursor = state[2]
        cursor.beginEditBlock()
        cursor.insertText('\n\n' + embedding + '\n\n')
        cursor.endEditBlock()
        self.selectionRequested.emit(cursor.position(), cursor.position())
        self.notify('Recorte inserido no Markdown.')


def create_engine(controller):
    engine = QQmlApplicationEngine()
    engine.addImageProvider('pdf', controller.provider)
    engine.destroyed.connect(controller.release_scene)
    engine.load_warnings = []
    engine.warnings.connect(lambda items: engine.load_warnings.extend(item.toString() for item in items))
    engine.setInitialProperties({'backend': controller})
    engine.load(QUrl.fromLocalFile(str(Path(__file__).parent / 'qml/Main.qml')))
    if not engine.rootObjects():
        controller.application.shutdown()
        raise RuntimeError('Não foi possível carregar a interface QML. Use --widgets para recuperação.')
    return engine


def main():
    mp.freeze_support()
    app = QApplication(sys.argv)
    app.setApplicationName('PDF → Obsidian')
    controller = QuickController()
    engine = create_engine(controller)
    app.aboutToQuit.connect(controller.shutdown)
    controller.application.start_polling()
    result = app.exec()
    # Destroy the scene before its Python-owned documents and image provider.
    engine.deleteLater()
    from PySide6.QtCore import QEvent
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    return result
