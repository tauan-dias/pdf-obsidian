import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Button {
    id: control
    required property Theme theme
    property string description: ""
    property string iconName: "document"
    property string shortcutHint: ""
    property bool primary: false
    property bool showArrow: true
    readonly property color foreground: !enabled ? theme.disabled : primary ? theme.accentText : theme.text
    hoverEnabled: true
    activeFocusOnTab: true
    padding: theme.medium
    implicitHeight: Math.max(64, actionContent.implicitHeight + padding * 2)
    Accessible.name: text
    Accessible.description: description

    background: Rectangle {
        radius: control.theme.controlRadius
        color: !control.enabled ? control.theme.raised
             : control.primary ? (control.down ? control.theme.accentPressed
                                   : control.hovered ? control.theme.accentHover : control.theme.accent)
             : control.down ? control.theme.border
             : control.hovered ? control.theme.hover : control.theme.raised
        border.width: 1
        border.color: control.visualFocus ? control.theme.text
                    : control.primary ? "transparent" : control.theme.border
        Behavior on color { ColorAnimation { duration: 100 } }
        Rectangle {
            anchors.fill: parent
            anchors.margins: -3
            radius: parent.radius + 3
            color: "transparent"
            border.width: control.visualFocus ? 1 : 0
            border.color: control.theme.accent
        }
    }
    contentItem: RowLayout {
        id: actionContent
        spacing: control.theme.medium
        Icon {
            name: control.iconName
            tint: control.foreground
            Layout.preferredWidth: 22
            Layout.preferredHeight: 22
        }
        ColumnLayout {
            spacing: 3
            Layout.fillWidth: true
            Text {
                text: control.text
                color: control.foreground
                font.family: control.theme.fontFamily
                font.pixelSize: control.theme.bodySize
                font.weight: Font.DemiBold
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }
            Text {
                visible: control.description.length > 0
                text: control.description
                color: control.primary ? control.theme.accentText : control.theme.muted
                font.family: control.theme.fontFamily
                font.pixelSize: control.theme.captionSize
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }
        }
        Rectangle {
            visible: control.shortcutHint.length > 0 && control.width > 440
            implicitWidth: keyLabel.implicitWidth + 12
            implicitHeight: keyLabel.implicitHeight + 8
            radius: 4
            color: "transparent"
            border.color: control.primary ? "#663c2e29" : control.theme.border
            Text {
                id: keyLabel
                anchors.centerIn: parent
                text: control.shortcutHint
                color: control.foreground
                font.family: control.theme.fontFamily
                font.pixelSize: control.theme.captionSize
            }
        }
        Icon {
            visible: control.showArrow
            name: "arrow"
            tint: control.foreground
            Layout.preferredWidth: 18
            Layout.preferredHeight: 18
        }
    }
}
