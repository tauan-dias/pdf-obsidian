import QtQuick
import QtQuick.Controls.Basic

Button {
    id: control
    required property Theme theme
    property bool primary: false
    property bool compact: false
    property bool selected: false
    property string description: ""
    property string shortcutHint: ""
    property bool boldLabel: false
    property bool italicLabel: false
    implicitHeight: Math.max(theme.controlHeight, label.implicitHeight + 12)
    implicitWidth: Math.max(theme.controlHeight, label.implicitWidth + 20)
    padding: 6
    horizontalPadding: 10
    hoverEnabled: true
    focusPolicy: Qt.StrongFocus
    Accessible.name: description || text
    Accessible.description: shortcutHint
    ToolTip.visible: hovered && enabled && description.length > 0
    ToolTip.delay: 650
    ToolTip.timeout: 4000
    ToolTip.text: description + (shortcutHint ? "  ·  " + shortcutHint : "")
    contentItem: Text {
        id: label
        text: control.text
        font.family: control.theme.fontFamily
        font.pixelSize: control.theme.bodySize
        font.weight: control.primary || control.boldLabel ? Font.DemiBold : Font.Normal
        font.italic: control.italicLabel
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        color: !control.enabled ? control.theme.disabled : control.primary ? control.theme.accentText : control.theme.text
    }
    background: Rectangle {
        radius: control.theme.controlRadius
        color: !control.enabled ? (control.compact ? "transparent" : control.theme.surface) :
            control.primary ? (control.down ? control.theme.accentPressed : control.hovered ? control.theme.accentHover : control.theme.accent) :
            control.down ? control.theme.hover : control.hovered || control.selected ? control.theme.raised :
            control.compact ? "transparent" : control.theme.surface
        border.width: 1
        border.color: control.activeFocus ? control.theme.accent :
            control.compact && !control.hovered && !control.selected ? "transparent" : control.theme.border
        opacity: control.enabled ? 1 : 0.65
        Behavior on color { ColorAnimation { duration: 100 } }
        Behavior on border.color { ColorAnimation { duration: 100 } }
        Rectangle {
            visible: control.selected
            anchors.bottom: parent.bottom; anchors.horizontalCenter: parent.horizontalCenter
            width: Math.min(22, parent.width - 16); height: 2
            radius: 1; color: control.theme.accent
        }
    }
}
