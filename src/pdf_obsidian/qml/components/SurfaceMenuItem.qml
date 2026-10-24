import QtQuick
import QtQuick.Controls.Basic

MenuItem {
    id: control
    required property Theme theme
    implicitHeight: Math.max(theme.controlHeight + 4, label.implicitHeight + 16)
    implicitWidth: Math.max(180, label.implicitWidth + 32)
    padding: 8
    font.family: theme.fontFamily
    font.pixelSize: theme.labelSize
    contentItem: Text {
        textFormat: Text.PlainText
        id: label
        text: control.text
        color: control.enabled ? control.theme.text : control.theme.disabled
        font: control.font
        verticalAlignment: Text.AlignVCenter
    }
    background: Rectangle {
        color: control.highlighted || control.hovered ? control.theme.hover : "transparent"
        radius: control.theme.menuItemRadius
        border.color: control.visualFocus ? control.theme.accent : "transparent"
    }
}
