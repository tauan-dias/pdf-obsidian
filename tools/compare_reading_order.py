"""Comparação sintética opcional; nunca recebe PDFs pessoais."""
import argparse
import importlib.metadata
import json
from pathlib import Path
import tempfile
import time

import pymupdf
from pdf_obsidian.converter import convert


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--markitdown-commit", default="não informado")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="pdf-reading-") as folder:
        root = Path(folder)
        from reading_fixtures import generate
        cases = generate(root)
        results = []
        def measure(name, operation):
            started = time.perf_counter()
            text = operation()
            positions = [text.find(token) for token in expected]
            results.append(dict(case=case, engine=name, seconds=time.perf_counter() - started,
                                missing=sum(p < 0 for p in positions),
                                duplicates=sum(max(0, text.count(token) - 1) for token in expected),
                                inversions=sum(a > b for i, a in enumerate(positions)
                                               for b in positions[i + 1:] if a >= 0 and b >= 0)))
        import pdf_obsidian.reading_order as reading_order
        regional = reading_order.regions
        try:
            import onnxruntime
            onnxruntime.disable_telemetry_events()
            from markitdown import MarkItDown
        except ImportError:
            MarkItDown = None
        for case, source, expected in cases:
            try:
                reading_order.regions = lambda items, width: [sorted(
                    items, key=lambda b: (round(b.bbox[1] / 3), b.bbox[0]))]
                measure("ordenação anterior", lambda: convert(source, root / (case + "-baseline")).markdown)
            finally:
                reading_order.regions = regional
            measure("pdf-obsidian", lambda: convert(source, root / (case + "-work")).markdown)
            if MarkItDown is None:
                results.append(dict(case=case, engine="markitdown", status="não instalado"))
            else:
                try:
                    measure("markitdown", lambda: MarkItDown(enable_plugins=False).convert_local(str(source)).markdown)
                    results[-1].update(version=importlib.metadata.version("markitdown"),
                                       commit=args.markitdown_commit)
                except Exception as exc:
                    results.append(dict(case=case, engine="markitdown", error=str(exc)))
        print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
