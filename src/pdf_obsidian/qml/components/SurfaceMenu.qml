import QtQuick
import QtQuick.Controls.Basic

Menu {
    id: control
    required property Theme theme
    enter: Transition {}
    exit: Transition {}
    implicitWidth: theme.menuWidth * theme.textScale
    padding: 5
    margins: 8
    font.family: theme.fontFamily
    font.pixelSize: theme.bodySize
    background: Rectangle {
        color: control.theme.raised
        border.color: control.theme.border
        radius: control.theme.controlRadius
    }
}
