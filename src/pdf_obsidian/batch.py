"""Fila sequencial de conversão e exportação com revisão entre as etapas."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import shutil
from uuid import uuid4
from typing import Callable, TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

if TYPE_CHECKING:
    from .sessions import DocumentSession


@dataclass(frozen=True)
class BatchHooks:
    """Adaptador de sessões; a fila não conhece janelas ou diálogos.

    prepare_start confirma/prepara a substituição do lote anterior. O frontend
    conserva a propriedade dos documentos e dos respectivos históricos.
    """
    prepare_start: Callable[[], bool]
    snapshot_active: Callable[[], None]
    create_session: Callable[[object], DocumentSession]


@dataclass
class BatchItem:
    source: Path
    id: str = field(default_factory=lambda: uuid4().hex)
    session: DocumentSession | None = None
    status: str = 'Pendente'
    included: bool = True
    export_status: str = ''
    message: str = ''
    target: str = ''


class BatchController(QObject):
    changed = Signal()
    progress_changed = Signal()

    def __init__(self, application, hooks: BatchHooks):
        super().__init__(application)
        self.application = application
        self.hooks = hooks
        self.items = []
        self.token = ''
        self.mode = None
        self.conversion_options = None
        self.queue = []
        self.ready = []
        self.active = None
        self.work = None
        self.cancel_requested = False
        self.progress = (0, 0)
        self.message = ''
        self.vault = None
        self.export_items = []

    @property
    def running(self):
        return self.mode is not None

    def start(self, paths):
        if self.application.busy or not self.application.workerAvailable:
            return False
        sources = list(dict.fromkeys(Path(path).resolve() for path in paths))
        if not sources or not self.hooks.prepare_start():
            return False
        self.hooks.snapshot_active()
        self.token = uuid4().hex
        self.items = [BatchItem(path) for path in sources]
        self.ready, self.export_items = [], []
        self.mode = 'convert'
        self.conversion_options = self.application.conversion_options
        self.queue = self.items.copy()
        self.cancel_requested = False
        self.application.runtime.cancel_event.clear()
        self.application.set_state(True, 'batch')
        self._dispatch()
        return True

    def export_selected(self, vault):
        if self.running or self.application.busy or not self.application.workerAvailable:
            return False
        vault = Path(vault).resolve()
        if not vault.is_dir():
            raise ValueError('Escolha uma pasta de vault existente.')
        self.hooks.snapshot_active()
        selected = [item for item in self.items if item.session and item.included]
        if not selected:
            return False
        self.token = uuid4().hex
        self.vault = vault
        self.mode = 'verify'
        self.export_items = selected.copy()
        self.queue, self.ready = selected, []
        for item in selected:
            item.export_status, item.message = 'A verificar', ''
        self.cancel_requested = False
        self.application.runtime.cancel_event.clear()
        self.application.set_state(True, 'batch')
        self._dispatch()
        return True

    @staticmethod
    def payload(item):
        session = item.session
        return session.result, session.document.toPlainText(), session.strip_markers, tuple(session.removals)

    def _dispatch(self):
        if self.cancel_requested:
            self._finish()
            return
        if not self.queue:
            if self.mode == 'verify' and self.ready:
                self.mode, self.queue = 'export', self.ready.copy()
            else:
                self._finish()
                return
        self.active = self.queue.pop(0)
        item = self.active
        self.progress = (0, 0)
        if self.mode == 'convert':
            item.status = 'Convertendo'
            self.work = self.application.runtime.allocate_workspace()
            self.message = f'Convertendo {self.items.index(item) + 1} de {len(self.items)}: {item.source.name}'
            command = ('batch_convert', self.token, item.id, str(item.source), str(self.work),
                       *((self.conversion_options,) if self.conversion_options.ocr_mode != 'auto' else ()))
        elif self.mode == 'verify':
            self.message = 'Verificando documentos selecionados…'
            record = item.session.exports.get(str(self.vault))
            command = ('batch_check', self.token, item.id, *self.payload(item), record)
        else:
            item.export_status = 'Salvando'
            self.message = f'Exportando {len(self.ready) - len(self.queue)} de {len(self.ready)}: {item.source.name}'
            command = ('batch_export', self.token, item.id, str(self.vault), *self.payload(item))
        self.application.runtime.commands.put(command)
        self.changed.emit()

    def handle(self, token, item_id, kind, *args):
        if token != self.token or not self.active or item_id != self.active.id or not self.running:
            return
        item = self.active
        if kind == 'stage':
            self.message = str(args[0])
            self.changed.emit()
            return
        if kind == 'progress':
            self.progress = tuple(args)
            self.progress_changed.emit()
            return
        if self.mode == 'convert':
            if kind == 'converted':
                item.session = self.hooks.create_session(args[0])
                item.status = 'Convertido'
            else:
                item.status = 'Cancelado' if kind == 'cancelled' else 'Falhou'
                item.included = False
                item.message = str(args[0]) if args else 'Conversão cancelada.'
                shutil.rmtree(self.work, ignore_errors=True)
            self.work = None
        elif kind == 'checked':
            signature, unchanged, target = args
            if unchanged:
                item.export_status, item.target = 'Já salvo', target
                item.session.record_export(self.vault, signature, target,
                                           item.session.exports[str(self.vault)].manifest)
            else:
                item.export_status = 'A exportar'
                previous = item.session.exports.get(str(self.vault))
                if previous and previous.signature == signature:
                    item.message = 'Publicação anterior alterada ou incompleta; será preservada em outra pasta.'
                self.ready.append(item)
        elif kind == 'exported':
            signature, target, *manifest = args
            item.export_status, item.target = 'Salvo', target
            item.session.record_export(self.vault, signature, target, manifest[0] if manifest else None)
        else:
            item.export_status = 'Cancelado' if kind == 'cancelled' else 'Falhou'
            item.message = str(args[0]) if args else 'Exportação cancelada.'
        self.active = None
        self._dispatch()

    def cancel(self):
        if self.running and not self.cancel_requested:
            self.cancel_requested = True
            self.application.runtime.cancel_event.set()
            self.message = ('Finalizando gravação; o lote será interrompido.' if self.mode == 'export'
                            else 'Cancelando; os documentos concluídos serão preservados…')
            self.changed.emit()

    def _finish(self):
        if self.mode == 'convert':
            for item in self.queue:
                item.status, item.included = 'Não executado', False
            done = sum(item.session is not None for item in self.items)
            failed = sum(item.status == 'Falhou' for item in self.items)
            self.message = f'{done} convertido(s), {failed} falha(s). Selecione um documento para revisar.'
        else:
            for item in self.items:
                if item.export_status in ('A verificar', 'A exportar'):
                    item.export_status = 'Não exportado'
            saved = sum(item.export_status == 'Salvo' for item in self.export_items)
            skipped = sum(item.export_status == 'Já salvo' for item in self.export_items)
            failed = sum(item.export_status == 'Falhou' for item in self.export_items)
            self.message = f'{saved} salvo(s), {skipped} já salvo(s), {failed} falha(s).'
        if self.cancel_requested:
            self.message = 'Operação interrompida. ' + self.message
        self.active = None
        self.queue = []
        self.mode = None
        self.application.set_state(False, None)
        self.changed.emit()

    def worker_failed(self):
        if not self.running:
            return
        if self.active:
            if self.mode == 'convert':
                self.active.status, self.active.included = 'Falhou', False
                if self.work:
                    shutil.rmtree(self.work, ignore_errors=True)
            else:
                self.active.export_status = 'Falhou'
            self.active.message = 'O processo de PDF terminou inesperadamente.'
        self.cancel_requested = True
        self._finish()
