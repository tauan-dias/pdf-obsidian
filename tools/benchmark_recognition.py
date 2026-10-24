"""Real offline worker/UI benchmark on generated mixed/scanned/native pages only."""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
import time

os.environ.update(QT_QPA_PLATFORM='offscreen', QT_QPA_PLATFORMTHEME='', QT_STYLE_OVERRIDE='Fusion', QT_QUICK_BACKEND='software')


def generate(root, pages):
    import pymupdf
    font = Path(__file__).resolve().parents[1] / 'src/pdf_obsidian/assets/fonts/Geist-Regular.ttf'
    def page_text(page, detailed):
        page.insert_font(fontname='Geist',fontfile=str(font))
        page.insert_text((40,65),'Reconhecimento de documentos',fontname='Geist',fontsize=22)
        page.insert_text((40,110),'Português: ação, ciência e informação.',fontname='Geist',fontsize=16)
        page.insert_text((40,145),'English: clear text and accurate results.',fontname='Geist',fontsize=16)
        if detailed:
            for y in (210,250,290,330):page.draw_line((40,y),(440,y))
            for x in (40,240,440):page.draw_line((x,210),(x,330))
            for x,y,text in ((55,237,'Item'),(255,237,'Valor'),(55,277,'Alfa'),(255,277,'10'),(55,317,'Beta'),(255,317,'20')):
                page.insert_text((x,y),text,fontname='Geist',fontsize=14)
            page.insert_text((40,400),'x² + 2x + 1 = (x + 1)²',fontname='Geist',fontsize=22)
    bitmaps=[]
    for detailed in (True,False):
        with pymupdf.open() as pdf:
            page=pdf.new_page();page_text(page,detailed)
            bitmaps.append(page.get_pixmap(dpi=200,alpha=False).tobytes('png'))
    source=root/'synthetic-ocr.pdf'
    with pymupdf.open() as pdf:
        for n in range(pages):
            page=pdf.new_page()
            if n==pages-1 and pages>1:
                page_text(page,False) # fast path must not invoke OCR
            else:
                page.insert_image(page.rect,stream=bitmaps[0 if n==0 else 1])
                if n%2:
                    page.insert_font(fontname='Geist',fontfile=str(font))
                    page.insert_text((40,110),'Português: ação, ciência e informação.',fontname='Geist',fontsize=16)
        pdf.save(source)
    return source


def rss(pid):
    try:
        return next(int(line.split()[1])*1024 for line in Path(f'/proc/{pid}/status').read_text().splitlines() if line.startswith('VmRSS:'))
    except (OSError,StopIteration):return 0


def main():
    from PySide6.QtWidgets import QApplication
    from PySide6.QtTest import QTest
    from PySide6.QtCore import QEvent
    from pdf_obsidian.quick import QuickController,create_engine
    from pdf_obsidian.recognition import resource_status
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pages',type=int,default=20)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--capture',type=Path)
    args=parser.parse_args()
    if args.pages<1:parser.error('--pages must be positive')
    if not resource_status()[0]:parser.error(resource_status()[1])
    app=QApplication([])
    with tempfile.TemporaryDirectory(prefix='pdf-obsidian-ocr-benchmark-') as directory:
        source=generate(Path(directory),args.pages)
        original=sha256(source.read_bytes()).hexdigest()
        c=QuickController();engine=create_engine(c);window=engine.rootObjects()[0]
        c.application.start_polling();stages=[];max_base=0;start=time.monotonic()
        errors=[]
        c.application.operationFailed.connect(errors.append)
        try:
            assert c.application.start_conversion(source)
            while not c.hasDocument:
                app.processEvents();QTest.qWait(25)
                max_base=max(max_base,rss(os.getpid())+rss(c.application.runtime.worker.pid))
                stage=c.application.conversionStage
                if stage and (not stages or stages[-1]!=stage):
                    stages.append(stage);print(stage,flush=True)
                if errors:raise RuntimeError(errors[-1])
                if time.monotonic()-start>args.pages*185+60:raise TimeoutError('Benchmark deadline exceeded')
            elapsed=time.monotonic()-start
            result=c.active.result
            assert sha256(source.read_bytes()).hexdigest()==original
            assert 'Português: ação, ciência e informação.' in result.markdown
            assert 'English: clear text and accurate results.' in result.markdown
            assert '| Alfa | 10 |' in result.markdown
            assert '$$' in result.markdown and 'x' in result.markdown
            assert result.markdown.count('Português: ação, ciência e informação.')==args.pages
            recognized=result.recognition
            assert len(recognized['pages'])==(args.pages-1 if args.pages>1 else 1)
            assert all(page['status']=='recognized' for page in recognized['pages']),recognized
            total=max_base+recognized['peak_bytes']
            assert total<6*1024**3,(total,recognized)
            output=dict(pages=args.pages,seconds=round(elapsed,3),base_peak_bytes=max_base,
                        conservative_total_peak_bytes=total,recognition=recognized,
                        source_hash_preserved=True,text_table_formula_checks=True,network='blocked in OCR child')
            if args.output:
                args.output.parent.mkdir(parents=True,exist_ok=True)
                args.output.write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
            print(json.dumps(output,ensure_ascii=False,indent=2))
            if args.capture:
                deadline=time.monotonic()+10
                while not c.pdfImage:
                    app.processEvents();QTest.qWait(10)
                    assert time.monotonic()<deadline
                QTest.qWait(160)
                assert window.grabWindow().save(str(args.capture))
            assert not engine.load_warnings,engine.load_warnings
        finally:
            c.shutdown();window.setProperty('closingApproved',True);window.close()
            engine.deleteLater();app.sendPostedEvents(None,QEvent.Type.DeferredDelete)


if __name__=='__main__':main()
