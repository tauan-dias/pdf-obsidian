"""Coordenação de processamento compartilhável por Widgets e Qt Quick.

Este módulo depende apenas de QtCore. Diálogos, documentos de edição e estado
visual pertencem ao adaptador do frontend, não ao processo de PDF.
"""
import multiprocessing as mp
from pathlib import Path
from queue import Empty
import shutil
import tempfile
from uuid import uuid4

from PySide6.QtCore import QObject, Property, QTimer, QUrl, Signal, Slot

from .batch import BatchController
from .exporter import export_document, export_signature, export_intact
from .worker import run
from .recognition import ConversionOptions, resource_status


class WorkerRuntime:
    """Dono das filas, processo e arquivos temporários da sessão."""

    def __init__(self):
        self.root = Path(tempfile.mkdtemp(prefix='pdf-obsidian-'))
        self.workspaces = []
        self.closed = False
        context = mp.get_context('spawn')
        self.commands, self.events = context.Queue(), context.Queue()
        self.cancel_event = context.Event()
        self.worker = context.Process(target=run, args=(self.commands, self.events, self.cancel_event), daemon=True)
        try:
            self.worker.start()
        except Exception:
            for channel in (self.commands, self.events):
                channel.close()
            shutil.rmtree(self.root, ignore_errors=True)
            raise

    def allocate_workspace(self):
        workspace = Path(tempfile.mkdtemp(dir=self.root))
        self.workspaces.append(workspace)
        return workspace

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.cancel_event.set()
        self.commands.put(('stop',))
        self.worker.join(timeout=.5)
        if self.worker.is_alive():
            self.worker.terminate()
            self.worker.join(timeout=2)
        for channel in (self.commands, self.events):
            channel.cancel_join_thread()
            channel.close()
        shutil.rmtree(self.root, ignore_errors=True)


class ApplicationController(QObject):
    """Fachada sem widgets; slots despacham e sinais entregam resultados.

    Renderização e recorte conservam o protocolo do worker. O frontend ainda
    aplica resultados ao seu editor e calcula a geometria visual do PDF.
    """

    stateChanged = Signal()
    workerAvailabilityChanged = Signal()
    progressChanged = Signal()
    conversionOptionsChanged = Signal()
    conversionStageChanged = Signal()
    sourceChanged = Signal()
    cancellationChanged = Signal()
    conversionCompleted = Signal(object)
    cropCompleted = Signal(str)
    conversionCancelled = Signal()
    operationFailed = Signal(str)
    renderCompleted = Signal(str, object)
    workerFailed = Signal()
    sessionExportCompleted = Signal(object)
    filteredReviewCompleted = Signal(object)

    def __init__(self, parent=None, *, runtime=None, tagged_operations=False):
        super().__init__(parent)
        self.runtime = runtime if runtime is not None else WorkerRuntime()
        self.tagged_operations = tagged_operations
        self._job_token = None
        self.batch = None
        self._busy = False
        self._operation = ''
        self._progress = (0, 0)
        self.conversion_options = ConversionOptions()
        self._conversion_stage = ''
        self._source = ''
        self._cancellation_requested = False
        self._failed = False
        self._closed = False
        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(80)
        self.poll_timer.timeout.connect(self.poll)

    @Property(str, notify=conversionOptionsChanged)
    def ocrMode(self):
        return self.conversion_options.ocr_mode

    @Slot(str)
    def setOcrMode(self, mode):
        if self.busy:
            return
        options = ConversionOptions(mode)
        if options != self.conversion_options:
            self.conversion_options = options
            self.conversionOptionsChanged.emit()

    @Property(str, constant=True)
    def recognitionStatus(self):
        return resource_status()[1]

    @Property(str, notify=conversionStageChanged)
    def conversionStage(self):
        return self._conversion_stage

    def set_conversion_stage(self, text):
        if text != self._conversion_stage:
            self._conversion_stage = text
            self.conversionStageChanged.emit()

    @Property(bool, notify=stateChanged)
    def busy(self):
        return self._busy

    @Property(str, notify=stateChanged)
    def operation(self):
        return self._operation

    @Property(bool, notify=workerAvailabilityChanged)
    def workerAvailable(self):
        return not self._closed and not self._failed and self.runtime.worker.is_alive()

    @Property(int, notify=progressChanged)
    def progressCurrent(self):
        return self._progress[0]

    @Property(int, notify=progressChanged)
    def progressTotal(self):
        return self._progress[1]

    @Property(str, notify=sourceChanged)
    def sourceName(self):
        return Path(self._source).name if self._source else ''

    @Property(str, notify=sourceChanged)
    def sourcePath(self):
        return self._source

    @Property(bool, notify=cancellationChanged)
    def cancellationRequested(self):
        return self._cancellation_requested

    def _reset_cancellation(self):
        if self._cancellation_requested:
            self._cancellation_requested = False
            self.cancellationChanged.emit()

    def set_state(self, busy, operation):
        state = bool(busy), operation or ''
        if state != (self._busy, self._operation):
            self._busy, self._operation = state
            self.stateChanged.emit()

    def _set_progress(self, current, total):
        progress = int(current), int(total)
        if progress != self._progress:
            self._progress = progress
            self.progressChanged.emit()

    def attach_batch(self, hooks):
        if self.batch is not None:
            raise RuntimeError('O controlador de lote já foi configurado.')
        self.batch = BatchController(self, hooks)
        return self.batch

    def start_polling(self):
        if not self._closed and not self._failed:
            self.poll_timer.start()

    @Slot(QUrl, result=bool)
    def startConversion(self, source):
        """Entrada QML explícita: somente URLs de arquivos locais."""
        if not source.isLocalFile() or not source.toLocalFile():
            return False
        return self.start_conversion(source.toLocalFile())

    def start_conversion(self, source):
        if not source or self.busy or not self.workerAvailable:
            return False
        source = str(Path(source).resolve())
        workspace = self.runtime.allocate_workspace()
        self.runtime.cancel_event.clear()
        self._source = source
        self.set_conversion_stage('Extraindo texto e imagens…')
        self._reset_cancellation()
        self.sourceChanged.emit()
        self._set_progress(0, 0)
        self.set_state(True, 'convert')
        if self.tagged_operations:
            self._job_token = uuid4().hex
            self.runtime.commands.put(('session_convert', self._job_token, source, str(workspace),
                                       *((self.conversion_options,) if self.ocrMode != 'auto' else ())))
        else:
            self.runtime.commands.put(('convert', source, str(workspace),
                                       *((self.conversion_options,) if self.ocrMode != 'auto' else ())))
        return True

    def start_crop(self, source, workspace, page, bbox):
        if self.busy or not self.workerAvailable:
            return False
        self.set_state(True, 'crop')
        if self.tagged_operations:
            self._job_token = uuid4().hex
            self.runtime.commands.put(('session_crop', self._job_token, str(source), str(workspace), page, tuple(bbox)))
        else:
            self.runtime.commands.put(('crop', str(source), str(workspace), page, tuple(bbox)))
        return True

    def dispatch_render(self, request):
        # Coalescing and viewport geometry still belong to the PDF adapter.
        if not self.workerAvailable:
            return False
        self.runtime.commands.put(('render', *request))
        return True

    def export_document(self, result, vault, markdown, *, strip_page_markers=False, cleanup_removals=(), record=None, manifest=None):
        """Publicação síncrona do adaptador Widgets de recuperação.

        A janela Quick usa session_export no worker, com snapshot e identidade.
        """
        signature = export_signature(result, markdown,
                                     strip_page_markers=strip_page_markers,
                                     cleanup_removals=cleanup_removals)
        if record and record.signature == signature and export_intact(record, vault):
            if manifest is not None:
                manifest.clear()
                manifest.update(record.manifest)
            return record.target, signature
        target = export_document(result, vault, markdown,
                                 strip_page_markers=strip_page_markers,
                                 cleanup_removals=cleanup_removals, manifest=manifest)
        return target, signature

    @Slot()
    def cancelConversion(self):
        if self.operation == 'convert' and not self._closed and not self._cancellation_requested:
            self._cancellation_requested = True
            self.runtime.cancel_event.set()
            self.cancellationChanged.emit()

    @Slot()
    def poll(self):
        if self._closed or self._failed:
            return
        while not self._closed:
            try:
                event = self.runtime.events.get_nowait()
            except Empty:
                break
            kind, *args = event
            if kind == 'session_event':
                token, kind, *args = args
                if token != self._job_token or self._job_token is None:
                    continue
                if kind in ('converted', 'cropped', 'cancelled', 'error'):
                    self._job_token = None
            elif self.tagged_operations and kind in ('progress', 'stage', 'converted', 'cropped', 'cancelled', 'error'):
                continue
            if kind == 'filtered_checked':
                self.filteredReviewCompleted.emit(args)
            elif kind == 'session_export':
                self.sessionExportCompleted.emit(args)
            elif kind == 'batch':
                if self.batch is not None:
                    self.batch.handle(*args)
            elif kind == 'stage':
                if self.operation == 'convert':
                    self.set_conversion_stage(str(args[0]))
            elif kind == 'progress':
                if self.operation == 'convert':
                    self._set_progress(*args)
            elif kind in ('rendered', 'render_error'):
                self.renderCompleted.emit(kind, args)
            elif kind in ('converted', 'cropped', 'cancelled', 'error'):
                self.set_state(False, None)
                self.set_conversion_stage('')
                self._reset_cancellation()
                if kind == 'converted':
                    self.conversionCompleted.emit(args[0])
                elif kind == 'cropped':
                    self.cropCompleted.emit(args[0])
                elif kind == 'cancelled':
                    self._set_progress(0, 1)
                    self.conversionCancelled.emit()
                else:
                    self._set_progress(0, 1)
                    self.operationFailed.emit(str(args[0]))
        if self._closed:
            return
        if not self.runtime.worker.is_alive():
            self._failed = True
            self._reset_cancellation()
            self.poll_timer.stop()
            if self.batch is not None:
                self.batch.worker_failed()
            self.set_state(True, None)
            self.workerAvailabilityChanged.emit()
            self.workerFailed.emit()

    def shutdown(self):
        """Chamado pelo frontend após confirmar descarte e encerrar o lote."""
        if self._closed:
            return
        self._closed = True
        self.poll_timer.stop()
        self.runtime.close()
        self._reset_cancellation()
        self.set_state(False, None)
        self.workerAvailabilityChanged.emit()
