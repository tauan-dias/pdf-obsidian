pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Dialog {
    id: control
    required property Theme theme
    enter: Transition {}
    exit: Transition {}
    property Item previousFocus: null
    property string tone: "neutral"
    modal: true
    focus: true
    anchors.centerIn: parent
    padding: theme.dialogPadding
    font.family: theme.fontFamily
    font.pixelSize: theme.bodySize
    closePolicy: Popup.CloseOnEscape
    onAboutToShow: previousFocus = control.parent && control.parent.Window.window ? control.parent.Window.window.activeFocusItem : null
    onClosed: {
        if (previousFocus && previousFocus.visible && previousFocus.enabled)
            previousFocus.forceActiveFocus(Qt.PopupFocusReason);
    }
    background: Rectangle { color: control.theme.surface; border.color: control.theme.border; radius: control.theme.panelRadius }
    header: RowLayout {
        spacing: 12
        Icon {
            Layout.leftMargin: control.theme.dialogPadding
            Layout.topMargin: control.theme.dialogPadding
            Layout.preferredWidth: 20; Layout.preferredHeight: 20
            visible: control.tone !== "neutral"
            name: control.tone === "danger" ? "error" : control.tone === "warning" ? "warning" : "info"
            tint: control.theme.text
        }
        Text {
            textFormat: Text.PlainText
            text: control.title
            Layout.fillWidth: true
            Layout.leftMargin: control.tone === "neutral" ? control.theme.dialogPadding : 0
            Layout.rightMargin: control.theme.dialogPadding
            Layout.topMargin: control.theme.dialogPadding
            color: control.theme.text
            font.family: control.theme.fontFamily
            font.pixelSize: control.theme.sectionSize
            font.weight: Font.Medium
            wrapMode: Text.WordWrap
        }
    }
    Overlay.modal: Rectangle { color: control.theme.overlay }
}
