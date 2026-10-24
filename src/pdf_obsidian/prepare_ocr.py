"""Explicit setup command; the application itself never installs or downloads OCR."""
import argparse
from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
import venv

from .recognition import resource_directory, verify_resources


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=resource_directory())
    parser.add_argument('--verify', action='store_true', help='Verify local assets without network access.')
    parser.add_argument('--offline', action='store_true', help='Prepare from a local wheelhouse and model bundle.')
    parser.add_argument('--wheelhouse', type=Path)
    parser.add_argument('--model-source', type=Path, help='Prepared OCR directory containing models and manifest.')
    args = parser.parse_args()
    root = args.directory.resolve()
    if args.verify:
        manifest = verify_resources(root)
        print(f'OCR local verificado: {len(manifest["files"])} arquivos, português e inglês.')
        return 0
    if args.offline and not (args.wheelhouse and args.model_source):
        parser.error('--offline exige --wheelhouse e --model-source; nenhum download será tentado.')
    root.mkdir(parents=True, exist_ok=True)
    environment = root / 'environment'
    python = environment / 'bin/python'
    if not python.is_file():
        venv.EnvBuilder(with_pip=True).create(environment)
    requirements = Path(__file__).with_name('ocr_requirements.txt')
    command = [str(python), '-m', 'pip', 'install', '-r', str(requirements),
               '--cache-dir', str(root / 'pip-cache')]
    if args.offline:
        command.extend(['--no-index', '--find-links', str(args.wheelhouse.resolve())])
    else:
        command.extend(['--index-url', 'https://pypi.org/simple', '--extra-index-url', 'https://download.pytorch.org/whl/cpu'])
    subprocess.run(command, check=True)
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parent.parent))
    if args.model_source:
        source = args.model_source.resolve()
        verify_resources(source, require_environment=False)
        if source != root:
            shutil.copytree(source / 'models', root / 'models', dirs_exist_ok=True)
            shutil.copy2(source / 'manifest.json', root / 'manifest.json')
    else:
        subprocess.run([str(python), '-m', 'pdf_obsidian.recognition_models', '--root', str(root)],
                       env=env, check=True)
    verify_resources(root)
    subprocess.run([str(python), '-m', 'pip', 'check'], check=True)
    print('OCR pronto para uso offline. Reinicie a aplicação se ela já estiver aberta.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
