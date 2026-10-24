import QtQuick
import QtQuick.Controls.Basic

MenuSeparator {
    id: control
    required property Theme theme
    padding: 4
    contentItem: Rectangle { implicitHeight: 1; color: control.theme.border }
}
