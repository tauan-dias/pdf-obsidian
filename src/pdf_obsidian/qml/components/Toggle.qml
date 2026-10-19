import QtQuick
import QtQuick.Controls.Basic
CheckBox {
    id: control
    required property Theme theme
    spacing: 8
    padding: 6
    implicitHeight: Math.max(32, contentItem.implicitHeight + 12)
    focusPolicy: Qt.StrongFocus
    Accessible.name: text
    indicator: Rectangle {
        x: control.leftPadding
        y: (control.height - height) / 2
        width: 16; height: 16; radius: 4
        color: control.checked ? control.theme.accent : control.theme.background
        border.color: control.activeFocus ? control.theme.text : control.checked ? control.theme.accent : control.theme.muted
        Text { anchors.centerIn: parent; text: "✓"; visible: control.checked; color: control.theme.accentText; font.pixelSize: 13 }
    }
    contentItem: Text {
        text: control.text
        leftPadding: control.indicator.width + control.spacing
        color: control.enabled ? control.theme.text : control.theme.disabled
        font.family: control.theme.fontFamily
        font.pixelSize: control.theme.bodySize
        verticalAlignment: Text.AlignVCenter
    }
}
