"""Adaptador visual da importação: QML por padrão, Widgets como recuperação."""
from pathlib import Path

from PySide6.QtCore import QEvent, QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (QApplication, QLabel, QPushButton, QProgressBar,
                              QStackedLayout, QVBoxLayout, QWidget)

from .appearance import COLORS, ElidedLabel, tool_icon


class LegacyImportPage(QWidget):
    """Tela Widgets funcional, construída somente quando o QML falha."""
    def __init__(self, panel):
        super().__init__(panel)
        layout = QVBoxLayout(self)
        layout.addStretch()
        self.title = QLabel('Seu PDF, pronto para editar')
        self.title.setObjectName('brand')
        self.title.setWordWrap(True)
        self.title.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title)
        description = QLabel('Abra um PDF, revise o Markdown e salve no seu vault.\nProcessamento local e offline · PDF original preservado')
        description.setWordWrap(True)
        description.setObjectName('muted')
        description.setAlignment(Qt.AlignCenter)
        layout.addWidget(description)
        self.open_button = QPushButton('Abrir PDF')
        self.open_button.setObjectName('primary')
        self.open_button.setIcon(tool_icon('open', COLORS['on_accent']))
        self.batch_button = QPushButton('Converter em lote…')
        self.documents_button = QPushButton()
        self.source = ElidedLabel()
        self.progress = QProgressBar()
        self.cancel = QPushButton('Cancelar conversão')
        for widget in (self.open_button, self.batch_button, self.documents_button, self.source, self.progress, self.cancel):
            layout.addWidget(widget)
        self.open_button.clicked.connect(panel.openPdfRequested)
        self.batch_button.clicked.connect(panel.batchRequested)
        self.documents_button.clicked.connect(panel.documentsRequested)
        self.cancel.clicked.connect(panel.cancelRequested)
        layout.addStretch()

    def update_state(self, state):
        converting, cancelling = state['converting'], state['cancelling']
        self.title.setText('Cancelando…' if cancelling else 'Convertendo seu PDF' if converting else 'Seu PDF, pronto para editar')
        for button in (self.open_button, self.batch_button):
            button.setVisible(not converting)
            button.setEnabled(state['canImport'])
        for widget in (self.source, self.progress, self.cancel):
            widget.setVisible(converting)
        self.source.setText(state['sourceName'])
        self.source.setToolTip(state['sourceName'])
        self.progress.setRange(0, state['progressTotal'])
        self.progress.setValue(state['progressCurrent'])
        self.cancel.setEnabled(converting and not cancelling)
        self.cancel.setText('Cancelando…' if cancelling else 'Cancelar conversão')
        self.documents_button.setVisible(state['documentCount'] > 0)
        self.documents_button.setText(f"Documentos ({state['documentCount']})")
        self.documents_button.setEnabled(state['documentsEnabled'])


class ImportPanel(QWidget):
    """Somente valores de apresentação atravessam a fronteira Python/QML.

    O painel não possui worker nem abre arquivos. Intenções voltam à janela,
    que mantém os fluxos existentes de seleção, confirmação e sessões.
    """
    openPdfRequested = Signal()
    batchRequested = Signal()
    documentsRequested = Signal()
    cancelRequested = Signal()
    loadFailed = Signal(str)

    def __init__(self, parent=None, *, qml_source=None):
        super().__init__(parent)
        self.quick = None
        self.fallback = None
        self.load_error = ''
        self._ready = False
        self._state = dict(converting=False, cancelling=False, canImport=True,
                           documentsEnabled=True, documentCount=0, sourceName='',
                           progressCurrent=0, progressTotal=0, feedback='',
                           fontFamily=QApplication.font().family(), textScale=self._text_scale())
        self.stack = QStackedLayout(self)
        self.stack.setContentsMargins(0, 0, 0, 0)
        self.setFocusPolicy(Qt.StrongFocus)
        QApplication.instance().fontChanged.connect(self._font_changed)
        try:
            from PySide6.QtQuickWidgets import QQuickWidget
            self.quick = QQuickWidget(self)
            self.quick.setFocusPolicy(Qt.StrongFocus)
            self.quick.setResizeMode(QQuickWidget.SizeRootObjectToView)
            self.quick.setClearColor(COLORS['background'])
            self.stack.addWidget(self.quick)
            self.quick.statusChanged.connect(self._status_changed)
            self.quick.sceneGraphError.connect(self._scene_error)
            self.quick.setInitialProperties(self._state)
            source = Path(qml_source) if qml_source is not None else Path(__file__).with_name('qml') / 'ImportPage.qml'
            self.quick.setSource(QUrl.fromLocalFile(str(source.resolve())))
        except Exception as exc:
            self._use_fallback(str(exc))

    @property
    def state(self):
        return self._state.copy()

    @property
    def using_qml(self):
        return self._ready and self.fallback is None

    def sizeHint(self):
        return QSize(1120, 760)

    def minimumSizeHint(self):
        return QSize(560, 400)

    def _status_changed(self, status):
        from PySide6.QtQuickWidgets import QQuickWidget
        if status == QQuickWidget.Error:
            self._use_fallback('\n'.join(error.toString() for error in self.quick.errors()))
        elif status == QQuickWidget.Ready and not self.load_error:
            root = self.quick.rootObject()
            if root is None:
                self._use_fallback('A página QML não foi criada.')
                return
            for name in ('openPdfRequested', 'batchRequested', 'documentsRequested', 'cancelRequested'):
                getattr(root, name).connect(getattr(self, name))
            self._ready = True
            self._apply_state()

    def _scene_error(self, _error, message):
        self._use_fallback(message)

    def _use_fallback(self, message):
        if self.fallback is not None:
            return
        self.load_error = message or 'Falha ao carregar a página QML.'
        self._ready = False
        self.fallback = LegacyImportPage(self)
        self.stack.addWidget(self.fallback)
        self.stack.setCurrentWidget(self.fallback)
        self.fallback.update_state(self._state)
        if self.quick is not None:
            # Keep Qt ownership; stop displaying the failed scene without
            # destroying the shared application state or deleting bindings by hand.
            self.quick.hide()
            QTimer.singleShot(0, self._unload_quick)
        self.loadFailed.emit(self.load_error)

    def _unload_quick(self):
        # Release the failed scene through Qt after its error callback returns.
        # This also stops animations that would otherwise survive off screen.
        if self.quick is not None and self.fallback is not None:
            self.quick.setSource(QUrl())

    def update_state(self, **changes):
        for name, value in changes.items():
            if name not in self._state:
                raise KeyError(name)
            self._state[name] = value
        self._apply_state()

    def _apply_state(self):
        if self.fallback is not None:
            self.fallback.update_state(self._state)
        elif self._ready:
            root = self.quick.rootObject()
            for name, value in self._state.items():
                if root.property(name) != value:
                    root.setProperty(name, value)

    def focus_primary(self):
        if not self.isVisible() or QApplication.activeModalWidget() is not None:
            return
        if self.fallback is not None:
            target = self.fallback.cancel if self._state['converting'] else self.fallback.open_button
            target.setFocus(Qt.TabFocusReason)
        elif self._ready:
            self.quick.setFocus(Qt.TabFocusReason)
            self.quick.rootObject().focusPrimaryAction()

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self.focus_primary)

    def _text_scale(self):
        baseline = QFontDatabase.systemFont(QFontDatabase.GeneralFont).pointSizeF()
        current = QApplication.font().pointSizeF()
        return current / baseline if baseline > 0 and current > 0 else 1.0

    def _font_changed(self, _font=None):
        # QSS may pin a QWidget's inherited font. Follow the application font
        # explicitly so an accessibility font change also reaches the QML text.
        self.update_state(fontFamily=QApplication.font().family(), textScale=self._text_scale())

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.FontChange, QEvent.ApplicationFontChange) and hasattr(self, '_state'):
            self.update_state(fontFamily=QApplication.font().family(), textScale=self._text_scale())
