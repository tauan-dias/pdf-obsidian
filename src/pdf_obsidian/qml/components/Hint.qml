import QtQuick
import QtQuick.Controls.Basic

ToolTip {
    id: control
    required property Theme theme
    enter: Transition {}
    exit: Transition {}
    delay: 650
    timeout: 5000
    padding: 8
    margins: 8
    width: Math.min(implicitWidth, 440 * theme.textScale, control.parent && control.parent.Window.window ? control.parent.Window.window.width - 32 : 440)
    font.family: theme.fontFamily
    font.pixelSize: theme.captionSize
    contentItem: Text {
        textFormat: Text.PlainText
        text: control.text
        color: control.theme.text
        font: control.font
        wrapMode: Text.Wrap
    }
    background: Rectangle {
        color: control.theme.raised
        border.color: control.theme.border
        radius: control.theme.controlRadius
    }
}
