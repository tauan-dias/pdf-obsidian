"""Preparação explícita em subprocesso, sem bloquear a interface."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile

from PySide6.QtCore import QObject, QTimer, Signal

from .recognition import resource_directory


class OcrSetup(QObject):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.process = None
        self.message = ''
        self.cancelled = False
        self.log_path = None
        self.timer = QTimer(self)
        self.timer.setInterval(500)
        self.timer.timeout.connect(self.poll)

    @property
    def running(self):
        return self.process is not None

    def start(self):
        if self.running:
            return
        self.cancelled = False
        self.message = 'Preparando OCR… Baixando e verificando dependências e modelos. Isso pode levar vários minutos.'
        try:
            descriptor, name = tempfile.mkstemp(prefix='pdf-obsidian-ocr-', suffix='.log')
            self.log_path = Path(name)
            with os.fdopen(descriptor, 'wb') as output:
                env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parent.parent), PYTHONUNBUFFERED='1')
                self.process = subprocess.Popen(
                    [sys.executable, '-m', 'pdf_obsidian.prepare_ocr', '--directory', str(resource_directory())],
                    stdout=output, stderr=subprocess.STDOUT, env=env, start_new_session=True)
        except OSError as exc:
            self.message = f'Não foi possível preparar OCR: {exc}. Tente novamente.'
        if self.running:
            self.timer.start()
        self.changed.emit()

    def poll(self):
        if not self.running:
            return
        code = self.process.poll()
        if code is None:
            try:
                with self.log_path.open('rb') as log:
                    log.seek(0, 2)
                    log.seek(max(0, log.tell() - 2048))
                    lines = log.read().decode('utf-8', errors='replace').splitlines()
                if lines:
                    message = 'Preparando OCR… ' + lines[-1][-180:]
                    if message != self.message:
                        self.message = message
                        self.changed.emit()
            except OSError:
                pass
            return
        self.process = None
        self.timer.stop()
        if self.cancelled:
            self.message = 'Preparação cancelada. Você pode tentar novamente; os arquivos baixados foram mantidos.'
        elif code == 0:
            self.message = 'OCR preparado e verificado. Disponível nas próximas conversões.'
        else:
            self.message = f'Falha na preparação do OCR. Confira a conexão e o espaço em disco e tente novamente. Log: {self.log_path}'
        self.changed.emit()

    def cancel(self):
        if self.running:
            self.cancelled = True
            # Encerra também pip e os subprocessos de download, antes de liberar os recursos.
            try:
                os.killpg(self.process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            self.process.wait()
            self.poll()

    def close(self):
        self.cancel()
