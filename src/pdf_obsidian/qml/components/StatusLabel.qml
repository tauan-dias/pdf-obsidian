import QtQuick

Row {
    id: control
    required property Theme theme
    property string text: ""
    property string tone: "neutral"
    readonly property color foreground: tone === "success" ? theme.success : tone === "warning" ? theme.warning : tone === "danger" ? theme.danger : theme.muted
    spacing: 6
    Accessible.role: Accessible.StaticText
    Accessible.name: text
    Icon {
        width: 14; height: 14
        name: control.tone === "success" ? "success" : control.tone === "danger" ? "error" : control.tone === "warning" ? "warning" : "info"
        tint: control.foreground
        anchors.verticalCenter: parent.verticalCenter
    }
    Text {
        textFormat: Text.PlainText
        text: control.text
        color: control.foreground
        font.family: control.theme.fontFamily
        font.pixelSize: control.theme.captionSize
    }
}
