"""Transição real worker → editor Quick, usando exclusivamente PDF sintético.

Executar: .venv/bin/python tools/benchmark_quick.py --pages 100
Não mede aceite em GPU/desktop. Não abre PDFs ou vaults pessoais.
"""
import argparse
import json
import os
from pathlib import Path
import tempfile
import time

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ['QT_QPA_PLATFORMTHEME'] = ''
os.environ['QT_STYLE_OVERRIDE'] = 'Fusion'
os.environ['QT_QUICK_BACKEND'] = 'software'


def main():
    import pymupdf
    from PySide6.QtCore import QEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from pdf_obsidian.application import ApplicationController
    from pdf_obsidian.quick import QuickController, create_engine

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pages', type=int, default=100)
    args = parser.parse_args()
    if args.pages < 1:
        parser.error('--pages deve ser positivo')
    app = QApplication([])
    with tempfile.TemporaryDirectory(prefix='pdf-obsidian-quick-benchmark-') as directory:
        source = Path(directory) / 'sintetico.pdf'
        pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 80, 20), False)
        pixmap.set_rect(pixmap.irect, (30, 70, 160))
        png = pixmap.tobytes('png')
        with pymupdf.open() as pdf:
            for number in range(args.pages):
                page = pdf.new_page()
                page.insert_image(pymupdf.Rect(30, 15, 150, 45), stream=png)
                page.insert_text((50, 100), f'Capitulo {number + 1}', fontsize=22)
                for line in range(28):
                    page.insert_text((50, 140 + line * 17),
                        f'Linha {line + 1}: material sintetico com conteudo para revisar a conversao.', fontsize=11)
                page.insert_image(pymupdf.Rect(50, 650, 290, 710), stream=png)
            pdf.save(source)
        application = ApplicationController(tagged_operations=True)
        timing = {}
        application.conversionCompleted.connect(lambda result: timing.update(delivered=time.perf_counter()))
        controller = QuickController(application=application)
        engine = create_engine(controller)
        window = engine.rootObjects()[0]
        def frame():
            if controller.hasDocument and 'editor_frame' not in timing:
                timing['editor_frame'] = time.perf_counter()
        window.frameSwapped.connect(frame)
        application.start_polling()
        start = time.perf_counter()
        try:
            application.start_conversion(source)
            while not controller.pdfImage or 'editor_frame' not in timing:
                app.processEvents()
                QTest.qWait(5)
                if time.perf_counter() - start > 180:
                    raise TimeoutError('Benchmark excedeu 180 segundos.')
            assert controller.editor.property('text') == controller.active.result.markdown
            assert controller._preview_doc is None and controller.filtered.rowCount() == 0
            assert not engine.load_warnings
            print(json.dumps({
                'pages': args.pages,
                'characters': len(controller.active.result.markdown),
                'filtered_images': controller.filteredCount,
                'conversion_and_transport_seconds': round(timing['delivered'] - start, 3),
                'delivery_to_editor_frame_seconds': round(timing['editor_frame'] - timing['delivered'], 3),
                'total_until_pdf_seconds': round(time.perf_counter() - start, 3),
                'renderer': os.environ.get('QT_QUICK_BACKEND', 'default'),
            }, indent=2))
        finally:
            controller.shutdown()
            window.setProperty('closingApproved', True)
            window.close()
            engine.deleteLater()
            app.sendPostedEvents(None, QEvent.Type.DeferredDelete)


if __name__ == '__main__':
    main()
