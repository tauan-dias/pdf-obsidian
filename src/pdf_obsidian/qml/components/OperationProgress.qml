import QtQuick
import QtQuick.Controls.Basic

ProgressBar {
    id: control
    required property Theme theme
    objectName: "operationProgress"
    implicitHeight: 6
    Accessible.name: "Progresso da operação"
    background: Rectangle { color: control.theme.border; radius: 3; implicitHeight: 6 }
    contentItem: Item {
        implicitHeight: 6
        clip: true
        Rectangle {
            id: indicator
            width: control.indeterminate ? parent.width * 0.3 : parent.width * control.visualPosition
            height: parent.height
            radius: 3
            color: control.theme.accent
            NumberAnimation on x {
                from: -indicator.width
                to: control.width
                duration: 1100
                loops: Animation.Infinite
                running: control.visible && control.indeterminate && !control.theme.reducedMotion
                onStopped: indicator.x = 0
            }
        }
    }
}
