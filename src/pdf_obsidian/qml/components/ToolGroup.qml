import QtQuick
import QtQuick.Controls.Basic

Control {
    id: control
    required property Theme theme
    default property alias tools: contents.data
    padding: 3
    implicitWidth: contents.implicitWidth + leftPadding + rightPadding
    implicitHeight: contents.implicitHeight + topPadding + bottomPadding
    contentItem: Row { id: contents; spacing: 2 }
    background: Rectangle {
        color: control.theme.surface
        border.color: control.enabled ? control.theme.controlBorder : control.theme.border
        radius: control.theme.controlRadius
    }
}
