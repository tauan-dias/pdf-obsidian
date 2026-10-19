import QtQuick

ActionButton {
    id: control
    property string iconName: ""
    property bool menuIndicator: false
    compact: true
    implicitWidth: Math.max(30, contents.implicitWidth + 16)
    implicitHeight: Math.max(30, theme.controlHeight)
    contentItem: Row {
        id: contents
        spacing: 6
        Icon {
            visible: control.iconName.length > 0
            width: visible ? 18 : 0; height: 18
            anchors.verticalCenter: parent.verticalCenter
            name: control.iconName
            tint: control.enabled ? control.theme.text : control.theme.disabled
        }
        Text {
            visible: control.text.length > 0
            text: control.text
            font.family: control.theme.fontFamily
            font.pixelSize: control.theme.bodySize
            color: control.enabled ? control.theme.text : control.theme.disabled
            anchors.verticalCenter: parent.verticalCenter
        }
        Icon {
            visible: control.menuIndicator
            width: visible ? 10 : 0; height: 10
            anchors.verticalCenter: parent.verticalCenter
            name: "chevron"
            tint: control.enabled ? control.theme.muted : control.theme.disabled
        }
    }
}
