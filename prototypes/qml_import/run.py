"""Standalone visual study. Does not import or start the production application."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    outputs = parser.add_mutually_exclusive_group()
    outputs.add_argument('--check', action='store_true', help='Check QML loading and demo keyboard/mouse actions, then exit.')
    outputs.add_argument('--capture', type=Path, help='Save an offscreen PNG and exit.')
    parser.add_argument('--size', default='1120x760', help='Window size, e.g. 1024x700.')
    parser.add_argument('--text-scale', type=float, default=1.0)
    parser.add_argument('--software', action='store_true', help='Use the Qt Quick software backend.')
    args = parser.parse_args()
    try:
        width, height = (int(part) for part in args.size.split('x'))
        if width < 560 or height < 480 or not 0.75 <= args.text_scale <= 2:
            raise ValueError
    except ValueError:
        parser.error('Use a size of at least 560x480 and a text scale between 0.75 and 2.')
    args.width, args.height = width, height
    return args


def main():
    args = arguments()
    if args.capture or args.check:
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'
        os.environ['QT_QPA_PLATFORMTHEME'] = ''
    if args.software or args.capture or args.check:
        os.environ['QT_QUICK_BACKEND'] = 'software'

    from PySide6.QtCore import QObject, QTimer, QUrl, Signal, Slot
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuickControls2 import QQuickStyle

    class DemoController(QObject):
        """Deliberately exposes only a demonstration intent, never file access."""
        feedbackChanged = Signal(str)

        @Slot(str)
        def request_import(self, mode):
            messages = {
                'single': 'Abrir PDF selecionado. Nesta prévia, nenhum arquivo é aberto ou convertido.',
                'batch': 'Conversão em lote selecionada. Nesta prévia, nenhuma fila é iniciada.',
            }
            if mode in messages:
                self.feedbackChanged.emit(messages[mode])

    app = QGuiApplication([sys.argv[0]])
    app.setApplicationName('PDF → Obsidian · Protótipo QML')
    from pdf_obsidian.visuals import load_fonts, install_icons
    from PySide6.QtGui import QFont
    app.setFont(QFont(load_fonts()[0]))
    QQuickStyle.setStyle('Basic')
    engine = QQmlApplicationEngine()
    install_icons(engine)
    warnings = []
    engine.warnings.connect(lambda errors: warnings.extend(error.toString() for error in errors))
    engine.setInitialProperties({'width': args.width, 'height': args.height, 'textScale': args.text_scale})
    engine.load(QUrl.fromLocalFile(str(Path(__file__).with_name('Main.qml'))))
    if not engine.rootObjects():
        return 1
    window = engine.rootObjects()[0]
    controller = DemoController(app)
    window.importRequested.connect(controller.request_import)
    controller.feedbackChanged.connect(lambda message: window.setProperty('feedback', message))

    if args.check:
        from PySide6.QtCore import QPointF, Qt
        from PySide6.QtQuick import QQuickItem
        from PySide6.QtTest import QTest

        def check():
            try:
                first = window.findChild(QQuickItem, 'openPdfAction')
                batch = window.findChild(QQuickItem, 'batchAction')
                assert first is not None and batch is not None
                first.forceActiveFocus(Qt.FocusReason.TabFocusReason)
                QTest.keyClick(window, Qt.Key.Key_Space)
                assert 'Abrir PDF selecionado' in window.property('feedback')
                QTest.keyClick(window, Qt.Key.Key_Tab)
                assert batch.hasActiveFocus()
                QTest.keyClick(window, Qt.Key.Key_Space)
                assert 'Conversão em lote selecionada' in window.property('feedback')
                QTest.keyClick(window, Qt.Key.Key_O, Qt.KeyboardModifier.ControlModifier)
                assert 'Abrir PDF selecionado' in window.property('feedback')
                point = batch.mapToScene(QPointF(batch.width() / 2, batch.height() / 2)).toPoint()
                QTest.mouseClick(window, Qt.MouseButton.LeftButton, pos=point)
                assert 'Conversão em lote selecionada' in window.property('feedback')
                batch.setEnabled(False)
                window.setProperty('feedback', 'disabled check')
                QTest.mouseClick(window, Qt.MouseButton.LeftButton, pos=point)
                assert window.property('feedback') == 'disabled check'
                assert not warnings, '\n'.join(warnings)
            except Exception as exc:
                print(f'Falha na verificação: {exc!r}', file=sys.stderr)
                app.exit(1)
            else:
                print('QML: carregamento, Tab, Espaço, Ctrl+O, clique e disabled verificados; sem avisos QML.')
                app.exit(0)

        QTimer.singleShot(350, check)

    if args.capture:
        attempts = 0

        def capture():
            nonlocal attempts
            screenshot = window.grabWindow()
            if screenshot.isNull() and attempts < 20:
                attempts += 1
                QTimer.singleShot(100, capture)
                return
            if screenshot.isNull() or not screenshot.save(str(args.capture.resolve())):
                print(f'Não foi possível salvar a captura: {args.capture}', file=sys.stderr)
                app.exit(1)
            else:
                print(f'Captura salva: {args.capture.resolve()}')
                app.exit(0)

        QTimer.singleShot(350, capture)
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
