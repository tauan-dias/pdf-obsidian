"""Preparação acionada pela interface, sem downloads nos testes."""
from types import SimpleNamespace

from pdf_obsidian.ocr_setup import OcrSetup
from pdf_obsidian.application import ApplicationController


def test_setup_launch_progress_success_and_duplicate_guard(app, monkeypatch, tmp_path):
    calls = []
    process = SimpleNamespace(poll=lambda: None)
    def launch(command, **kwargs):
        calls.append((command, kwargs))
        kwargs['stdout'].write(b'Baixando modelos\n')
        kwargs['stdout'].flush()
        return process
    monkeypatch.setattr('pdf_obsidian.ocr_setup.subprocess.Popen', launch)
    monkeypatch.setenv('PDF_OBSIDIAN_OCR_DIR', str(tmp_path / 'recursos'))
    setup = OcrSetup()
    setup.start()
    setup.start()
    assert len(calls) == 1 and setup.running
    assert calls[0][0][-2:] == ['--directory', str(tmp_path / 'recursos')]
    assert calls[0][1]['start_new_session']
    setup.poll()
    assert 'Baixando modelos' in setup.message
    process.poll = lambda: 0
    setup.poll()
    assert not setup.running and 'verificado' in setup.message
    assert setup.log_path.is_file()


def test_setup_failure_retry_and_cancel(app, monkeypatch):
    process = SimpleNamespace(poll=lambda: 1, pid=123, wait=lambda: None)
    monkeypatch.setattr('pdf_obsidian.ocr_setup.subprocess.Popen', lambda *a, **kw: process)
    killed = []
    monkeypatch.setattr('pdf_obsidian.ocr_setup.os.killpg', lambda *args: killed.append(args))
    setup = OcrSetup()
    setup.start()
    setup.poll()
    assert 'Falha' in setup.message and str(setup.log_path) in setup.message
    setup.start()
    setup.cancel()
    assert killed and not setup.running and 'cancelada' in setup.message


def test_setup_launch_failure(app, monkeypatch):
    def fail(*args, **kwargs):
        raise OSError('Sem espaço')
    monkeypatch.setattr('pdf_obsidian.ocr_setup.subprocess.Popen', fail)
    setup = OcrSetup()
    setup.start()
    assert not setup.running and 'Sem espaço' in setup.message


def test_controller_setup_blocks_conversion_and_shutdown_cancels(app, monkeypatch, tmp_path):
    from test_application import MemoryRuntime
    process = SimpleNamespace(poll=lambda: -9, pid=123, wait=lambda: None)
    monkeypatch.setattr('pdf_obsidian.ocr_setup.subprocess.Popen', lambda *a, **kw: process)
    killed = []
    monkeypatch.setattr('pdf_obsidian.ocr_setup.os.killpg', lambda *args: killed.append(args))
    controller = ApplicationController(runtime=MemoryRuntime(tmp_path / 'runtime'))
    controller.set_state(True, 'convert')
    controller.prepareOcr()
    assert not controller.ocrPreparing
    controller.set_state(False, None)
    controller.prepareOcr()
    assert controller.ocrPreparing and not controller.ocrAvailable
    assert not controller.start_conversion(tmp_path / 'sintetico.pdf')
    controller.shutdown()
    assert killed and not controller.ocrPreparing


def test_retry_repairs_partially_created_environment(monkeypatch, tmp_path):
    from pdf_obsidian import prepare_ocr
    python = tmp_path / 'environment/bin/python'
    python.parent.mkdir(parents=True)
    python.touch()
    created = []
    monkeypatch.setattr('sys.argv', ['prepare-ocr', '--directory', str(tmp_path)])
    monkeypatch.setattr(prepare_ocr.venv, 'EnvBuilder', lambda **kw: SimpleNamespace(create=created.append))
    monkeypatch.setattr(prepare_ocr.subprocess, 'run', lambda *a, **kw: None)
    monkeypatch.setattr(prepare_ocr, 'verify_resources', lambda *a, **kw: {})
    assert prepare_ocr.main() == 0
    assert created == [tmp_path / 'environment']
