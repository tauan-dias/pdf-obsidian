"""Contratos da fachada sem janela; documentos e destinos sempre sintéticos."""
from pathlib import Path
from queue import Queue
from types import SimpleNamespace
import os
import subprocess
import sys
import tempfile
import threading

import pytest
from PySide6.QtCore import QUrl

from pdf_obsidian.application import ApplicationController
from pdf_obsidian.batch import BatchHooks


class MemoryRuntime:
    def __init__(self, root):
        self.root = root
        root.mkdir()
        self.workspaces = []
        self.commands, self.events = Queue(), Queue()
        self.cancel_event = threading.Event()
        self.alive = True
        self.close_count = 0
        self.worker = SimpleNamespace(is_alive=lambda: self.alive)

    def allocate_workspace(self):
        workspace = Path(tempfile.mkdtemp(dir=self.root))
        self.workspaces.append(workspace)
        return workspace

    def close(self):
        self.close_count += 1
        self.alive = False


@pytest.fixture
def controller(app, tmp_path):
    runtime = MemoryRuntime(tmp_path / 'runtime')
    controller = ApplicationController(runtime=runtime)
    yield controller
    controller.shutdown()


def test_local_url_progress_and_result_handoff(controller, tmp_path):
    runtime = controller.runtime
    assert not controller.startConversion(QUrl('https://example.org/material.pdf'))
    assert not controller.startConversion(QUrl())
    assert runtime.commands.empty() and runtime.workspaces == []
    source = tmp_path / 'aula com ação 💡.pdf'
    assert controller.startConversion(QUrl.fromLocalFile(str(source)))
    assert controller.busy and controller.operation == 'convert'
    assert controller.sourceName == source.name
    assert controller.sourcePath == str(source)
    assert runtime.commands.get_nowait()[0:2] == ('convert', str(source))
    assert not controller.start_conversion(source)
    assert len(runtime.workspaces) == 1
    progress = []
    controller.progressChanged.connect(lambda: progress.append((controller.progressCurrent, controller.progressTotal)))
    runtime.events.put(('progress', 3, 10))
    runtime.events.put(('progress', 3, 10))
    controller.poll()
    assert progress == [(3, 10)]

    results = []
    sentinel = object()
    def receive(result):
        results.append(result)
        # A frontend may schedule the first PDF render during this callback.
        controller.set_state(True, 'render')
    controller.conversionCompleted.connect(receive)
    runtime.events.put(('converted', sentinel))
    runtime.events.put(('progress', 9, 10))  # no longer a conversion
    controller.poll()
    assert results == [sentinel]
    assert controller.busy and controller.operation == 'render'
    assert progress == [(3, 10)]


def test_recognition_status_tracks_mode_without_changing_active_work(controller, monkeypatch):
    updates = []
    controller.conversionOptionsChanged.connect(lambda: updates.append(controller.recognitionStatus))
    assert 'OCR indisponível' in controller.recognitionStatus
    assert controller.ocrMode == 'off' and not controller.ocrAvailable
    controller.setOcrMode('auto')
    assert controller.ocrMode == 'off' and not updates
    monkeypatch.setattr('pdf_obsidian.application.resource_status', lambda: (True, 'OCR local pronto', {}))
    controller.setOcrMode('auto')
    assert controller.ocrMode == 'auto' and updates == ['OCR local pronto']
    controller.setOcrMode('off')
    assert updates[-1] == 'OCR desligado. Apenas texto nativo e imagens serão extraídos.'
    controller.set_state(True, 'convert')
    controller.setOcrMode('auto')
    assert controller.ocrMode == 'off' and len(updates) == 2
    controller.set_state(False, '')
    controller.setOcrMode('auto')
    assert controller.ocrMode == 'auto' and updates[-1] == 'OCR local pronto'


@pytest.mark.parametrize('event,signal', [('cancelled', 'conversionCancelled'), ('error', 'operationFailed')])
def test_conversion_terminal_states_preserve_workspaces(controller, tmp_path, event, signal):
    assert controller.start_conversion(tmp_path / 'sintetico.pdf')
    delivered = []
    getattr(controller, signal).connect(lambda *args: delivered.append(args))
    cancellations = []
    controller.cancellationChanged.connect(lambda: cancellations.append(controller.cancellationRequested))
    controller.cancelConversion()
    controller.cancelConversion()
    assert cancellations == [True]
    assert controller.cancellationRequested
    assert controller.runtime.cancel_event.is_set()
    controller.runtime.events.put((event, 'Falha sintética') if event == 'error' else (event,))
    controller.poll()
    assert not controller.busy and controller.operation == ''
    assert not controller.cancellationRequested
    assert cancellations == [True, False]
    assert (controller.progressCurrent, controller.progressTotal) == (0, 1)
    expected = [('Falha sintética',)] if event == 'error' else [()]
    assert delivered == expected
    assert controller.runtime.workspaces[0].exists()
    assert controller.start_conversion(tmp_path / 'nova.pdf')
    assert not controller.runtime.cancel_event.is_set()


def test_crop_render_and_close_during_result_delivery(controller, tmp_path):
    events = []
    controller.cropCompleted.connect(events.append)
    assert controller.start_crop(tmp_path / 'pdf.pdf', tmp_path, 2, [1, 2, 30, 40])
    assert not controller.start_crop(tmp_path / 'pdf.pdf', tmp_path, 2, [1, 2, 30, 40])
    command = controller.runtime.commands.get_nowait()
    assert command == ('crop', str(tmp_path / 'pdf.pdf'), str(tmp_path), 2, (1, 2, 30, 40))
    controller.runtime.events.put(('cropped', 'assets/recorte.png'))
    controller.poll()
    assert events == ['assets/recorte.png'] and not controller.busy
    rendered = []
    controller.renderCompleted.connect(lambda kind, args: rendered.append((kind, args)))
    request = (12, str(tmp_path / 'pdf.pdf'), 2, 100, str(tmp_path / 'page.png'))
    assert controller.dispatch_render(request)
    assert controller.runtime.commands.get_nowait() == ('render', *request)
    controller.set_state(True, 'render')
    controller.runtime.events.put(('rendered', 12, 2, request[-1], (0, 0, 100, 200)))
    controller.poll()
    assert rendered[0][0] == 'rendered'
    # The PDF adapter, rather than the transport, decides when rendering is idle.
    assert controller.operation == 'render'
    controller.conversionCompleted.connect(lambda _: controller.shutdown())
    controller.runtime.events.put(('converted', object()))
    controller.poll()
    controller.shutdown()
    assert controller.runtime.close_count == 1
    assert not controller.workerAvailable
    assert not controller.start_conversion(tmp_path / 'pdf.pdf')


def make_hooks(allowed=True):
    sessions, snapshots = [], []
    def factory(result):
        session = SimpleNamespace(result=result, id=str(len(sessions)), exports={}, removals=[], strip_markers=False)
        session.document = SimpleNamespace(toPlainText=lambda: 'Markdown editado')
        session.record_export = lambda vault, signature, target, manifest=None: session.exports.update(
            {str(vault): SimpleNamespace(signature=signature, target=Path(target), manifest=manifest or {})})
        sessions.append(session)
        return session
    hooks = BatchHooks(lambda: allowed, lambda: snapshots.append(True), factory)
    return hooks, sessions, snapshots


def test_batch_without_window_retains_rows_sessions_and_cancel(controller, tmp_path):
    hooks, sessions, snapshots = make_hooks()
    batch = controller.attach_batch(hooks)
    source = tmp_path / 'a.pdf'
    alias = tmp_path / 'atalho.pdf'
    source.write_bytes(b'synthetic placeholder')
    alias.symlink_to(source)
    assert batch.start([source, alias, tmp_path / 'b.pdf'])
    assert len(batch.items) == 2 and snapshots == [True]
    rows = batch.items.copy()
    current = controller.runtime.commands.get_nowait()
    assert current[:3] == ('batch_convert', batch.token, rows[0].id)
    workspace = batch.work
    controller.runtime.events.put(('batch', 'obsolete', rows[0].id, 'converted', object()))
    controller.poll()
    assert sessions == []
    changes, progress = [], []
    batch.changed.connect(lambda: changes.append(True))
    batch.progress_changed.connect(lambda: progress.append(batch.progress))
    controller.runtime.events.put(('batch', batch.token, rows[0].id, 'progress', 1, 4))
    controller.poll()
    assert progress == [(1, 4)] and changes == []
    controller.runtime.events.put(('batch', batch.token, rows[0].id, 'converted', object()))
    controller.poll()
    assert rows[0].session is sessions[0] and workspace.exists()
    assert batch.active is rows[1]
    second_workspace = batch.work
    batch.cancel()
    batch.cancel()
    controller.runtime.events.put(('batch', batch.token, rows[1].id, 'cancelled'))
    controller.poll()
    assert not batch.running and not controller.busy
    assert all(before is after for before, after in zip(rows, batch.items))
    assert rows[0].session is sessions[0] and workspace.exists()
    assert not second_workspace.exists()
    assert rows[1].status == 'Cancelado'


def test_batch_prepare_veto_and_export_protocol_without_window(controller, tmp_path):
    hooks, _, _ = make_hooks(False)
    batch = controller.attach_batch(hooks)
    assert not batch.start([tmp_path / 'a.pdf'])
    assert controller.runtime.commands.empty() and not controller.busy
    hooks, sessions, snapshots = make_hooks()
    batch.hooks = hooks
    assert batch.start([tmp_path / 'a.pdf'])
    controller.runtime.commands.get_nowait()
    controller.runtime.events.put(('batch', batch.token, batch.active.id, 'converted', object()))
    controller.poll()
    item = batch.items[0]
    assert not batch.running
    vault = tmp_path / 'vault'
    vault.mkdir()
    assert batch.export_selected(vault)
    command = controller.runtime.commands.get_nowait()
    assert command[0] == 'batch_check' and command[4] == 'Markdown editado'
    controller.runtime.events.put(('batch', batch.token, item.id, 'checked', 'signature', False, ''))
    controller.poll()
    assert controller.runtime.commands.get_nowait()[0] == 'batch_export'
    target = vault / 'Importados' / 'a'
    controller.runtime.events.put(('batch', batch.token, item.id, 'exported', 'signature', str(target)))
    controller.poll()
    assert item.export_status == 'Salvo' and not controller.busy
    assert item.session is sessions[0]
    assert batch.export_selected(vault)
    controller.runtime.commands.get_nowait()
    controller.runtime.events.put(('batch', batch.token, item.id, 'checked', 'signature', True, str(target)))
    controller.poll()
    assert item.export_status == 'Já salvo' and not batch.running
    assert controller.runtime.commands.empty()


def test_worker_failure_is_reported_once_and_blocks_new_jobs(controller, tmp_path):
    hooks, sessions, _ = make_hooks()
    batch = controller.attach_batch(hooks)
    assert batch.start([tmp_path / 'a.pdf', tmp_path / 'b.pdf'])
    controller.runtime.events.put(('batch', batch.token, batch.active.id, 'converted', object()))
    controller.poll()
    delivered = []
    controller.workerFailed.connect(lambda: delivered.append(True))
    controller.runtime.alive = False
    controller.poll()
    controller.poll()
    assert delivered == [True]
    assert not batch.running and controller.busy and controller.operation == ''
    assert batch.items[0].session is sessions[0]
    assert batch.items[1].status == 'Falhou'
    assert not controller.workerAvailable
    assert not controller.start_conversion(tmp_path / 'c.pdf')
    assert not batch.start([tmp_path / 'c.pdf'])


def test_real_worker_with_qcoreapplication_and_no_widgets(tmp_path):
    script = tmp_path / 'headless_application.py'
    script.write_text('''
from pathlib import Path
import hashlib
import sys
import time
import pymupdf
from PySide6.QtCore import QCoreApplication, QUrl
from pdf_obsidian.application import ApplicationController

def main():
    app = QCoreApplication([])
    source = Path(sys.argv[1]) / 'sintetico.pdf'
    with pymupdf.open() as pdf:
        page = pdf.new_page()
        page.insert_text((50, 100), 'Conteudo sintetico sem widgets.')
        pdf.save(source)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    controller = ApplicationController()
    root = controller.runtime.root
    results, errors = [], []
    controller.conversionCompleted.connect(results.append)
    controller.operationFailed.connect(errors.append)
    try:
        assert 'PySide6.QtWidgets' not in sys.modules
        assert controller.startConversion(QUrl.fromLocalFile(str(source)))
        deadline = time.monotonic() + 15
        while controller.busy:
            app.processEvents()
            controller.poll()
            assert time.monotonic() < deadline
            time.sleep(.01)
        assert not errors and len(results) == 1
        assert 'Conteudo sintetico sem widgets.' in results[0].markdown
        assert results[0].workspace.exists()
        assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
        invalid = source.with_name('invalido.pdf')
        invalid.write_bytes(b'not a PDF')
        assert controller.startConversion(QUrl.fromLocalFile(str(invalid)))
        deadline = time.monotonic() + 15
        while controller.busy:
            app.processEvents()
            controller.poll()
            assert time.monotonic() < deadline
            time.sleep(.01)
        assert len(results) == 1 and len(errors) == 1
        assert results[0].workspace.exists()
        assert 'PySide6.QtWidgets' not in sys.modules
    finally:
        controller.shutdown()
    assert not root.exists()
    assert not controller.runtime.worker.is_alive()

if __name__ == '__main__':
    main()
''')
    env = dict(os.environ, PYTHONPATH=str(Path('src').resolve()))
    completed = subprocess.run([sys.executable, str(script), str(tmp_path)], env=env,
                               capture_output=True, text=True, timeout=35)
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_facade_properties_are_not_writable_from_qml(controller, tmp_path):
    from PySide6.QtQml import QQmlComponent, QQmlEngine
    engine = QQmlEngine()
    QQmlEngine.setObjectOwnership(controller, QQmlEngine.ObjectOwnership.CppOwnership)
    component = QQmlComponent(engine)
    component.setData(b"""
import QtQml
QtObject {
    required property QtObject application
    readonly property bool running: application.busy
    readonly property string operation: application.operation
    readonly property string sourceName: application.sourceName
    readonly property int current: application.progressCurrent
    readonly property int total: application.progressTotal
}
""", QUrl())
    assert not component.isError(), [error.toString() for error in component.errors()]
    view = component.createWithInitialProperties({'application': controller})
    assert view is not None
    view.setParent(engine)
    try:
        assert not view.property('running') and view.property('operation') == ''
        meta = controller.metaObject()
        for name in ('busy', 'operation', 'sourceName', 'progressCurrent', 'progressTotal', 'workerAvailable', 'cancellationRequested'):
            prop = meta.property(meta.indexOfProperty(name))
            assert prop.hasNotifySignal() and not prop.isWritable()
        assert controller.start_conversion(tmp_path / 'aula.pdf')
        assert view.property('running') and view.property('operation') == 'convert'
        assert view.property('sourceName') == 'aula.pdf'
        controller.runtime.events.put(('progress', 4, 12))
        controller.poll()
        assert (view.property('current'), view.property('total')) == (4, 12)
    finally:
        # Disconnect the consumer and let Qt destroy its parent-owned objects.
        view.deleteLater()
        engine.deleteLater()
        from PySide6.QtCore import QCoreApplication, QEvent
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_tagged_session_operations_reject_late_progress_and_terminal_results(controller, tmp_path):
    controller.tagged_operations = True
    results = []
    controller.conversionCompleted.connect(results.append)
    assert controller.start_conversion(tmp_path / 'sintetico.pdf')
    command = controller.runtime.commands.get_nowait()
    assert command[0] == 'session_convert'
    token = command[1]
    controller.runtime.events.put(('session_event', 'obsolete', 'converted', 'wrong'))
    controller.runtime.events.put(('converted', 'untagged'))
    controller.runtime.events.put(('session_event', token, 'progress', 2, 5))
    controller.poll()
    assert results == [] and controller.busy and controller.progressCurrent == 2
    controller.runtime.events.put(('session_event', token, 'converted', 'valid'))
    controller.poll()
    assert results == ['valid'] and not controller.busy
    assert controller.start_crop(tmp_path / 'sintetico.pdf', tmp_path, 1, (0, 0, 10, 10))
    crop = controller.runtime.commands.get_nowait()
    assert crop[0] == 'session_crop' and crop[1] != token
    controller.runtime.events.put(('session_event', token, 'error', 'late'))
    controller.poll()
    assert controller.busy and controller.operation == 'crop'
    crops = []
    controller.cropCompleted.connect(crops.append)
    controller.runtime.events.put(('session_event', crop[1], 'cropped', 'assets/crop.png'))
    controller.poll()
    assert crops == ['assets/crop.png'] and not controller.busy


def test_batch_uses_one_immutable_ocr_snapshot(controller,tmp_path):
    from pdf_obsidian.recognition import ConversionOptions
    c=controller
    c.setOcrMode('off')
    b=c.attach_batch(BatchHooks(lambda:True,lambda:None,lambda result:result))
    assert b.start([tmp_path/'one.pdf',tmp_path/'two.pdf'])
    first=c.runtime.commands.get_nowait()
    assert first[0]=='batch_convert' and first[-1]==ConversionOptions('off')
    # Even a programmatic change cannot change the batch snapshot.
    c.conversion_options=ConversionOptions('auto')
    b.handle(b.token,b.active.id,'stage','Página 1 · reconhecendo…')
    assert b.message=='Página 1 · reconhecendo…'
    b.handle(b.token,b.active.id,'converted',SimpleNamespace())
    second=c.runtime.commands.get_nowait()
    assert second[0]=='batch_convert' and second[-1]==ConversionOptions('off')
    b.handle(b.token,b.active.id,'cancelled')
    assert not b.running
