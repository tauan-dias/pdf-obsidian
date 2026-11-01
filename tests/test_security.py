import subprocess
import sys

import pytest
import pymupdf
from PySide6.QtCore import QUrl
from PySide6.QtGui import QImage, QTextDocument

from pdf_obsidian.comparison import preview_document
from pdf_obsidian.pdf import render


def test_preview_confines_images(app, tmp_path):
    workspace = tmp_path / 'session'
    assets = workspace / 'assets'
    assets.mkdir(parents=True)
    image = QImage(2, 2, QImage.Format.Format_RGB32)
    image.fill(0)
    outside = tmp_path / 'private.png'
    image.save(str(outside))
    image.save(str(assets / 'valid.png'))
    (assets / 'symlink.png').symlink_to(outside)
    doc = preview_document('', workspace)
    for name in (outside.as_uri(), '../private.png', 'assets/symlink.png',
                 'https://example.invalid/a.png', 'data:image/png;base64,AAAA'):
        assert doc.resource(QTextDocument.ResourceType.ImageResource, QUrl(name)) is None
    assert not doc.resource(QTextDocument.ResourceType.ImageResource, QUrl('assets/valid.png')).isNull()


def test_huge_pdf_rejected_before_render(tmp_path):
    source = tmp_path / 'huge.pdf'
    with pymupdf.open() as doc:
        doc.new_page(width=14000, height=14000)
        doc.save(source)
    original = source.read_bytes()
    with pytest.raises(ValueError, match='limite seguro'):
        render(source, 1, tmp_path / 'out.png')
    assert source.read_bytes() == original
    assert not (tmp_path / 'out.png').exists()


def test_native_network_denied():
    result = subprocess.run([sys.executable, '-c', '''
import ctypes, socket
from pdf_obsidian.sandbox import restrict_network
restrict_network()
lib = ctypes.CDLL(None, use_errno=True)
for kind in (socket.SOCK_STREAM, socket.SOCK_DGRAM):
    assert lib.socket(socket.AF_INET, kind, 0) == -1
    assert ctypes.get_errno() == 1
    assert lib.socket(socket.AF_INET6, kind, 0) == -1
with socket.socket(socket.AF_UNIX):
    pass
'''], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_watchdog_terminates_blocked_operation():
    result = subprocess.run([sys.executable, '-c', '''
import ctypes, queue
from pdf_obsidian.worker_guard import GuardedCommands
q = queue.Queue(); q.put(('render',))
commands = GuardedCommands(q, timeout=.1)
commands.get()
ctypes.PyDLL(None).sleep(5)
'''], capture_output=True, timeout=10)
    assert result.returncode == -9


def test_ocr_lock_covers_all_pins():
    from pathlib import Path
    import re
    import pdf_obsidian
    root = Path(pdf_obsidian.__file__).parent
    pins = set((root / 'ocr_requirements.txt').read_text().splitlines())
    lock = (root / 'ocr_requirements.lock').read_text()
    entries = re.findall(r'^([^#\s].*?) \\\n((?:    --hash=sha256:[0-9a-f]{64}(?: \\)?\n)+)', lock, re.M)
    assert {pin for pin, _ in entries} == pins


def test_landlock_confines_filesystem(tmp_path):
    allowed = tmp_path / 'allowed'
    allowed.mkdir()
    secret = tmp_path / 'secret.txt'
    secret.write_text('private synthetic')
    script = '''
import pathlib, sys
from pdf_obsidian.sandbox import restrict_filesystem
allowed, secret = map(pathlib.Path, sys.argv[1:])
restrict_filesystem(['/usr', '/lib'], [allowed])
(allowed/'result').write_text('ok')
assert (allowed/'result').read_text() == 'ok'
for operation in (lambda: secret.read_text(), lambda: secret.write_text('bad')):
    try: operation()
    except PermissionError: pass
    else: raise AssertionError('Escaped filesystem policy')
'''
    result = subprocess.run([sys.executable, '-c', script, str(allowed), str(secret)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert secret.read_text() == 'private synthetic'


@pytest.mark.parametrize('budget', ['memory', 'disk'])
def test_watchdog_enforces_budget(tmp_path, budget):
    (tmp_path / 'synthetic.bin').write_bytes(b'x' * 2048)
    script = '''
import ctypes, queue, sys
from pdf_obsidian.worker_guard import GuardedCommands
q = queue.Queue(); q.put(('convert',))
kwargs = {'memory_limit': 1} if sys.argv[2] == 'memory' else {'disk_limit': 1}
g = GuardedCommands(q, workspace=sys.argv[1], **kwargs)
g.get()
ctypes.PyDLL(None).sleep(5)
'''
    result = subprocess.run([sys.executable, '-c', script, str(tmp_path), budget], timeout=10)
    assert result.returncode == -9
    assert (tmp_path / 'synthetic.bin').read_bytes() == b'x' * 2048


def test_pip_offline_rejects_tampered_wheel(tmp_path):
    import hashlib
    import zipfile
    wheels = tmp_path / 'wheels'
    wheels.mkdir()
    wheel = wheels / 'audit_fixture-1.0-py3-none-any.whl'
    with zipfile.ZipFile(wheel, 'w') as archive:
        archive.writestr('audit_fixture/__init__.py', 'VALUE = 1\n')
        archive.writestr('audit_fixture-1.0.dist-info/METADATA',
                         'Metadata-Version: 2.1\nName: audit-fixture\nVersion: 1.0\n')
        archive.writestr('audit_fixture-1.0.dist-info/WHEEL',
                         'Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n')
        archive.writestr('audit_fixture-1.0.dist-info/RECORD', '')
    lock = tmp_path / 'requirements.txt'
    lock.write_text('audit-fixture==1.0 --hash=sha256:' + hashlib.sha256(wheel.read_bytes()).hexdigest())
    def install(target):
        return subprocess.run([sys.executable, '-m', 'pip', '--isolated', 'install', '--no-index',
                               '--find-links', str(wheels), '--require-hashes', '--only-binary=:all:',
                               '--no-deps', '--target', str(target), '-r', str(lock)], capture_output=True, text=True)
    result = install(tmp_path / 'valid')
    assert result.returncode == 0, result.stderr
    assert (tmp_path / 'valid/audit_fixture/__init__.py').is_file()
    with wheel.open('ab') as stream:
        stream.write(b'tampered')
    result = install(tmp_path / 'rejected')
    assert result.returncode != 0
    assert 'HASHES' in result.stderr.upper()
    assert not (tmp_path / 'rejected/audit_fixture').exists()


def test_preview_rejects_non_png_and_special_files(app, tmp_path):
    import os
    assets = tmp_path / 'assets'
    assets.mkdir()
    (assets / 'active.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" width="5" height="5"/>')
    os.mkfifo(assets / 'pipe.png')
    doc = preview_document('', tmp_path)
    for name in ('assets/active.svg', 'assets/pipe.png'):
        assert doc.resource(QTextDocument.ResourceType.ImageResource, QUrl(name)) is None


def test_preview_uses_opened_bytes_if_path_changes(app, tmp_path, monkeypatch):
    import os
    assets = tmp_path / 'assets'
    assets.mkdir()
    image = QImage(2, 2, QImage.Format.Format_RGB32)
    image.fill(0)
    original = assets / 'valid.png'
    image.save(str(original))
    outside = tmp_path / 'external.png'
    image = QImage(3, 3, QImage.Format.Format_RGB32)
    image.fill(0)
    image.save(str(outside))
    real_open = os.open
    def swapped_open(path, flags, *args, **kwargs):
        descriptor = real_open(path, flags, *args, **kwargs)
        if path == 'valid.png':
            original.rename(assets / 'old.png')
            original.symlink_to(outside)
        return descriptor
    monkeypatch.setattr('pdf_obsidian.comparison.os.open', swapped_open)
    doc = preview_document('', tmp_path)
    resource = doc.resource(QTextDocument.ResourceType.ImageResource, QUrl('assets/valid.png'))
    assert resource.width() == resource.height() == 2


def test_preview_rejects_oversized_png_header(app, tmp_path):
    import struct
    import zlib
    assets = tmp_path / 'assets'
    assets.mkdir()
    def chunk(kind, data):
        return struct.pack('!I', len(data)) + kind + data + struct.pack('!I', zlib.crc32(kind + data))
    payload = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!IIBBBBB', 30000, 30000, 8, 2, 0, 0, 0))
    payload += chunk(b'IDAT', zlib.compress(b'\0')) + chunk(b'IEND', b'')
    (assets / 'huge.png').write_bytes(payload)
    doc = preview_document('', tmp_path)
    assert doc.resource(QTextDocument.ResourceType.ImageResource, QUrl('assets/huge.png')) is None


def test_ocr_memory_accounting_includes_descendants():
    from pathlib import Path
    from pdf_obsidian.recognition import process_tree_rss
    parent = subprocess.Popen([sys.executable, '-u', '-c', '''
import subprocess,sys,time
child=subprocess.Popen([sys.executable,'-u','-c',"import time; data=bytearray(16000000); print('ready',flush=True); time.sleep(30)"], stdout=subprocess.PIPE)
assert child.stdout.readline().strip()==b'ready'
print(child.pid,flush=True)
try: time.sleep(30)
finally: child.terminate();child.wait()
'''], stdout=subprocess.PIPE, text=True, start_new_session=True)
    try:
        child_pid = int(parent.stdout.readline())
        def rss(pid):
            return next(int(line.split()[1])*1024 for line in Path(f'/proc/{pid}/status').read_text().splitlines() if line.startswith('VmRSS:'))
        assert process_tree_rss(parent.pid) >= rss(parent.pid) + rss(child_pid)
    finally:
        import os
        import signal
        os.killpg(parent.pid, signal.SIGTERM)
        parent.wait(timeout=5)


def test_ocr_does_not_inherit_cumulative_parser_cpu_budget():
    result = subprocess.run([sys.executable, '-c', '''
import resource
from pdf_obsidian.recognition_engine import reset_inherited_cpu_budget
_, hard = resource.getrlimit(resource.RLIMIT_CPU)
resource.setrlimit(resource.RLIMIT_CPU,(1, hard))
reset_inherited_cpu_budget()
assert resource.getrlimit(resource.RLIMIT_CPU) == (hard, hard)
'''], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
