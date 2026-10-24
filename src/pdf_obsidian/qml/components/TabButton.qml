import QtQuick

ActionButton {
    id: control
    compact: true
    Accessible.role: Accessible.PageTab
    Accessible.selected: selected
    background: Rectangle {
        color: control.hovered && control.enabled ? control.theme.surface : "transparent"
        radius: control.theme.controlRadius
        border.width: 2
        border.color: control.visualFocus ? control.theme.accent : "transparent"
        Rectangle {
            visible: control.selected
            anchors.bottom: parent.bottom
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.leftMargin: 10
            anchors.rightMargin: 10
            height: 2
            color: control.theme.accent
        }
    }
}
