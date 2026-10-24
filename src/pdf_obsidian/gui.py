import multiprocessing as mp
from pathlib import Path
import sys

from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QKeySequence, QShortcut, QTextCursor
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QPushButton, QFileDialog, QMessageBox, QSplitter, QPlainTextEdit,
    QListWidget, QLabel, QTabWidget, QToolButton, QMenu, QWidgetAction, QStackedWidget)

from .visuals import visual_settings
from .progress_ui import OperationProgress as QProgressBar
from .appearance import CheckBox as QCheckBox, apply_theme, tool_icon, COLORS, ElidedLabel, AdaptiveRow
from .comparison import (preview_document, reading_position, restore_reading_position,
                         scroll_editor_to, unique_markers)
from .cleanup import apply_cleanup, build_manual_cleanup_plan
from .session_ui import SessionWindowMixin
from .application import ApplicationController
from .import_panel import ImportPanel
from .batch import BatchHooks
from .batch_dialog import BatchDialog
from .editor_tools import EditorTools
from .filtered_images import FilteredImagesDialog, restoration_edit
from .markdown import utf16_position
from .models import AssetInfo
from .preview import ImagePreview
from .viewer import PDFPanel


class Window(SessionWindowMixin, QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF-Obsidian")
        self.resize(1300, 850)
        self.application = ApplicationController(self)
        # Compatibility aliases for the Widgets PDF/session adapters. The
        # application controller owns these resources and their lifecycle.
        runtime = self.application.runtime
        self.root, self.workspaces = runtime.root, runtime.workspaces
        self.commands, self.events = runtime.commands, runtime.events
        self.cancel_event, self.worker = runtime.cancel_event, runtime.worker
        self.result = None
        self.sessions = {}
        self.active_session = None
        self.switching_session = False
        self.restoring_pdf = None
        self.batch_dialog = None
        self.busy = False
        self.operation = None
        self.displayed_page = None
        self.requested_page = None
        self.zoom_mode = "width"
        self.zoom_percent = 100.0
        self.render_sequence = 0
        self.desired_render = None
        self.active_render = None
        self.pending_render = None
        self.view_revision = 0
        self.preview_dirty = False
        self.crop_cursor = None
        self.crop_bbox = None
        self.strip_page_markers = False
        self.cleanup_removals = []
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(16, 12, 16, 8)
        layout.setSpacing(12)
        header = self.header = QWidget()
        header.setObjectName("header")
        bar = QHBoxLayout(header)
        bar.setContentsMargins(0, 0, 0, 0)
        self.document_label = ElidedLabel("PDF-Obsidian")
        self.document_label.setObjectName("section")
        self.document_label.setMinimumWidth(0)
        bar.addWidget(self.document_label, 1)
        self.modified_label = QLabel("Alterações não salvas")
        self.modified_label.setObjectName("muted")
        bar.addWidget(self.modified_label)
        self.modified_label.setToolTip("As edições são mantidas durante esta sessão. Salve no vault para exportá-las.")
        self.batch_button = QPushButton("Converter em lote…")
        self.documents_button = QPushButton("Documentos (0)")
        self.batch_button.clicked.connect(self.open_batch)
        self.documents_button.clicked.connect(self.show_documents)
        self.open_button = QPushButton("Abrir")
        self.export_button = QPushButton("Salvar no vault…")
        self.strip_markers_option = QCheckBox("Remover marcações de página na exportação")
        self.export_button.setObjectName("primary")
        self.open_button.setIcon(tool_icon("open"))
        self.open_button.setToolTip("Abrir PDF (Ctrl+O) ou converter em lote")
        self.export_button.setToolTip("Salvar documento ativo no vault (Ctrl+S)")
        self.export_button.setIcon(tool_icon("export", COLORS["on_accent"]))
        self.export_options = QToolButton()
        self.export_options.setIcon(tool_icon("more"))
        self.export_options.setAccessibleName("Opções de exportação")
        self.export_options.setToolTip("Opções de exportação")
        menu = QMenu(self.export_options)
        option = QWidgetAction(menu)
        option.setDefaultWidget(self.strip_markers_option)
        menu.addAction(option)
        self.reduced_motion_option = QCheckBox("Reduzir movimento")
        self.reduced_motion_option.setChecked(visual_settings().reducedMotion)
        motion_action = QWidgetAction(menu)
        motion_action.setDefaultWidget(self.reduced_motion_option)
        menu.addSeparator()
        menu.addAction(motion_action)
        self.reduced_motion_option.toggled.connect(visual_settings().setReducedMotion)
        visual_settings().reducedMotionChanged.connect(self._sync_motion)
        self.next_ocr_option = QCheckBox("OCR automático nas próximas conversões")
        self.next_ocr_option.setChecked(self.application.ocrMode == 'auto')
        self.next_ocr_option.setToolTip(self.application.recognitionStatus + ' Não altera o documento atual.')
        ocr_action = QWidgetAction(menu)
        ocr_action.setDefaultWidget(self.next_ocr_option)
        menu.addSeparator()
        menu.addAction(ocr_action)
        self.next_ocr_option.toggled.connect(lambda enabled: self.application.setOcrMode('auto' if enabled else 'off'))
        self.application.conversionOptionsChanged.connect(self._sync_ocr_mode)
        self.export_options.setMenu(menu)
        self.export_options.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        open_menu = QMenu(self.open_button)
        open_menu.addAction(tool_icon("open"), "Abrir PDF…", self.open_pdf)
        self.batch_action = open_menu.addAction("Converter em lote…", self.open_batch)
        self.open_button.setMenu(open_menu)
        self.open_button.setAccessibleName("Abrir documento ou converter em lote")
        for widget in (self.documents_button, self.open_button, self.export_button, self.export_options):
            bar.addWidget(widget)
        self.batch_button.hide()
        layout.addWidget(header)
        self.content = QStackedWidget()
        self.welcome = ImportPanel(self)
        self.welcome.openPdfRequested.connect(self.open_pdf)
        self.welcome.batchRequested.connect(self.open_batch)
        self.welcome.documentsRequested.connect(self.show_documents)
        self.welcome.cancelRequested.connect(self.application.cancelConversion)
        self.welcome.loadFailed.connect(self.import_load_failed)
        self._import_return_focus = None
        self.content.addWidget(self.welcome)
        self.workspace = QWidget()
        workspace_layout = QVBoxLayout(self.workspace)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        control_row = AdaptiveRow()
        controls = control_row.row
        self.pdf_toggle = QPushButton("Ocultar PDF")
        self.pdf_toggle.clicked.connect(self.toggle_pdf)
        controls.addWidget(self.pdf_toggle)
        self.follow_page = QCheckBox("Acompanhar página")
        self.follow_page.setChecked(True)
        self.follow_page.setToolTip("Ao navegar no PDF, mostrar o trecho correspondente no Markdown e na prévia, sem mover o cursor de edição.")
        controls.addWidget(self.follow_page)
        self.filtered_button = QPushButton("Imagens filtradas (0)")
        self.filtered_button.clicked.connect(self.review_filtered_images)
        controls.addWidget(self.filtered_button)
        controls.addStretch()
        workspace_layout.addWidget(control_row)
        splitter = self.splitter = QSplitter()
        self.pdf_sizes = [480, 720]
        splitter.setHandleWidth(10)
        self.pdf_panel = PDFPanel()
        self.page_view = self.pdf_panel.page_view
        self.page_number = self.pdf_panel.page_number
        self.pdf_scroll = self.pdf_panel.scroll
        splitter.addWidget(self.pdf_panel)
        comparison = QWidget()
        comparison.setObjectName("panel")
        comparison.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        comparison_layout = QVBoxLayout(comparison)
        comparison_layout.setContentsMargins(12, 12, 12, 12)
        self.tabs = QTabWidget()
        self.editor = QPlainTextEdit()
        self.editor.setObjectName("markdownEditor")
        self.editor.setPlaceholderText("Abra um PDF para converter e revisar o Markdown aqui.")
        self.editor_tools = EditorTools(self.editor, lambda message: self.statusBar().showMessage(message))
        self.editor_panel = QWidget()
        editor_layout = QVBoxLayout(self.editor_panel)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.addWidget(self.editor_tools)
        editor_layout.addWidget(self.editor)
        self.preview = ImagePreview()
        self.tabs.addTab(self.editor_panel, "Markdown")
        self.tabs.addTab(self.preview, "Prévia")
        comparison_layout.addWidget(self.tabs)
        splitter.addWidget(comparison)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes(self.pdf_sizes)
        splitter.setChildrenCollapsible(False)
        workspace_layout.addWidget(splitter, 1)
        self.content.addWidget(self.workspace)
        layout.addWidget(self.content, 1)
        self.warning_list = QListWidget()
        self.warning_list.setMaximumHeight(110)
        self.warnings_toggle = QToolButton()
        self.warnings_toggle.setText("Avisos (0)")
        self.warnings_toggle.setObjectName("warningsToggle")
        self.warnings_toggle.setCheckable(True)
        self.warnings_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.warnings_toggle.setArrowType(Qt.ArrowType.RightArrow)
        self.warnings_toggle.toggled.connect(self.toggle_warnings)
        workspace_layout.addWidget(self.warnings_toggle)
        workspace_layout.addWidget(self.warning_list)
        self.warning_list.hide()
        self.editor.document().modificationChanged.connect(self.update_modified)

        self.export_button.clicked.connect(self.export)
        self.strip_markers_option.toggled.connect(self.set_strip_page_markers)
        self.preview.selection_changed.connect(self.update_controls)
        self.preview.selection_issue.connect(lambda message: self.statusBar().showMessage(message))
        self.preview.remove_requested.connect(self.remove_preview_images)
        self.preview.undo_requested.connect(self.editor.undo)
        self.preview.redo_requested.connect(self.editor.redo)
        self.editor.undoAvailable.connect(self.update_controls)
        self.editor.redoAvailable.connect(self.update_controls)
        self.page_number.valueChanged.connect(self.request_page)
        self.pdf_panel.previous.clicked.connect(lambda: self.step_page(-1))
        self.pdf_panel.next.clicked.connect(lambda: self.step_page(1))
        self.pdf_panel.zoom.valueChanged.connect(self.set_manual_zoom)
        self.pdf_panel.zoom_out.clicked.connect(lambda: self.step_zoom(-25))
        self.pdf_panel.zoom_in.clicked.connect(lambda: self.step_zoom(25))
        self.pdf_panel.fit_width.clicked.connect(lambda: self.set_zoom_mode("width"))
        self.pdf_panel.fit_page.clicked.connect(lambda: self.set_zoom_mode("page"))
        self.pdf_scroll.viewport_resized.connect(self.viewport_resized)
        self.follow_page.toggled.connect(lambda checked: self.follow_current_page() if checked else None)
        self.tabs.currentChanged.connect(self.tab_changed)
        self.page_view.selected.connect(self.crop)
        self.warning_list.itemClicked.connect(self.warning_clicked)
        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.setInterval(300)
        self.preview_timer.timeout.connect(self.refresh_preview)
        self.editor.textChanged.connect(self.mark_preview_dirty)
        self.render_timer = QTimer(self)
        self.render_timer.setSingleShot(True)
        self.render_timer.setInterval(180)
        self.render_timer.timeout.connect(self.dispatch_render)
        self.install_shortcuts()
        self.poll_timer = self.application.poll_timer
        self.batch = self.application.attach_batch(BatchHooks(
            prepare_start=self.discard_batch,
            snapshot_active=self.save_active_session,
            create_session=self.create_session))
        self.batch.changed.connect(self.update_controls)
        self.application.progressChanged.connect(self.update_import_state)
        self.application.sourceChanged.connect(self.update_import_state)
        self.application.cancellationChanged.connect(self.update_import_state)
        self.application.conversionOptionsChanged.connect(self.update_import_state)
        self.application.conversionStageChanged.connect(self.update_import_state)
        self.welcome.ocrModeRequested.connect(lambda enabled: self.application.setOcrMode('auto' if enabled else 'off'))
        self.application.conversionCompleted.connect(self.receive_single_document)
        self.application.cropCompleted.connect(self.receive_crop)
        self.application.conversionCancelled.connect(self.conversion_cancelled)
        self.application.operationFailed.connect(self.operation_failed)
        self.application.renderCompleted.connect(self.finish_render)
        self.application.workerFailed.connect(self.worker_failed)
        self.application.start_polling()
        apply_theme(self)
        QApplication.instance().fontChanged.connect(self._refresh_theme)
        self.update_controls()
        if self.welcome.load_error:
            self.import_load_failed(self.welcome.load_error)

    def _sync_ocr_mode(self):
        self.next_ocr_option.setChecked(self.application.ocrMode == 'auto')

    def _refresh_theme(self, _font=None):
        apply_theme(self)

    def _sync_motion(self):
        self.reduced_motion_option.setChecked(visual_settings().reducedMotion)

    def update_modified(self, *_):
        self.modified_label.setVisible(self.result is not None and (self.active_session.modified if self.active_session else self.editor.document().isModified()))

    def toggle_pdf(self):
        self.set_pdf_visible(self.pdf_panel.isHidden())

    def set_pdf_visible(self, visible):
        if visible == (not self.pdf_panel.isHidden()):
            return
        if not visible:
            self.pdf_sizes = self.splitter.sizes()
        self.pdf_panel.setVisible(visible)
        self.pdf_toggle.setText("Ocultar PDF" if visible else "Mostrar PDF")
        if visible:
            self.splitter.setSizes(self.pdf_sizes)

    def toggle_warnings(self, expanded):
        self.warning_list.setVisible(expanded)
        self.warnings_toggle.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)

    def update_controls(self):
        self.next_ocr_option.setEnabled(not self.busy)
        if self.switching_session:
            return
        batch_running = hasattr(self, "batch") and self.batch.running
        count = len(self.batch.items) if hasattr(self, "batch") else 0
        self.documents_button.setVisible(count > 0)
        self.documents_button.setText(f"Documentos ({count})")
        self.documents_button.setEnabled(not batch_running and self.operation in (None, "render"))
        self.batch_button.hide()
        self.batch_action.setEnabled(not self.busy and self.worker.is_alive())
        self.batch_button.setEnabled(not self.busy and self.worker.is_alive())
        importing = self.result is None or self.operation == "convert"
        previous = self.content.currentWidget()
        self.content.setCurrentWidget(self.welcome if importing else self.workspace)
        self.header.setVisible(not importing)
        self.update_import_state()
        if not importing and previous is self.welcome:
            focus = self._import_return_focus
            if focus is None or not self.workspace.isAncestorOf(focus) or not focus.isEnabled():
                focus = self.editor
            focus.setFocus(Qt.OtherFocusReason)
            self._import_return_focus = None
        self.open_button.setVisible(self.result is not None)
        self.export_button.setVisible(self.result is not None)
        self.export_options.setVisible(self.result is not None)
        self.update_modified()
        filtered_count = len(self.result.filtered_images) if self.result else 0
        self.filtered_button.setVisible(filtered_count > 0)
        self.filtered_button.setText(f"Imagens filtradas ({filtered_count})")
        self.filtered_button.setEnabled(self.result is not None and self.operation in (None, "render"))
        navigation = self.result is not None and self.operation in (None, "render") and self.worker.is_alive()
        self.open_button.setEnabled(not self.busy)
        self.follow_page.setEnabled(self.result is not None)
        self.export_button.setEnabled(self.result is not None and not self.busy)
        self.strip_markers_option.setEnabled(self.result is not None and not self.busy)
        self.export_options.setEnabled(self.result is not None and not self.busy)
        self.page_number.setEnabled(navigation)
        current = self.requested_page or 1
        self.pdf_panel.previous.setEnabled(navigation and current > 1)
        self.pdf_panel.next.setEnabled(navigation and current < self.page_number.maximum())
        self.pdf_panel.zoom.setEnabled(navigation)
        self.pdf_panel.zoom_out.setEnabled(navigation and self.zoom_percent > 25)
        self.pdf_panel.zoom_in.setEnabled(navigation and self.zoom_percent < 300)
        self.pdf_panel.fit_width.setEnabled(navigation)
        self.pdf_panel.fit_page.setEnabled(navigation)
        self.pdf_panel.fit_width.setChecked(self.zoom_mode == "width")
        self.pdf_panel.fit_page.setChecked(self.zoom_mode == "page")
        # Continuar recebendo foco/atalhos e rolagem enquanto a nova imagem é
        # preparada; apenas a seleção para recorte precisa ficar suspensa.
        self.page_view.setEnabled(navigation)
        self.page_view.set_selection_enabled(navigation and not self.busy and self.displayed_page is not None)
        self.editor.setReadOnly(self.operation in ("convert", "crop", "batch"))
        self.editor_tools.setEnabled(self.result is not None and self.operation not in ("convert", "crop", "batch"))
        self.preview.set_interaction_available(self.result is not None and not self.busy and not self.preview_dirty)
        can_edit = self.result is not None and self.operation not in ("convert", "crop", "batch")
        self.preview.undo_button.setEnabled(can_edit and self.editor.document().isUndoAvailable())
        self.preview.redo_button.setEnabled(can_edit and self.editor.document().isRedoAvailable())
        self.follow_page.setEnabled(self.result is not None and not batch_running)
        self.pdf_toggle.setEnabled(not batch_running)
        if self.batch_dialog is not None:
            self.batch_dialog.refresh()

    def tab_changed(self, *_):
        session = self.active_session
        QTimer.singleShot(0, lambda: self.follow_current_page() if self.active_session is session else None)

    def _show_batch_dialog(self, preparing):
        if self.batch_dialog is not None:
            self.batch_dialog.raise_()
            return
        self.save_active_session()
        dialog = BatchDialog(self, preparing)
        self.batch_dialog = dialog
        def release(*_):
            if self.batch_dialog is dialog:
                self.batch_dialog = None
            dialog.deleteLater()
        dialog.finished.connect(release)
        dialog.show()

    def open_batch(self):
        if not self.busy and self.worker.is_alive():
            self._show_batch_dialog(True)

    def show_documents(self):
        if self.batch.items and self.operation in (None, "render"):
            self._show_batch_dialog(False)

    def open_pdf(self):
        if self.busy or (not self.batch.items and not self.confirm_discard()):
            return
        return_focus = QApplication.focusWidget()
        source, _ = QFileDialog.getOpenFileName(self, "Abrir PDF digital", "", "PDF (*.pdf)")
        if not source:
            return
        if self.application.start_conversion(source):
            self._import_return_focus = return_focus
            self.update_controls()

    def request_page(self, number):
        if self.result is None or self.operation not in (None, "render"):
            return
        if not 1 <= number <= len(self.result.pages):
            return
        self.requested_page = number
        self.page_number.blockSignals(True)
        self.page_number.setValue(number)
        self.page_number.blockSignals(False)
        self.calculate_zoom()
        self.schedule_render()

    def step_page(self, delta):
        self.request_page((self.requested_page or 1) + delta)

    def install_shortcuts(self):
        self.shortcuts = []
        for key, callback in (("Ctrl+O", self.open_pdf),
                              ("Ctrl+S", lambda: self.export() if self.export_button.isEnabled() else None),
                              ("Alt+Left", lambda: self.step_page(-1)),
                              ("Alt+Right", lambda: self.step_page(1))):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(callback)
            self.shortcuts.append(shortcut)
        for keys, callback in ((("Ctrl++", "Ctrl+="), lambda: self.step_zoom(25)),
                               (("Ctrl+-",), lambda: self.step_zoom(-25)),
                               (("Ctrl+0",), lambda: self.set_zoom_mode("width"))):
            shortcut = QShortcut(self.pdf_panel)
            shortcut.setKeys([QKeySequence(key) for key in keys])
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(callback)
            self.shortcuts.append(shortcut)

    def calculate_zoom(self):
        if self.result is None or self.requested_page is None:
            return
        page = self.result.pages[self.requested_page - 1]
        viewport = self.pdf_scroll.viewport().size()
        if self.zoom_mode != "manual":
            width_scale = max(1, viewport.width() - 2) / (page.width * 100 / 72)
            height_scale = max(1, viewport.height() - 2) / (page.height * 100 / 72)
            self.zoom_percent = 100 * (min(width_scale, height_scale) if self.zoom_mode == "page" else width_scale)
        self.pdf_panel.zoom.blockSignals(True)
        self.pdf_panel.zoom.setValue(self.zoom_percent)
        self.pdf_panel.zoom.blockSignals(False)

    def image_size(self):
        page = self.result.pages[self.requested_page - 1]
        scale = 100 / 72 * self.zoom_percent / 100
        return QSize(max(1, round(page.width * scale)), max(1, round(page.height * scale)))

    def viewport_resized(self):
        if self.switching_session:
            return
        if (hasattr(self, "render_timer") and self.result is not None and self.requested_page is not None
                and not self.pdf_panel.isHidden()
                and self.zoom_mode != "manual" and self.operation in (None, "render")):
            old = self.image_size()
            self.calculate_zoom()
            if old != self.image_size():
                self.resize_current_image()
                self.schedule_render(debounce=True)

    def set_manual_zoom(self, percent):
        if self.result is None or self.operation not in (None, "render"):
            return
        self.zoom_mode = "manual"
        self.zoom_percent = max(25, min(300, percent))
        self.calculate_zoom()
        self.resize_current_image()
        self.schedule_render(debounce=True)

    def step_zoom(self, delta):
        self.set_manual_zoom(self.zoom_percent + delta)

    def set_zoom_mode(self, mode):
        if self.result is None or self.operation not in (None, "render"):
            return
        self.zoom_mode = mode
        self.calculate_zoom()
        self.resize_current_image()
        self.schedule_render(debounce=True)

    def resize_current_image(self, reset_top=False, new_image=None):
        if (self.displayed_page != self.requested_page
                or (self.page_view.original is None and new_image is None)):
            return
        width, height = max(1, self.page_view.width()), max(1, self.page_view.height())
        viewport = self.pdf_scroll.viewport()
        horizontal, vertical = self.pdf_scroll.horizontalScrollBar(), self.pdf_scroll.verticalScrollBar()
        cx = (horizontal.value() + min(width, viewport.width()) / 2) / width
        cy = (vertical.value() + min(height, viewport.height()) / 2) / height
        self.view_revision += 1
        revision = self.view_revision
        if new_image:
            path, rect = new_image
            self.page_view.show_page(path, rect, self.image_size())
        else:
            self.page_view.resize_image(self.image_size())

        def restore():
            if revision != self.view_revision:
                return
            horizontal.setValue(0 if reset_top else round(cx * self.page_view.width() - viewport.width() / 2))
            vertical.setValue(0 if reset_top else round(cy * self.page_view.height() - viewport.height() / 2))

        restore()
        QTimer.singleShot(0, restore)

    def schedule_render(self, debounce=False):
        self.render_sequence += 1
        request_id = self.render_sequence
        dpi = max(25, min(300, round(self.zoom_percent)))
        path = str(self.root / f"page-{request_id}.png")
        self.pending_render = (request_id, str(self.result.source), self.requested_page, dpi, path)
        self.desired_render = request_id
        self.busy, self.operation = True, "render"
        self.statusBar().showMessage(f"Carregando página {self.requested_page}…")
        if debounce:
            self.render_timer.start()
        else:
            self.render_timer.stop()
            self.dispatch_render()
        self.update_controls()

    def dispatch_render(self):
        if self.active_render is None and self.pending_render is not None:
            self.active_render, self.pending_render = self.pending_render, None
            self.application.dispatch_render(self.active_render)

    def finish_render(self, kind, args):
        request_id = args[0]
        if self.active_render is None or self.active_render[0] != request_id:
            return
        request = self.active_render
        self.active_render = None
        try:
            if request_id == self.desired_render:
                if kind == "render_error":
                    raise ValueError(args[1])
                _, page, path, rect = args
                previous = self.displayed_page
                self.displayed_page = page
                try:
                    self.resize_current_image(reset_top=previous != page, new_image=(path, rect))
                except Exception:
                    self.displayed_page = previous
                    raise
                self.statusBar().clearMessage()
                if not self.restore_pdf_session_view() and (previous != page or (self.follow_page.isChecked()
                        and page not in unique_markers(self.editor.toPlainText()))):
                    self.follow_current_page()
        except Exception as exc:
            self.requested_page = self.displayed_page or 1
            self.page_number.blockSignals(True)
            self.page_number.setValue(self.displayed_page or 1)
            self.page_number.blockSignals(False)
            self.calculate_zoom()
            self.resize_current_image()
            self.statusBar().showMessage("Falha ao carregar a página. Você pode tentar novamente.")
            QMessageBox.critical(self, "Não foi possível carregar a página", str(exc))
        finally:
            Path(request[-1]).unlink(missing_ok=True)
        if not self.render_timer.isActive():
            self.dispatch_render()
        if self.active_render is None and self.pending_render is None:
            self.busy, self.operation = False, None
        self.update_controls()

    def crop(self, bbox):
        if not self.result or self.busy or self.displayed_page is None:
            return
        self.crop_cursor = self.editor.textCursor()
        self.crop_bbox = tuple(bbox)
        self.application.start_crop(self.result.source, self.result.workspace, self.displayed_page, bbox)
        self.update_controls()

    def warning_clicked(self, item):
        self.set_pdf_visible(True)
        page = item.data(Qt.ItemDataRole.UserRole)
        if page and self.operation in (None, "render"):
            self.request_page(page)

    def mark_preview_dirty(self):
        if self.switching_session:
            return
        self.preview_dirty = True
        self.preview.clear_image_selection()
        self.preview.set_interaction_available(False)
        self.preview_timer.start()
        self.update_controls()

    def refresh_preview(self):
        # A synchronous refresh consumes the pending deferred rebuild as well.
        # Otherwise it may clear a new image selection after a session snapshot.
        self.preview_timer.stop()
        if self.result:
            saved = reading_position(self.preview)
            horizontal = self.preview.horizontalScrollBar().value()
            document = preview_document(self.editor.toPlainText(), self.result.workspace, self.preview)
            previous_document = self.preview.document()
            previous_document.setParent(None)
            self.preview.setDocument(document)
            previous_document.deleteLater()
            self.preview.configure_images(self.editor.toPlainText(), self.result.workspace, self.result.assets)
            restore_reading_position(self.preview, saved)
            self.preview.horizontalScrollBar().setValue(horizontal)
            self.preview_dirty = False
            self.update_controls()

    def review_filtered_images(self):
        if self.result and self.result.filtered_images and self.operation in (None, "render"):
            dialog = FilteredImagesDialog(self)
            dialog.exec()
            dialog.deleteLater()

    def restore_filtered_image(self, filtered):
        if not self.result or self.operation not in (None, "render") or self.editor.isReadOnly():
            raise ValueError("Aguarde o processamento antes de restaurar uma imagem.")
        if filtered not in self.result.filtered_images:
            raise ValueError("Esta imagem não pertence ao documento atual.")
        markdown = self.editor.toPlainText()
        position, insertion = restoration_edit(self.result, markdown, filtered)
        saved = self.editor.textCursor()
        cursor = QTextCursor(self.editor.document())
        cursor.setPosition(utf16_position(markdown, position))
        cursor.beginEditBlock()
        cursor.insertText(insertion)
        cursor.endEditBlock()
        self.editor.setTextCursor(saved)
        self.statusBar().showMessage("Imagem restaurada ao final do trecho da página. Use desfazer para reverter.")

    def remove_preview_images(self):
        if not self.result or self.busy or self.preview_dirty or not self.preview.selected_images:
            return
        try:
            plan = build_manual_cleanup_plan(self.result, self.editor.toPlainText(), self.preview.selected_images)
            self.apply_cleanup_plan(plan, self.strip_page_markers)
        except ValueError as exc:
            self.preview.clear_image_selection()
            self.statusBar().showMessage(str(exc))
            return
        self.preview_timer.stop()
        self.refresh_preview()

    def follow_current_page(self):
        if (not self.follow_page.isChecked() or not self.result
                or self.displayed_page is None or self.displayed_page != self.requested_page):
            return
        marker = unique_markers(self.editor.toPlainText()).get(self.displayed_page)
        if marker is None:
            self.statusBar().showMessage(
                f"Página {self.displayed_page}: marcador ausente ou duplicado no Markdown; comparação automática indisponível.")
            return
        if self.preview_dirty:
            self.preview_timer.stop()
            self.refresh_preview()
        scroll_editor_to(self.editor, utf16_position(self.editor.toPlainText(), marker.start()))
        # Permitir que até as últimas páginas com pouco texto alcancem o topo.
        frame = self.preview.document().rootFrame()
        fmt = frame.frameFormat()
        fmt.setBottomMargin(self.preview.viewport().height())
        frame.setFrameFormat(fmt)
        self.preview.scrollToAnchor(f"pdf-page-{self.displayed_page}")

    def set_strip_page_markers(self, checked):
        if checked != self.strip_page_markers:
            self.strip_page_markers = checked
            if self.active_session:
                self.active_session.strip_markers = checked
            self.update_modified()

    def apply_cleanup_plan(self, plan, strip_markers):
        if self.busy:
            raise ValueError("Aguarde o processamento antes de aplicar a limpeza.")
        markdown = self.editor.toPlainText()
        apply_cleanup(markdown, plan)  # Rejeitar seleções calculadas sobre outro texto.
        if plan.removals:
            saved = self.editor.textCursor()
            cursor = QTextCursor(self.editor.document())
            cursor.beginEditBlock()
            for removal in reversed(plan.removals):
                cursor.setPosition(utf16_position(markdown, removal.start))
                cursor.setPosition(utf16_position(markdown, removal.end), QTextCursor.MoveMode.KeepAnchor)
                cursor.removeSelectedText()
            cursor.endEditBlock()
            self.editor.setTextCursor(saved)
            self.cleanup_removals.extend(plan.removals)
        if strip_markers != self.strip_page_markers:
            self.strip_page_markers = strip_markers
            self.editor.document().setModified(True)
        if plan.removals:
            self.statusBar().showMessage(
                f"{len(plan.removals)} incorporações removidas; {len(plan.skipped)} ocorrências mantidas. "
                "Use Ctrl+Z no editor para desfazer a limpeza.")
        else:
            self.statusBar().showMessage("Opções de exportação atualizadas. Nenhuma imagem foi removida.")

    @property
    def busy(self):
        return self.application.busy

    @busy.setter
    def busy(self, value):
        self.application.set_state(value, self.application.operation)

    @property
    def operation(self):
        return self.application.operation or None

    @operation.setter
    def operation(self, value):
        self.application.set_state(self.application.busy, value)

    def poll(self):
        self.application.poll()

    def update_import_state(self):
        if not hasattr(self, 'welcome'):
            return
        count = len(self.batch.items) if hasattr(self, 'batch') else 0
        batch_running = hasattr(self, 'batch') and self.batch.running
        self.welcome.update_state(
            converting=self.operation == 'convert',
            cancelling=self.operation == 'convert' and self.application.cancellationRequested,
            canImport=not self.busy and self.application.workerAvailable,
            documentsEnabled=not batch_running and self.operation in (None, 'render'),
            documentCount=count, sourceName=self.application.sourceName,
            progressCurrent=self.application.progressCurrent,
            progressTotal=self.application.progressTotal,
            ocrMode=self.application.ocrMode, ocrStatus=self.application.recognitionStatus,
            conversionStage=self.application.conversionStage)

    def import_load_failed(self, message):
        self.statusBar().showMessage('Interface QML indisponível; usando a tela de importação Widgets.')
        self.statusBar().setToolTip(message)

    def receive_crop(self, asset):
        embedding = f"![Recorte da página {self.displayed_page}]({asset})"
        self.crop_cursor.insertText(f"\n\n{embedding}\n\n")
        self.editor.setTextCursor(self.crop_cursor)
        page = self.result.pages[self.displayed_page - 1]
        self.result.assets.append(AssetInfo(asset, "manual", "manual", self.displayed_page,
                                           self.crop_bbox, (page.width, page.height),
                                           generated_markdown=embedding))
        self.update_controls()

    def conversion_cancelled(self):
        self.statusBar().showMessage("Conversão cancelada. O vault não foi alterado.")
        self.update_controls()

    def operation_failed(self, message):
        QMessageBox.critical(self, "Não foi possível concluir", message)
        self.update_controls()

    def worker_failed(self):
        self.render_timer.stop()
        self.pending_render = self.active_render = None
        self.update_controls()
        QMessageBox.critical(self, "Processamento interrompido", "O processo de PDF terminou inesperadamente. Feche e reabra a aplicação.")

    def export(self):
        if self.result is None or self.busy:
            return
        vault = QFileDialog.getExistingDirectory(self, "Escolher pasta do vault")
        if not vault:
            return
        self.save_active_session()
        record = self.active_session.exports.get(str(Path(vault).resolve()))
        manifest = {}
        try:
            target, signature = self.application.export_document(self.result, vault, self.editor.toPlainText(),
                strip_page_markers=self.strip_page_markers,
                cleanup_removals=self.cleanup_removals, record=record, manifest=manifest)
        except Exception as exc:
            QMessageBox.critical(self, "Falha ao salvar", str(exc))
            return
        self.save_active_session()
        self.active_session.record_export(vault, signature, target, manifest)
        title = 'Documento já salvo' if record and record.target == target else 'Documento salvo'
        message = f'Arquivos gravados em:\n{target}'
        if record and record.signature == signature and record.target != target:
            message = 'A publicação anterior está incompleta ou foi alterada e foi preservada.\n\n' + message
        QMessageBox.information(self, title, message)

    def closeEvent(self, event):
        if self.batch.running:
            self.batch.cancel()
            event.ignore()
            return
        if not self.confirm_discard():
            event.ignore()
            return
        self.poll_timer.stop()
        self.render_timer.stop()
        self.preview_timer.stop()
        self.application.shutdown()
        event.accept()


def main():
    if '--widgets' not in sys.argv:
        from .quick import main as quick_main
        sys.exit(quick_main())
    sys.argv.remove('--widgets')
    mp.freeze_support()
    app = QApplication(sys.argv)
    window = Window()
    window.show()
    sys.exit(app.exec())
