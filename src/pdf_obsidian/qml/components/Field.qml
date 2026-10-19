import QtQuick
import QtQuick.Controls.Basic
TextField {
    id: control
    required property Theme theme
    implicitHeight: Math.max(32, contentHeight + 14)
    color: theme.text
    placeholderTextColor: theme.disabled
    selectionColor: theme.accent
    selectedTextColor: theme.accentText
    font.family: theme.fontFamily
    font.pixelSize: theme.bodySize
    padding: 8
    selectByMouse: true
    background: Rectangle {
        color: control.theme.background
        radius: control.theme.controlRadius
        border.color: control.activeFocus ? control.theme.accent : control.theme.border
        border.width: control.activeFocus ? 2 : 1
    }
}
