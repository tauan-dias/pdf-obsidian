import QtQuick

Item {
    id: ring
    required property Theme theme
    Rectangle {
        anchors.fill: parent
        anchors.margins: -4
        color: "transparent"
        radius: ring.theme.controlRadius + 4
        border.width: 2
        border.color: ring.theme.accent
        Rectangle {
            anchors.fill: parent
            anchors.margins: 2
            color: "transparent"
            radius: ring.theme.controlRadius + 2
            border.width: 2
            border.color: ring.theme.background
        }
    }
}
