import json
import time

import pytest
from PySide6.QtWidgets import QFileDialog, QMessageBox

from pdf_obsidian.gui import Window


@pytest.fixture
def reviewed(app, decorative_source, tmp_path, monkeypatch):
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args: (str(decorative_source), "PDF"))
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QMessageBox, "information", lambda *args: QMessageBox.StandardButton.Ok)
    errors = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *args: errors.append(args[-1]))
    vault = tmp_path / "vault"
    vault.mkdir()
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *args: str(vault))
    window = Window()
    window.show()
    def settle():
        deadline = time.monotonic() + 15
        idle_since = None
        while True:
            app.processEvents()
            if time.monotonic() > deadline:
                pytest.fail("O processo de PDF não respondeu a tempo.")
            if window.busy:
                idle_since = None
            elif idle_since is None:
                idle_since = time.monotonic()
            elif time.monotonic() - idle_since >= .05:
                return
            time.sleep(.01)
    try:
        window.open_pdf()
        settle()
        assert not errors
        yield window, vault, errors, settle
        assert not errors
    finally:
        window.editor.document().setModified(False)
        window.close()
        app.processEvents()


def test_margin_filter_and_page_marker_export_option(reviewed):
    window, vault, _, _ = reviewed
    assert not hasattr(window, "cleanup_button")
    assert not hasattr(window, "review_cleanup")
    original = window.editor.toPlainText()
    assert not window.strip_markers_option.isChecked()
    assert not window.cleanup_removals
    filtered = {item.asset for item in window.result.filtered_images}
    assert len(filtered) == 10
    assert all((asset.generated_markdown in original) == (asset.path not in filtered)
               for asset in window.result.assets)
    window.strip_markers_option.setChecked(True)
    assert window.strip_page_markers
    assert window.editor.toPlainText() == original
    window.export()
    exported = next((vault / "Importados").iterdir())
    assert "<!-- Página" not in next(exported.glob("*.md")).read_text()
    assert window.editor.toPlainText() == original
    report = json.loads((exported / "conversao.json").read_text())
    assert not report["cleanup"]["image_removals"]
    window.strip_markers_option.setChecked(False)
    assert not window.strip_page_markers


def test_manual_crop_remains_available(reviewed):
    window, _, _, settle = reviewed
    window.crop((40, 10, 180, 60))
    settle()
    crop = window.result.assets[-1]
    assert crop.origin == crop.role == "manual"
    assert crop.generated_markdown in window.editor.toPlainText()
