import QtQuick
import QtQuick.Controls.Basic
Dialog {
    id: control
    required property Theme theme
    modal: true
    focus: true
    anchors.centerIn: parent
    padding: 20
    closePolicy: Popup.CloseOnEscape
    background: Rectangle { color: control.theme.surface; border.color: control.theme.border; radius: 12 }
    header: Text {
        text: control.title
        padding: 20; bottomPadding: 12
        color: control.theme.text
        font.family: control.theme.fontFamily
        font.pixelSize: control.theme.bodySize + 4
        font.weight: Font.DemiBold
    }
    Overlay.modal: Rectangle { color: "#99000000" }
}
