"""Barra de edição; o Markdown permanece a fonte de verdade."""
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QKeySequence, QShortcut, QTextCursor
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QFrame, QMenu, QToolButton, QVBoxLayout, QWidget,
)

from .appearance import tool_icon, CONTROL_HEIGHT, AdaptiveRow
from .formatting import format_text, link_label
from .markdown import utf16_position
from .tokens import METRICS


def python_position(text, qt_position):
    return len(text.encode("utf-16-le")[:qt_position * 2].decode("utf-16-le"))


class LinkDialog(QDialog):
    def __init__(self, label, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Inserir link")
        layout = QFormLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        self.label = QLineEdit(label)
        self.destination = QLineEdit()
        self.destination.setPlaceholderText("https://… ou caminho relativo")
        for text, field in (("Texto", self.label), ("Destino", self.destination)):
            caption = QLabel(text)
            caption.setObjectName("formLabel")
            caption.setBuddy(field)
            layout.addRow(caption, field)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Inserir link")
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setObjectName("primary")
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        self.destination.textChanged.connect(lambda text: self.buttons.button(
            QDialogButtonBox.StandardButton.Ok).setEnabled(bool(text.strip())))
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addRow(self.buttons)
        available = self.screen().availableGeometry()
        self.resize(min(480, max(240, available.width() - 48)), self.sizeHint().height())
        (self.destination if label else self.label).setFocus()


class EditorTools(QWidget):
    def __init__(self, editor, notify, parent=None):
        super().__init__(parent)
        self.editor = editor
        self.notify = notify
        self.setObjectName("editorTools")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 6, 0, 6)
        adaptive = AdaptiveRow()
        outer.addWidget(adaptive)
        inline, structure = QWidget(), QWidget()
        inline.setObjectName("toolGroup")
        structure.setObjectName("toolGroup")
        first = QHBoxLayout(inline)
        layout = QHBoxLayout(structure)
        for group in (first, layout):
            group.setContentsMargins(3, 3, 3, 3)
            group.setSpacing(2)
        adaptive.row.addWidget(inline)
        adaptive.row.addWidget(structure)
        adaptive.row.addStretch()
        self.buttons = {}
        self.heading = QComboBox()
        self.heading.setAccessibleName("Estilo do parágrafo")
        self.heading.addItem("Estilo…", None)
        self.heading.addItem("Parágrafo", 0)
        for level in range(1, 7):
            self.heading.addItem(f"Título {level}", level)
        self.heading.setToolTip("Aplicar ao parágrafo atual ou aos parágrafos selecionados")
        self.heading.activated.connect(self.heading_selected)
        first.addWidget(self.heading)
        for command, label, tip in (
            ("bold", "B", "Negrito (Ctrl+B)"),
            ("italic", "I", "Itálico (Ctrl+I)"),
            ("link", "Link", "Inserir link (Ctrl+K)"),
        ):
            self.add_button(first, command, label, tip)
        self.add_separator(first)
        self.menus = {}
        for name, entries in (
            ("Listas", (("bullet", "Lista com marcadores"), ("ordered", "Lista numerada"), ("quote", "Citação"))),
            ("Alinhar", tuple(("align:" + value, label) for value, label in
                (("left", "Esquerda"), ("center", "Centro"), ("right", "Direita"), ("justify", "Justificar")))),
        ):
            button = QToolButton()
            button.setText(name)
            button.setAccessibleName(name)
            button.setMinimumHeight(32)
            button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            menu = QMenu(button)
            for key, label in entries:
                # Manter os controles de comando para atalhos e integrações existentes.
                value = key.split(":")[1] if key.startswith("align:") else None
                self.add_button(layout, key, label, label, "align" if value else key, value)
                self.buttons[key].hide()
                action = menu.addAction(self.buttons[key].icon(), label)
                action.triggered.connect(lambda checked=False, key=key: self.buttons[key].click())
            button.setMenu(menu)
            button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
            self.menus[name] = button
            layout.addWidget(button)
        layout.addStretch()
        self.shortcuts = []
        for keys, command in (("Ctrl+B", "bold"), ("Ctrl+I", "italic"), ("Ctrl+K", "link")):
            shortcut = QShortcut(QKeySequence(keys), editor)
            shortcut.setContext(Qt.ShortcutContext.WidgetShortcut)
            shortcut.activated.connect(lambda command=command: self.apply(command) if self.isEnabled() else None)
            self.shortcuts.append(shortcut)

    @staticmethod
    def add_separator(row):
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setFixedSize(1, 18)
        separator.setObjectName("separator")
        row.addSpacing(6)
        row.addWidget(separator)
        row.addSpacing(6)

    def add_button(self, row, key, label, tip, command=None, value=None):
        button = QToolButton()
        button.setText(label)
        button.setFixedSize(CONTROL_HEIGHT, CONTROL_HEIGHT)
        button.setIconSize(QSize(METRICS["iconSize"], METRICS["iconSize"]))
        icon_name = value if key.startswith("align:") else key
        if icon_name in ("bold", "italic", "left", "center", "right", "justify", "bullet", "ordered", "quote", "link"):
            button.setIcon(tool_icon(icon_name))
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        if key.startswith("align:"):
            name = {"left": "Esquerda", "center": "Centro", "right": "Direita", "justify": "Justificar"}[value]
            tip = name + " — " + tip
        button.setAccessibleName(tip.split(" — ")[0])
        button.setToolTip(tip)
        if key in ("bold", "italic"):
            font = button.font()
            font.setBold(key == "bold")
            font.setItalic(key == "italic")
            button.setFont(font)
        button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        button.clicked.connect(lambda: self.apply(command or key, value))
        self.buttons[key] = button
        row.addWidget(button)

    def heading_selected(self, index):
        value = self.heading.itemData(index)
        if value is not None:
            self.apply("heading", value)
        self.heading.setCurrentIndex(0)

    def apply(self, command, value=None):
        if not self.isEnabled() or self.editor.isReadOnly():
            return
        text = self.editor.toPlainText()
        saved = self.editor.textCursor()
        reverse_selection = saved.anchor() > saved.position()
        start = python_position(text, saved.selectionStart())
        end = python_position(text, saved.selectionEnd())
        if command == "link":
            try:
                label = link_label(text, start, end)
            except ValueError as exc:
                self.notify(str(exc))
                self.editor.setFocus()
                return
            dialog = LinkDialog(label, self)
            accepted = dialog.exec() == QDialog.DialogCode.Accepted
            self.editor.window().activateWindow()
            if not accepted:
                dialog.deleteLater()
                self.editor.setFocus()
                return
            value = (dialog.label.text(), dialog.destination.text().strip())
            dialog.deleteLater()
        try:
            edit = format_text(text, start, end, command, value)
        except ValueError as exc:
            self.notify(str(exc))
            self.editor.setFocus()
            return
        updated = text[:edit.start] + edit.text + text[edit.end:]
        cursor = QTextCursor(self.editor.document())
        if updated != text:
            cursor.beginEditBlock()
            cursor.setPosition(utf16_position(text, edit.start))
            cursor.setPosition(utf16_position(text, edit.end), QTextCursor.MoveMode.KeepAnchor)
            cursor.insertText(edit.text)
            cursor.endEditBlock()
        # Preservar também a direção da seleção, importante para Shift+setas.
        a, b = edit.selection_start, edit.selection_end
        if reverse_selection:
            a, b = b, a
        cursor.setPosition(utf16_position(updated, a))
        cursor.setPosition(utf16_position(updated, b), QTextCursor.MoveMode.KeepAnchor)
        self.editor.setTextCursor(cursor)
        self.editor.setFocus()
        self.notify("Formatação aplicada." if updated != text else "Formatação mantida.")
