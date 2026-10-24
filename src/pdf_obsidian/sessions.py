"""Documentos de edição duráveis; nenhuma preferência é gravada em disco."""
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from PySide6.QtGui import QTextDocument

from .models import ConversionResult


@dataclass
class ExportRecord:
    signature: str
    target: Path
    manifest: dict = field(default_factory=dict)


@dataclass
class DocumentSession:
    result: ConversionResult
    document: QTextDocument
    id: str = field(default_factory=lambda: uuid4().hex)
    strip_markers: bool = False
    removals: list = field(default_factory=list)
    view: dict = field(default_factory=dict)
    exports: dict[str, ExportRecord] = field(default_factory=dict)
    saved_strip_markers: bool = False

    @property
    def modified(self):
        return self.document.isModified() or self.strip_markers != self.saved_strip_markers

    @classmethod
    def create(cls, result, owner):
        document = QTextDocument(owner)
        from PySide6.QtWidgets import QPlainTextDocumentLayout
        document.setDocumentLayout(QPlainTextDocumentLayout(document))
        document.setDefaultFont(owner.editor.font())
        document.setPlainText(result.markdown)
        document.setModified(True)
        return cls(result, document)

    def record_export(self, vault, signature, target, manifest=None):
        # Widgets publica sincronicamente; Quick/lote recebem o manifesto do worker.
        if manifest is None:
            from .exporter import export_manifest
            manifest = export_manifest(target)
        self.exports[str(Path(vault).resolve())] = ExportRecord(signature, Path(target), manifest)
        self.saved_strip_markers = self.strip_markers
        self.document.setModified(False)
