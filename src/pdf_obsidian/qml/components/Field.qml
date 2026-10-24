import QtQuick
import QtQuick.Controls.Basic
TextField {
    id: control
    required property Theme theme
    implicitHeight: Math.max(theme.controlHeight, contentHeight + 12)
    color: enabled ? theme.text : theme.disabled
    placeholderTextColor: theme.muted
    selectionColor: theme.accent
    selectedTextColor: theme.accentText
    font.family: theme.fontFamily
    font.pixelSize: theme.labelSize
    padding: 8
    selectByMouse: true
    background: Rectangle {
        color: control.theme.surface
        radius: control.theme.controlRadius
        border.color: control.activeFocus ? control.theme.accent : control.hovered ? control.theme.controlBorderHover : control.theme.controlBorder
        border.width: control.activeFocus ? 2 : 1
    }
}
