"""Troca de documentos sem recriar o histórico do editor."""
from pathlib import Path
import shutil

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QTextCursor, QTextDocument
from PySide6.QtWidgets import QMessageBox, QPlainTextDocumentLayout

from .comparison import reading_position, restore_reading_position
from .sessions import DocumentSession


class SessionWindowMixin:
    def create_session(self, result):
        session = DocumentSession.create(result, self)
        self.sessions[session.id] = session
        return session

    def save_active_session(self):
        if self.result is None:
            return
        if self.active_session is None or self.active_session.result is not self.result:
            document = self.editor.document()
            document.setParent(self)
            self.active_session = DocumentSession(self.result, document)
            self.sessions[self.active_session.id] = self.active_session
        session = self.active_session
        session.strip_markers = self.strip_page_markers
        session.removals = self.cleanup_removals
        cursor = self.editor.textCursor()
        h, v = self.pdf_scroll.horizontalScrollBar(), self.pdf_scroll.verticalScrollBar()
        viewport = self.pdf_scroll.viewport()
        center = ((h.value() + viewport.width() / 2) / max(1, self.page_view.width()),
                  (v.value() + viewport.height() / 2) / max(1, self.page_view.height()))
        session.view = dict(cursor=(cursor.anchor(), cursor.position()),
            editor_scroll=(self.editor.horizontalScrollBar().value(), self.editor.verticalScrollBar().value()),
            preview=reading_position(self.preview), preview_x=self.preview.horizontalScrollBar().value(),
            selected=set(self.preview.selected_images), selection_mode=self.preview.selection_mode.isChecked(),
            tab=self.tabs.currentIndex(), page=self.requested_page or self.displayed_page or 1,
            zoom_mode=self.zoom_mode, zoom_percent=self.zoom_percent, follow=self.follow_page.isChecked(),
            pdf_visible=not self.pdf_panel.isHidden(),
            sizes=self.splitter.sizes() if not self.pdf_panel.isHidden() else self.pdf_sizes.copy(),
            pdf_center=center if self.displayed_page == self.requested_page else None,
            warnings=self.warnings_toggle.isChecked())

    def activate_session(self, session_id):
        if self.operation not in (None, 'render'):
            return False
        session = self.sessions.get(session_id)
        if session is None:
            return False
        if self.active_session is session and self.result is session.result:
            return True
        self.save_active_session()
        self.switching_session = True
        self.preview_timer.stop()
        self.render_timer.stop()
        self.pending_render = self.desired_render = None
        self.view_revision += 1
        self.restoring_pdf = None
        old_document = self.editor.document()
        try:
            old_document.modificationChanged.disconnect(self.update_modified)
        except (RuntimeError, TypeError):
            pass
        # O proprietário não é o widget: setDocument não deve apagar o histórico anterior.
        old_document.setParent(self)
        self.result, self.active_session = session.result, session
        view = session.view
        self.editor.blockSignals(True)
        self.editor.setDocument(session.document)
        cursor = QTextCursor(session.document)
        anchor, position = view.get('cursor', (0, 0))
        maximum = session.document.characterCount() - 1
        cursor.setPosition(min(anchor, maximum))
        cursor.setPosition(min(position, maximum), QTextCursor.KeepAnchor)
        self.editor.setTextCursor(cursor)
        self.editor.blockSignals(False)
        session.document.modificationChanged.connect(self.update_modified)
        self.strip_page_markers, self.cleanup_removals = session.strip_markers, session.removals
        self.strip_markers_option.blockSignals(True)
        self.strip_markers_option.setChecked(session.strip_markers)
        self.strip_markers_option.blockSignals(False)
        self.document_label.setText(session.result.source.name)
        self.document_label.setToolTip(str(session.result.source))
        self.follow_page.blockSignals(True)
        self.follow_page.setChecked(view.get('follow', True))
        self.follow_page.blockSignals(False)
        self.tabs.blockSignals(True)
        self.tabs.setCurrentIndex(view.get('tab', 0))
        self.tabs.blockSignals(False)
        self.pdf_sizes = view.get('sizes', [480, 720]).copy()
        visible = view.get('pdf_visible', True)
        self.pdf_panel.setVisible(visible)
        self.pdf_toggle.setText('Ocultar PDF' if visible else 'Mostrar PDF')
        if visible:
            self.splitter.setSizes(self.pdf_sizes)
        self.zoom_mode, self.zoom_percent = view.get('zoom_mode', 'width'), view.get('zoom_percent', 100.)
        self.displayed_page = self.requested_page = None
        self.page_view.clear_page()
        self.page_number.blockSignals(True)
        self.page_number.setRange(1, len(session.result.pages))
        self.page_number.setValue(view.get('page', 1))
        self.page_number.setSuffix(f' de {len(session.result.pages)}')
        self.page_number.blockSignals(False)
        self.warning_list.clear()
        for warning in session.result.warnings:
            self.warning_list.addItem(f"{'Página ' + str(warning.page) if warning.page else 'Revisão'}: {warning.message}")
            self.warning_list.item(self.warning_list.count() - 1).setData(Qt.UserRole, warning.page)
        self.warnings_toggle.setText(f'Avisos ({self.warning_list.count()})')
        self.warnings_toggle.setChecked(view.get('warnings', False))
        self.preview_dirty = True
        self.refresh_preview()
        self.preview.selection_mode.setChecked(view.get('selection_mode', False))
        self.preview.selected_images = set(view.get('selected', ())) & set(self.preview.targets.values())
        self.preview.viewport().update()
        self.switching_session = False
        self.update_controls()
        self.restoring_pdf = (session.id, view) if view else None
        self.request_page(view.get('page', 1))
        revision = self.view_revision
        def restore_reading():
            if self.active_session is not session or self.view_revision != revision:
                return
            horizontal, vertical = view.get('editor_scroll', (0, 0))
            self.editor.horizontalScrollBar().setValue(horizontal)
            self.editor.verticalScrollBar().setValue(vertical)
            if view.get('preview'):
                restore_reading_position(self.preview, view['preview'])
                self.preview.horizontalScrollBar().setValue(view.get('preview_x', 0))
        restore_reading()
        QTimer.singleShot(0, restore_reading)
        return True

    def restore_pdf_session_view(self):
        restoration = self.restoring_pdf
        self.restoring_pdf = None
        if (not restoration or not self.active_session or restoration[0] != self.active_session.id
                or restoration[1].get('page', 1) != self.displayed_page):
            return False
        session_id, view = restoration
        center = view.get('pdf_center')
        revision = self.view_revision
        def restore():
            if not self.active_session or self.active_session.id != session_id or revision != self.view_revision:
                return
            if center:
                viewport = self.pdf_scroll.viewport()
                self.pdf_scroll.horizontalScrollBar().setValue(round(center[0] * self.page_view.width() - viewport.width() / 2))
                self.pdf_scroll.verticalScrollBar().setValue(round(center[1] * self.page_view.height() - viewport.height() / 2))
        restore()
        QTimer.singleShot(0, restore)
        return True

    def clear_session_view(self):
        self.switching_session = True
        self.preview_timer.stop()
        self.render_timer.stop()
        self.pending_render = self.desired_render = None
        self.restoring_pdf = None
        self.view_revision += 1
        old = self.editor.document()
        old.setParent(self)
        try:
            old.modificationChanged.disconnect(self.update_modified)
        except (RuntimeError, TypeError):
            pass
        document = QTextDocument(self)
        document.setDocumentLayout(QPlainTextDocumentLayout(document))
        self.editor.blockSignals(True)
        self.editor.setDocument(document)
        self.editor.blockSignals(False)
        document.modificationChanged.connect(self.update_modified)
        self.result = self.active_session = None
        self.displayed_page = self.requested_page = None
        self.page_view.clear_page()
        self.preview.clear_image_selection()
        self.preview.clear()
        self.warning_list.clear()
        self.document_label.setText('PDF-Obsidian')
        self.switching_session = False
        self.update_controls()

    def confirm_discard(self, sessions=None):
        candidates = list(self.sessions.values()) if sessions is None else sessions
        dirty = sum(session.modified for session in candidates)
        if sessions is None and not any(session.document is self.editor.document() for session in candidates):
            dirty += self.editor.document().isModified()
        if not dirty:
            return True
        return QMessageBox.question(self, 'Descartar alterações?',
            f'{dirty} documento(s) têm alterações ou conversões não salvas. Deseja descartá-las?',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes

    def discard_batch(self):
        self.save_active_session()
        sessions = [item.session for item in self.batch.items if item.session]
        if not self.confirm_discard(sessions):
            return False
        if self.active_session in sessions:
            self.clear_session_view()
        for session in sessions:
            self.sessions.pop(session.id, None)
            session.document.deleteLater()
            shutil.rmtree(session.result.workspace, ignore_errors=True)
        return True

    def receive_single_document(self, result):
        old_sessions = list(self.sessions.values()) if not self.batch.items else []
        session = self.create_session(result)
        self.activate_session(session.id)
        for previous in old_sessions:
            if previous is not session:
                self.sessions.pop(previous.id, None)
                previous.document.deleteLater()
