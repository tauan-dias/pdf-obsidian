import QtQuick

ActionButton {
    id: control
    property string iconName: ""
    property bool menuIndicator: false
    compact: true
    outlined: !compact
    implicitWidth: Math.max(theme.controlHeight, contents.implicitWidth + 16)
    implicitHeight: Math.max(theme.controlHeight, contents.implicitHeight + 12)
    contentItem: Row {
        id: contents
        spacing: 6
        Icon {
            visible: control.iconName.length > 0
            width: visible ? control.theme.iconSize : 0; height: control.theme.iconSize
            anchors.verticalCenter: parent.verticalCenter
            name: control.iconName
            tint: control.enabled ? control.theme.text : control.theme.disabled
        }
        Text {
            textFormat: Text.PlainText
            visible: control.text.length > 0
            text: control.text
            font.family: control.theme.fontFamily
            font.pixelSize: control.theme.labelSize
            color: control.enabled ? control.theme.text : control.theme.disabled
            anchors.verticalCenter: parent.verticalCenter
        }
        Icon {
            visible: control.menuIndicator
            width: visible ? 12 : 0; height: 12
            anchors.verticalCenter: parent.verticalCenter
            name: "chevron"
            tint: control.enabled ? control.theme.muted : control.theme.disabled
        }
    }
}
