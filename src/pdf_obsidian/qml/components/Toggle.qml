import QtQuick
import QtQuick.Controls.Basic
CheckBox {
    id: control
    required property Theme theme
    spacing: 8
    padding: 6
    implicitHeight: Math.max(32, contentItem.implicitHeight + 12)
    focusPolicy: Qt.StrongFocus
    hoverEnabled: true
    opacity: enabled ? 1 : 0.6
    background: Rectangle {
        radius: control.theme.controlRadius
        color: control.hovered && control.enabled ? control.theme.raised : "transparent"
        border.width: control.visualFocus ? 2 : 1
        border.color: control.visualFocus ? control.theme.accent : "transparent"
    }
    Accessible.name: text
    indicator: Rectangle {
        x: control.leftPadding
        y: (control.height - height) / 2
        width: 16; height: 16; radius: 4
        color: control.checked ? control.theme.accent : control.theme.background
        border.color: control.activeFocus ? control.theme.text : control.checked ? control.theme.accent : control.theme.muted
        Icon { anchors.centerIn: parent; width: 12; height: 12; name: "check"; visible: control.checked; tint: control.theme.accentText }
    }
    contentItem: Text {
        textFormat: Text.PlainText
        text: control.text
        leftPadding: control.indicator.width + control.spacing
        color: control.enabled ? control.theme.text : control.theme.disabled
        font.family: control.theme.fontFamily
        font.pixelSize: control.theme.labelSize
        verticalAlignment: Text.AlignVCenter
        wrapMode: Text.WordWrap
    }
}
