"""Capture every UI surface with synthetic presentation fixtures, never personal PDFs.

Run: .venv/bin/python tools/visual_review.py --output /tmp/pdf-obsidian-premium
Fixtures inject progress/error states; real worker integration is tested by pytest
and measured separately by benchmark_quick.py. All generated inputs are temporary.
"""
import argparse
import os
from pathlib import Path
from queue import Queue
from tempfile import TemporaryDirectory, mkdtemp
from types import SimpleNamespace
from unittest.mock import patch

os.environ.update(QT_QPA_PLATFORM='offscreen', QT_QPA_PLATFORMTHEME='',
                  QT_STYLE_OVERRIDE='Fusion', QT_QUICK_BACKEND='software')


class CaptureRuntime:
    def __init__(self, root):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.commands, self.events = Queue(), Queue()
        self.cancel_event = SimpleNamespace(set=lambda: None, clear=lambda: None)
        self.worker = SimpleNamespace(is_alive=lambda: True)
        self.workspaces = []

    def allocate_workspace(self):
        workspace = Path(mkdtemp(dir=self.root))
        self.workspaces.append(workspace)
        return workspace

    def close(self):
        pass


def synthetic_document(root):
    import pymupdf
    from pdf_obsidian.converter import convert
    from pdf_obsidian.models import Warning
    source = root / 'material-sintetico.pdf'
    logo = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 100, 20), False)
    logo.set_rect(logo.irect, (35, 75, 130))
    figure = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 220, 80), False)
    figure.set_rect(figure.irect, (170, 65, 40))
    with pymupdf.open() as pdf:
        for number in range(4):
            page = pdf.new_page()
            page.insert_image(pymupdf.Rect(40, 12, 140, 32), stream=logo.tobytes('png'))
            page.insert_text((40, 95), 'Material de estudo', fontsize=24)
            for line in range(12):
                page.insert_text((40, 140 + line * 22), 'Conteudo sintetico para comparar com o Markdown.', fontsize=12)
            page.insert_image(pymupdf.Rect(40, 450, 260, 530), stream=figure.tobytes('png'))
        pdf.save(source)
        bitmap = root / 'page.png'
        pdf[0].get_pixmap(matrix=pymupdf.Matrix(.8, .8)).save(bitmap)
    result = convert(source, root / 'converted')
    result.title = 'Material de estudo — revisão de documentos'
    result.warnings = [Warning(1, 'Confira a organização deste trecho antes de salvar.'), Warning(0, 'Documento sintético criado apenas para conferência visual.')]
    filtered = {item.asset for item in result.filtered_images}
    asset = next(a.path for a in result.assets if a.path not in filtered)
    result.markdown = ('<!-- Página 1 -->\n\n# Material de estudo\n\n'
                       'Organize suas notas com **clareza**, *ênfase* e [referências](original.pdf).\n\n'
                       '## Revisão do conteúdo\n\n- Compare o texto com o PDF original\n- Confira os anexos antes de publicar\n\n'
                       '> O documento original permanece intacto.\n\n'
                       f'![Figura sintética]({asset})\n\n'
                       '```python\nprint("Processamento local e offline")\n```\n\n' +
                       ('Texto sintético para conferir leitura, alinhamento e espaçamento.\n\n' * 24) +
                       '<!-- Página 2 -->\n\n## Continuação\n\nConteúdo de revisão.')
    return result, bitmap


def main():
    from PySide6.QtCore import QEvent, QMetaObject, QObject, Qt
    from PySide6.QtGui import QFont, QImage
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QMessageBox
    from pdf_obsidian.application import ApplicationController
    from pdf_obsidian.quick import QuickController, create_engine
    from pdf_obsidian.visuals import visual_settings

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    app = QApplication([])
    count = 0
    with TemporaryDirectory(prefix='pdf-obsidian-visual-inputs-') as temp:
        root = Path(temp)
        result, bitmap = synthetic_document(root)
        c = QuickController(application=ApplicationController(runtime=CaptureRuntime(root / 'quick')))
        engine = create_engine(c)
        warnings = engine.load_warnings
        engine.warnings.connect(lambda items: warnings.extend(i.toString() for i in items))
        w = engine.rootObjects()[0]
        base_font = QFont(w.property('font'))
        size_tag = ''

        def take(name):
            nonlocal count
            QTest.qWait(160)
            assert w.grabWindow().save(str(args.output / f'{size_tag}-{name}.png'))
            count += 1

        def dialog(name, shot):
            item = w.findChild(QObject, name)
            assert item is not None, name
            assert QMetaObject.invokeMethod(item, 'open')
            take(shot)
            assert QMetaObject.invokeMethod(item, 'close')
            QTest.qWait(20)

        try:
            for width, height in ((800, 600), (1024, 700), (1300, 850)):
                for scale in (1, 1.25):
                    size_tag = f'{width}x{height}-{scale}'
                    w.setWidth(width); w.setHeight(height)
                    font = QFont(base_font)
                    font.setPointSizeF(base_font.pointSizeF() * scale)
                    w.setProperty('font', font)
                    page = w.findChild(QQuickItem, 'importPage')
                    if c.active:
                        c.snapshot()
                        c.active = None
                        c.changed.emit()
                    page.setProperty('converting', False)
                    take('import')
                    page.setProperty('converting', True)
                    page.setProperty('sourceName', 'material-sintetico-com-nome-extenso-para-conferir-o-layout.pdf')
                    page.setProperty('progressCurrent', 2); page.setProperty('progressTotal', 4)
                    take('conversion')
                    page.setProperty('cancelling', True)
                    take('cancelling')
                    page.setProperty('cancelling', False)
                    page.setProperty('progressTotal', 0)
                    visual_settings().setReducedMotion(True)
                    take('reduced-motion')
                    visual_settings().setReducedMotion(False)
                    page.setProperty('converting', False)
                    c.receive(result)
                    c.render_timer.stop()
                    c.provider.image = QImage(str(bitmap))
                    c._image_url = 'image://pdf/synthetic'
                    c._inflight = None
                    c.changed.emit()
                    for pdf_visible in (True, False):
                        w.setProperty('pdfVisible', pdf_visible)
                        for tab in (0, 1):
                            w.setProperty('tab', tab)
                            take(('preview' if tab else 'editor') + ('-pdf' if pdf_visible else '-full'))
                    w.setProperty('pdfVisible', True)
                    w.setProperty('tab', 0)
                    w.setProperty('warningsExpanded', True)
                    take('warnings')
                    w.setProperty('warningsExpanded', False)
                    for menu in ('openMenu', 'fitMenu', 'styleMenu', 'alignMenu', 'editorMenu'):
                        dialog(menu, menu)
                    w.setProperty('tab', 1)
                    QTest.qWait(80)
                    dialog('previewMenu', 'preview-menu')
                    c.setSelectionMode(True)
                    if c._images:
                        c.toggleImage(next(iter(c._images)))
                    take('image-selection')
                    c.setSelectionMode(False)
                    w.setProperty('tab', 0)
                    c.pending_paths = [str(root / ('Documento com nome extenso ' + str(i) + '.pdf')) for i in range(4)]
                    c.sync_pending()
                    dialog('preparation', 'batch-preparation')
                    statuses = ('Pronto', 'Salvo', 'Falhou', 'Cancelado', 'Não executado')
                    c.documents.sync([dict(key=str(i), name='Documento sintético ' + str(i + 1), status=status,
                                          detail='Falha sintética: não foi possível processar este arquivo.' if status == 'Falhou' else '',
                                          included=i == 0, ready=i < 2, external=False)
                                      for i, status in enumerate(statuses)])
                    dialog('documents', 'documents-states')
                    c.batch.mode = 'convert'
                    c.batch.progress = (2, 4)
                    c.batch.message = 'Convertendo documento sintético 2 de 4…'
                    c.changed.emit()
                    dialog('documents', 'batch-progress')
                    c.batch.mode = None
                    c.batch.message = ''
                    c.changed.emit()
                    c.documents.sync([])
                    dialog('documents', 'documents-empty')
                    c.sync_documents()
                    c.openFiltered()
                    dialog('filteredDialog', 'filtered-images')
                    for index in range(c.filteredCount):
                        c._filtered_cache[(c.active.id, c.active.document.revision(), index)] = ''
                    c.openFiltered()
                    dialog('filteredDialog', 'filtered-ready')
                    c.linkRequested.emit('Texto selecionado para revisão')
                    take('link')
                    QMetaObject.invokeMethod(w.findChild(QObject, 'linkDialog'), 'close')
                    dialog('options', 'options')
                    c.application.set_state(True, 'export')
                    take('saving')
                    c.application.set_state(False, '')
                    for kind, title, message in (
                        ('info', 'Documento salvo', 'Arquivos gravados em:\n/tmp/Vault sintético/Importados/Material de estudo'),
                        ('error', 'Falha no processamento', 'Não foi possível processar o arquivo. Seu trabalho foi preservado.\n\n' + 'Detalhe sintético extenso para conferir rolagem. ' * 60),
                        ('confirm', 'Descartar alterações?', 'Este documento tem alterações não salvas. Deseja descartá-las?')):
                        c.dialogRequested.emit(title, message, kind)
                        take(kind)
                        QMetaObject.invokeMethod(w.findChild(QObject, 'messageDialog'), 'close')
                    c.active.document.setModified(False)
            assert not warnings, warnings
        finally:
            c.shutdown()
            w.setProperty('closingApproved', True); w.close()
            engine.deleteLater(); app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        # The recovery frontend uses the same fonts, icons and tokens.
        from pdf_obsidian import gui
        from pdf_obsidian.batch_dialog import BatchDialog
        from pdf_obsidian.filtered_images import FilteredImagesDialog
        from pdf_obsidian.editor_tools import LinkDialog
        with patch.object(gui, 'ApplicationController', lambda parent: ApplicationController(parent, runtime=CaptureRuntime(root / 'widgets'))):
            window = gui.Window()
            window.resize(1024, 700); window.show(); QTest.qWait(100)
            assert window.grab().save(str(args.output / 'widgets-import.png'))
            window.receive_single_document(result)
            window.pdf_panel.page_view.show_page(bitmap, (0, 0, 595, 842))
            QTest.qWait(100)
            window.render_timer.stop()
            window.active_render = window.pending_render = None
            window.busy, window.operation = False, None
            window.statusBar().showMessage('Documento convertido. Revise o Markdown antes de salvar.')
            window.update_controls()
            app.processEvents()
            assert window.grab().save(str(args.output / 'widgets-editor.png'))
            for name, item in (('batch', BatchDialog(window, preparing=True)),
                               ('filtered', FilteredImagesDialog(window)), ('link', LinkDialog('Texto', window))):
                item.show(); QTest.qWait(80)
                assert item.grab().save(str(args.output / f'widgets-{name}.png'))
                item.reject()
            notice = QMessageBox(QMessageBox.Icon.Critical, 'Falha no processamento',
                                 'Este é um erro sintético. O documento original permanece preservado.',
                                 QMessageBox.StandardButton.Ok, window)
            notice.show(); QTest.qWait(80)
            assert notice.grab().save(str(args.output / 'widgets-error.png'))
            notice.close()
            window.active_session.document.setModified(False)
            window.close()
            app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        visual_settings().setReducedMotion(False)
    print(f'{count} Quick captures and 6 Widgets captures: {args.output}')


if __name__ == '__main__':
    main()
