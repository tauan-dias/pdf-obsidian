import QtQuick
import QtQuick.Controls.Basic

Button {
    id: control
    required property Theme theme
    property bool primary: false
    property bool destructive: false
    property bool compact: false
    property bool selected: false
    property bool outlined: !compact
    property string description: ""
    property string shortcutHint: ""
    property bool boldLabel: false
    property bool italicLabel: false
    implicitHeight: Math.max(theme.controlHeight, label.implicitHeight + 12)
    implicitWidth: Math.max(theme.controlHeight, label.implicitWidth + (destructive ? 44 : 20))
    padding: 6
    horizontalPadding: 10
    hoverEnabled: true
    focusPolicy: Qt.StrongFocus
    Accessible.name: description || text
    Accessible.description: shortcutHint
    Hint {
        theme: control.theme
        visible: control.hovered && control.enabled && control.description.length > 0
        text: control.description + (control.shortcutHint ? "  ·  " + control.shortcutHint : "")
    }
    contentItem: Text {
        textFormat: Text.PlainText
        id: label
        text: control.text
        font.family: control.theme.fontFamily
        font.pixelSize: control.theme.labelSize
        font.weight: control.primary || control.boldLabel ? Font.DemiBold : Font.Medium
        font.italic: control.italicLabel
        leftPadding: control.destructive ? 20 : 0
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        color: !control.enabled ? control.theme.disabled : control.primary ? control.theme.accentText : control.destructive ? control.theme.danger : control.theme.text
    }
    Icon {
        visible: control.destructive
        anchors.left: parent.left; anchors.leftMargin: 10
        anchors.verticalCenter: parent.verticalCenter
        width: 16; height: 16; name: "remove"
        tint: control.enabled ? control.theme.text : control.theme.disabled
    }
    background: Rectangle {
        radius: control.theme.controlRadius
        color: !control.enabled ? (control.compact ? "transparent" : control.theme.raised) :
            control.primary ? (control.down ? control.theme.accentPressed : control.hovered ? control.theme.accentHover : control.theme.accent) :
            control.destructive && (control.hovered || control.down) ? control.theme.dangerSurface :
            control.down ? control.theme.hover : control.hovered || control.selected ? control.theme.hover :
            control.compact ? "transparent" : control.theme.surface
        border.width: control.visualFocus ? 2 : 1
        border.color: control.activeFocus ? control.theme.accent :
            !control.enabled ? control.theme.border :
            (control.outlined && (control.hovered || control.down)) || control.selected ? control.theme.controlBorderHover :
            control.outlined ? control.theme.controlBorder : "transparent"
        opacity: control.enabled ? 1 : 0.65
        Behavior on color { ColorAnimation { duration: control.theme.motionDuration } }
        Behavior on border.color { ColorAnimation { duration: control.theme.motionDuration } }
        FocusRing {
            anchors.fill: parent
            theme: control.theme
            visible: control.primary && control.visualFocus && control.enabled
        }

    }
}
