import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import time
import pymupdf
import pytest
from PySide6.QtWidgets import QFileDialog, QMessageBox
from pdf_obsidian.gui import Window


def wait_until(app, window, predicate):
    deadline = time.monotonic() + 15
    while not predicate():
        app.processEvents()
        if time.monotonic() > deadline:
            pytest.fail("O processo auxiliar não respondeu a tempo.")
        time.sleep(.01)
    app.processEvents()


def test_window_starts_and_closes(app):
    window = Window()
    assert window.open_button.isEnabled()
    assert not window.export_button.isEnabled()
    assert not window.welcome.state['converting']
    assert window.welcome.using_qml
    process = window.worker
    window.close()
    app.processEvents()
    assert not process.is_alive()
    assert not window.root.exists()


def test_conversion_crop_and_export_through_gui(app, tmp_path, monkeypatch):
    source = tmp_path / "apostila.pdf"
    with pymupdf.open() as doc:
        page = doc.new_page()
        page.insert_text((50, 100), "Titulo da aula", fontsize=20)
        page.insert_text((50, 150), "Texto para estudo.", fontsize=12)
        doc.save(source)
    vault = tmp_path / "vault"
    vault.mkdir()
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a: (str(source), "PDF"))
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *a: str(vault))
    monkeypatch.setattr(QMessageBox, "information", lambda *a: QMessageBox.StandardButton.Ok)
    monkeypatch.setattr(QMessageBox, "question", lambda *a: QMessageBox.StandardButton.Yes)
    errors = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *args: errors.append(args[-1]))
    window = Window()
    try:
        window.open_pdf()
        wait_until(app, window, lambda: window.result is not None and not window.busy)
        assert window.displayed_page == 1
        assert "Texto para estudo" in window.editor.toPlainText()
        assert window.page_view.original.width() > 0
        window.editor.appendPlainText("Correcao feita na interface.")
        window.crop((40, 90, 250, 180))
        wait_until(app, window, lambda: not window.busy)
        assert "recorte-" in window.editor.toPlainText()
        window.refresh_preview()
        assert "Correcao feita na interface" in window.preview.toPlainText()
        window.export()
        exported = list((vault / "Importados").glob("*/*.md"))
        assert len(exported) == 1
        assert "Correcao feita na interface" in exported[0].read_text()
        assert "recorte-" in exported[0].read_text()
        assert "PDFObsidian" not in exported[0].read_text()
        assert "pdf-page-" not in exported[0].read_text()
        assert not window.editor.document().isModified()
        assert not errors
    finally:
        window.close()


def test_ocr_controls_require_prepared_resources(app, monkeypatch):
    from pdf_obsidian.batch_dialog import BatchDialog
    from pdf_obsidian.import_panel import LegacyImportPage
    window = Window()
    batch = BatchDialog(window, preparing=True)
    fallback = LegacyImportPage(window.welcome)
    try:
        fallback.update_state(window.welcome.state)
        for control in (window.next_ocr_option, batch.ocr, fallback.ocr):
            assert not control.isChecked() and not control.isEnabledTo(control.parentWidget())
        monkeypatch.setattr('pdf_obsidian.application.resource_status', lambda: (True, 'OCR local pronto', {}))
        window.application.ocr_setup.changed.emit()
        fallback.update_state(window.welcome.state)
        for control in (window.next_ocr_option, batch.ocr, fallback.ocr):
            assert not control.isChecked() and control.isEnabledTo(control.parentWidget())
        batch.ocr.click()
        fallback.update_state(window.welcome.state)
        assert window.application.ocrMode == 'auto'
        assert all(control.isChecked() for control in (window.next_ocr_option, batch.ocr, fallback.ocr))
    finally:
        batch.close()
        fallback.close()
        window.close()
        app.processEvents()
