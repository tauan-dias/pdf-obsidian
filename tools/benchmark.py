"""Medição reproduzível do núcleo com 200 páginas sintéticas."""
from pathlib import Path
import resource
import tempfile
import time
import pymupdf
from pdf_obsidian.converter import convert


def gui_benchmark(source, root):
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox
    from pdf_obsidian.gui import Window
    app = QApplication.instance() or QApplication([])
    window = Window()
    QFileDialog.getOpenFileName = lambda *args: (str(source), "PDF")
    QMessageBox.question = lambda *args: QMessageBox.StandardButton.Yes
    failures = []
    QMessageBox.critical = lambda *args: failures.append(args[-1])
    peak = 0
    start = time.perf_counter()
    try:
        window.open_pdf()
        while window.busy:
            app.processEvents()
            rss = 0
            for pid in (os.getpid(), window.worker.pid):
                try:
                    status = Path(f"/proc/{pid}/status").read_text()
                    rss += int(next(line.split()[1] for line in status.splitlines() if line.startswith("VmRSS:")))
                except (FileNotFoundError, StopIteration):
                    pass
            peak = max(peak, rss)
            if failures:
                raise RuntimeError(failures[0])
            if time.perf_counter() - start > 180:
                raise TimeoutError("Benchmark excedeu 180 segundos.")
            time.sleep(.02)
        window.refresh_preview()
        # Observar também o editor e a prévia após carregar todo o documento.
        app.processEvents()
        for _ in range(3):
            rss = sum(int(next(line.split()[1] for line in Path(f"/proc/{pid}/status").read_text().splitlines() if line.startswith("VmRSS:")))
                      for pid in (os.getpid(), window.worker.pid))
            peak = max(peak, rss)
            app.processEvents()
        print(f"Interface + processo PDF: {time.perf_counter() - start:.2f}s; pico RSS combinado observado: {peak / 1024:.1f} MiB")
    finally:
        window.editor.document().setModified(False)
        window.close()


def main():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "benchmark.pdf"
        with pymupdf.open() as doc:
            for index in range(200):
                page = doc.new_page()
                page.insert_text((50, 50), f"Capitulo {index + 1}", fontsize=20)
                for line in range(35):
                    page.insert_text((50, 90 + line * 18), "Texto de estudo para medir a conversao de uma apostila digital.", fontsize=11)
            doc.save(source)
        import sys
        if "--gui" in sys.argv:
            gui_benchmark(source, root)
            return
        start = time.perf_counter()
        result = convert(source, root / "work")
        print(f"Paginas: {len(result.pages)}; tempo: {time.perf_counter() - start:.2f}s; pico RSS do nucleo: {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024:.1f} MiB")


if __name__ == "__main__":
    main()
