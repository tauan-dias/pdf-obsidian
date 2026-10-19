"""Modelos estáveis: progresso nunca reconstrói a lista de documentos."""
from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt


class RowsModel(QAbstractListModel):
    def __init__(self, fields, parent=None):
        super().__init__(parent)
        self.fields = fields
        self.rows = []

    def roleNames(self):
        return {Qt.ItemDataRole.UserRole + i + 1: name.encode() for i, name in enumerate(self.fields)}

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def data(self, index, role):
        i = role - Qt.ItemDataRole.UserRole - 1
        if index.isValid() and 0 <= index.row() < len(self.rows) and 0 <= i < len(self.fields):
            return self.rows[index.row()].get(self.fields[i])
        return None

    def sync(self, rows):
        """Identidade e ordem sobrevivem às mudanças de status/inclusão."""
        wanted = {row['key'] for row in rows}
        for i in range(len(self.rows) - 1, -1, -1):
            if self.rows[i]['key'] not in wanted:
                self.beginRemoveRows(QModelIndex(), i, i)
                self.rows.pop(i)
                self.endRemoveRows()
        for i, row in enumerate(rows):
            if i >= len(self.rows) or self.rows[i]['key'] != row['key']:
                old = next((j for j in range(i, len(self.rows)) if self.rows[j]['key'] == row['key']), None)
                if old is not None:
                    self.beginMoveRows(QModelIndex(), old, old, QModelIndex(), i)
                    self.rows.insert(i, self.rows.pop(old))
                    self.endMoveRows()
                else:
                    self.beginInsertRows(QModelIndex(), i, i)
                    self.rows.insert(i, dict(row))
                    self.endInsertRows()
            if self.rows[i] != row:
                roles = [Qt.ItemDataRole.UserRole + j + 1 for j, name in enumerate(self.fields)
                         if self.rows[i].get(name) != row.get(name)]
                self.rows[i] = dict(row)
                self.dataChanged.emit(self.index(i), self.index(i), roles)
