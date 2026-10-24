import QtQuick
import QtQuick.Controls.Basic

ScrollBar {
    id: control
    required property Theme theme
    padding: 2
    implicitWidth: 10
    implicitHeight: 10
    minimumSize: 0.05
    x: horizontal || !parent ? 0 : parent.width - width
    y: vertical || !parent ? 0 : parent.height - height
    width: horizontal && parent ? parent.width : implicitWidth
    height: vertical && parent ? parent.height : implicitHeight
    contentItem: Rectangle {
        implicitWidth: 6; implicitHeight: 6
        radius: 3
        color: control.pressed ? control.theme.muted : control.hovered ? control.theme.disabled : control.theme.selection
        opacity: control.size < 0.999 ? 1 : 0
    }
    background: Rectangle { color: "transparent" }
}
