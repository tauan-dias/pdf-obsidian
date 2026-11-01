"""Pure contracts, resource validation and cancellable OCR subprocess client."""
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json
import math
import os
import selectors
import signal
import subprocess
import sys
import time
from uuid import uuid4


@dataclass(frozen=True)
class ConversionOptions:
    ocr_mode: str = 'auto'

    def __post_init__(self):
        if self.ocr_mode not in ('auto', 'off'):
            raise ValueError('Modo OCR inválido: use auto ou off.')


def resource_directory():
    return Path(os.environ.get('PDF_OBSIDIAN_OCR_DIR', Path(sys.prefix) / 'share/pdf-obsidian/ocr')).resolve()


def trusted_model_hashes():
    return json.loads(Path(__file__).with_name('ocr_trusted_models.json').read_text())


def verify_trusted_models(root, check=None):
    """Autenticar artefatos usando hashes distribuídos com a aplicação."""
    root = Path(root).resolve()
    expected = trusted_model_hashes()
    for relative, digest in expected.items():
        path = root / relative
        if not path.resolve().is_relative_to(root) or not path.is_file():
            raise RuntimeError(f'Modelo oficial ausente ou caminho inválido: {relative}')
        actual = sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                if check:
                    check()
                actual.update(chunk)
        if actual.hexdigest() != digest:
            raise RuntimeError(f'Recurso OCR corrompido ou não aprovado: {relative}')
    return expected


def resource_status(root=None, *, require_environment=True):
    root = Path(root) if root is not None else resource_directory()
    try:
        manifest = json.loads((root / 'manifest.json').read_text())
        if not isinstance(manifest, dict) or manifest.get('schema') != 1 or not isinstance(manifest.get('files'), dict) or not manifest['files']:
            raise ValueError('Manifesto inválido')
        if require_environment and not (root / 'environment/bin/python').is_file():
            raise ValueError('Ambiente OCR ausente')
        if any(not name or Path(name).is_absolute() or '..' in Path(name).parts
               or not (root / name).resolve().is_relative_to(root.resolve())
               for name in manifest['files']):
            raise ValueError('Caminho inválido no manifesto')
        if any(not isinstance(digest, str) or len(digest) != 64
               or any(char not in '0123456789abcdef' for char in digest)
               for digest in manifest['files'].values()):
            raise ValueError('Hash inválido no manifesto')
        if any(not (root / name).is_file() for name in manifest['files']):
            raise ValueError('Modelo incompleto')
        return True, 'OCR local pronto · português e inglês', manifest
    except (OSError, ValueError, TypeError):
        return False, 'OCR indisponível. A conversão preserva texto nativo e imagens. Use Preparar OCR na interface para baixar e verificar os recursos. A preparação requer internet e cerca de 3 GB em disco.', {}


def verify_resources(root, check=None, *, require_environment=True):
    ok, reason, manifest = resource_status(root, require_environment=require_environment)
    if not ok:
        raise RuntimeError(reason)
    expected_files = trusted_model_hashes()
    if manifest['files'] != expected_files:
        raise RuntimeError('Manifesto OCR diverge dos modelos oficiais aprovados. Prepare novamente.')
    deployed = Path(root) / 'models'
    if deployed.exists():
        for path in deployed.rglob('*'):
            if '.cache' in path.relative_to(deployed).parts:
                continue
            if path.is_symlink() or (path.is_file() and path.relative_to(root).as_posix() not in expected_files):
                raise RuntimeError('Pasta de modelos contém arquivos não aprovados. Prepare em uma pasta limpa.')
    for relative, expected in manifest['files'].items():
        path = Path(root) / relative
        if Path(relative).is_absolute() or '..' in Path(relative).parts or not path.resolve().is_relative_to(Path(root).resolve()):
            raise ValueError('Caminho inválido no manifesto OCR.')
        digest = sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                if check: check()
                digest.update(chunk)
        if digest.hexdigest() != expected:
            raise RuntimeError(f'Recurso OCR corrompido: {relative}')
    return manifest


def validate_response(data, request_id, page, width, height):
    if not isinstance(data, dict) or data.get('id') != request_id or data.get('page') != page:
        raise ValueError('Resposta OCR pertence a outra tarefa.')
    if data.get('error'):
        raise RuntimeError(str(data['error'])[:2000])
    blocks = data.get('blocks')
    if not isinstance(blocks, list) or len(blocks) > 20000:
        raise ValueError('Blocos OCR inválidos.')
    for block in blocks:
        if not isinstance(block, dict) or block.get('kind') not in ('text', 'table', 'formula'):
            raise ValueError('Tipo de bloco OCR inválido.')
        bbox = block.get('bbox')
        if not isinstance(bbox, list) or len(bbox) != 4 or any(not isinstance(n, (int, float)) or not math.isfinite(n) for n in bbox):
            raise ValueError('Coordenadas OCR inválidas.')
        x0, y0, x1, y1 = bbox
        if not (0 <= x0 < x1 <= width + 1 and 0 <= y0 < y1 <= height + 1):
            raise ValueError('Bloco OCR fora da página.')
        if not isinstance(block.get('text', ''), str) or len(block.get('text', '')) > 200000:
            raise ValueError('Texto OCR inválido.')
    return blocks


def process_tree_rss(pid):
    """Orçamento inclui eventuais filhos do motor, além do PID principal."""
    pending, visited, total = [pid], set(), 0
    while pending:
        current = pending.pop()
        if current in visited:
            continue
        visited.add(current)
        try:
            status = Path(f'/proc/{current}/status').read_text()
            total += next(int(line.split()[1]) * 1024 for line in status.splitlines()
                          if line.startswith('VmRSS:'))
            for task in Path(f'/proc/{current}/task').iterdir():
                try:
                    pending.extend(int(value) for value in (task / 'children').read_text().split())
                except (FileNotFoundError, ProcessLookupError):
                    pass
        except (FileNotFoundError, ProcessLookupError, StopIteration):
            pass
    return total


class RecognitionClient:
    """One persistent child per conversion; models never enter the Qt process."""
    def __init__(self, root, workspace, *, timeout=180, memory_limit=4 * 1024**3):
        self.root, self.workspace = Path(root), Path(workspace)
        self.timeout, self.memory_limit = timeout, memory_limit
        self.process = None
        self.selector = None
        self.buffer = b''
        self.log = None
        self.peak_bytes = 0
        self.verified = None

    def start(self, check=None):
        if self.process is not None:
            return
        if self.verified is None:
            self.verified = verify_resources(self.root, check)
        directory = self.workspace / 'ocr'
        directory.mkdir(exist_ok=True)
        self.log = (directory / 'runtime.log').open('ab')
        env = {key: os.environ[key] for key in ('LANG', 'LC_ALL', 'LC_CTYPE', 'TZ') if key in os.environ}
        env.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_DATASETS_OFFLINE='1',
                   HF_HUB_DISABLE_TELEMETRY='1', DO_NOT_TRACK='1', OMP_NUM_THREADS='2', MKL_NUM_THREADS='2',
                   TOKENIZERS_PARALLELISM='false', PYTHONUNBUFFERED='1')
        env.update(PYTHONNOUSERSITE='1', PATH='/usr/bin:/bin')
        # The isolated interpreter imports the application contracts, not Qt.
        env['PYTHONPATH'] = str(Path(__file__).resolve().parent.parent)
        self.process = subprocess.Popen([str(self.root / 'environment/bin/python'), '-m',
                                         'pdf_obsidian.recognition_engine', '--root', str(self.root),
                                         '--workspace', str(directory.resolve())],
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.log,
                                        env=env, cwd=directory, close_fds=True, start_new_session=True)
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.process.stdout, selectors.EVENT_READ)
        self.buffer = b''

    def recognize(self, image, page, width, height, check, *, formula_regions=()):
        check()
        request_id = uuid4().hex
        request = dict(id=request_id, page=page, image=str(Path(image).resolve()), width=width, height=height, formula_regions=list(formula_regions))
        start = time.monotonic()
        try:
            self.start(check)
            self.process.stdin.write((json.dumps(request) + '\n').encode())
            self.process.stdin.flush()
            while True:
                check()
                elapsed = time.monotonic() - start
                if elapsed > self.timeout:
                    raise TimeoutError(f'OCR excedeu {self.timeout:g} segundos nesta página.')
                try:
                    rss = process_tree_rss(self.process.pid)
                    self.peak_bytes = max(self.peak_bytes, rss)
                    if rss > self.memory_limit:
                        raise MemoryError('OCR atingiu o orçamento de memória; imagem preservada.')
                except (FileNotFoundError, StopIteration):
                    pass
                if b'\n' in self.buffer:
                    line, self.buffer = self.buffer.split(b'\n', 1)
                    data = json.loads(line)
                    blocks = validate_response(data, request_id, page, width, height)
                    return blocks, elapsed
                if self.selector.select(.05):
                    chunk = os.read(self.process.stdout.fileno(), 65536)
                    if not chunk:
                        raise RuntimeError('O processo OCR encerrou sem resultado. Consulte o log temporário.')
                    self.buffer += chunk
                    if len(self.buffer) > 16 * 1024**2:
                        raise ValueError('Resposta OCR excede o limite de tamanho.')
        except BaseException:
            self.close(graceful=False)
            raise

    def close(self, graceful=True):
        if self.process:
            if graceful and self.process.poll() is None:
                try:
                    self.process.stdin.write(b'{"stop": true}\n')
                    self.process.stdin.flush()
                    self.process.wait(timeout=.8)
                except (OSError, subprocess.TimeoutExpired):
                    pass
            if self.process.poll() is None:
                try:
                    os.killpg(self.process.pid, signal.SIGTERM)
                    self.process.wait(timeout=.5)
                except subprocess.TimeoutExpired:
                    os.killpg(self.process.pid, signal.SIGKILL)
                    self.process.wait(timeout=.5)
                except ProcessLookupError:
                    pass
            self.process.stdin.close()
            self.process.stdout.close()
            self.process = None
        if self.selector:
            self.selector.close()
            self.selector = None
        if self.log:
            self.log.close()
            self.log = None
