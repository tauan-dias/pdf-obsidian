"""Run only during explicit OCR preparation, inside its isolated interpreter."""
import argparse
from hashlib import sha256
from importlib.metadata import version
import json
import os
import shutil
from pathlib import Path


def prepare(root):
    from huggingface_hub import HfApi, snapshot_download
    from docling.models.stages.ocr.rapid_ocr_model import RapidOcrModel
    root = Path(root).resolve()
    models = root / 'models'
    models.mkdir(parents=True, exist_ok=True)
    sources_path = Path(__file__).with_name('ocr_models.json')
    sources = json.loads(sources_path.read_text())
    records = []
    api = HfApi()
    for source in sources:
        revision = source['revision']
        info = api.model_info(source['repo'], revision=revision)
        resolved = info.sha
        print(f'Preparing {source["repo"]}@{resolved}', flush=True)
        snapshot_download(source['repo'], revision=resolved,
                          local_dir=models / source['repo'].replace('/', '--'),
                          cache_dir=root / 'cache', max_workers=2)
        records.append(dict(repo=source['repo'], revision=resolved))
    RapidOcrModel.download_models('onnxruntime', local_dir=models / RapidOcrModel._model_repo_folder,
                                  lang='latin', model_size='small', progress=True)
    licenses = models / 'LICENSES'
    licenses.mkdir(exist_ok=True)
    for path in Path(__file__).with_name('ocr_licenses').glob('*'):
        if path.is_file():
            shutil.copy2(path, licenses / path.name)
    from .recognition import verify_trusted_models
    approved = verify_trusted_models(root)
    # Every deployed model/config/dictionary/license participates in integrity checks.
    files = {}
    for path in sorted(models.rglob('*')):
        if not path.is_file() or '.cache' in path.parts:
            continue
        digest = sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(chunk)
        files[path.relative_to(root).as_posix()] = digest.hexdigest()
    if files != approved:
        raise RuntimeError('Conjunto de modelos contém arquivos ausentes ou não aprovados.')
    versions = {name: version(name) for name in ('docling', 'docling-core', 'docling-ibm-models', 'rapidocr', 'onnxruntime', 'torch', 'transformers')}
    manifest = dict(schema=1, versions=versions, sources=records, languages=['pt', 'en'],
                    licenses=['Apache-2.0', 'CDLA-Permissive-2.0'], files=files)
    temporary = root / 'manifest.json.tmp'
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(root / 'manifest.json')
    print(f'OCR prepared: {len(files)} files, {sum((root/name).stat().st_size for name in files)/1024**2:.1f} MiB', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    os.environ.update(HF_HOME=str(args.root / 'cache'), HF_HUB_DISABLE_TELEMETRY='1',
                      HF_HUB_DISABLE_XET='1', DO_NOT_TRACK='1', OMP_NUM_THREADS='2', MKL_NUM_THREADS='2')
    prepare(args.root)


if __name__ == '__main__':
    main()
