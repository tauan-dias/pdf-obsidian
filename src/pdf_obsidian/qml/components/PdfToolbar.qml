import QtQuick
import QtQuick.Layouts

ColumnLayout {
    id: control
    required property Theme theme
    required property var backend
    property bool cropMode: false
    signal cropToggled(bool checked)
    spacing: 8
    RowLayout {
        Layout.fillWidth: true
        Text { textFormat: Text.PlainText; text: "PDF original"; color: control.theme.muted; font.family: control.theme.fontFamily; font.pixelSize: control.theme.captionSize; Layout.fillWidth: true }
        Toggle { objectName: "cropAction"; theme: control.theme; text: "Recortar"; checked: control.cropMode; enabled: control.backend.editable && !control.backend.rendering; onToggled: control.cropToggled(checked) }
    }
    Flow {
        objectName: "pdfToolbar"
        Layout.fillWidth: true
        spacing: 8
        ToolGroup {
            theme: control.theme; objectName: "pageTools"
            ToolButton { theme: control.theme; iconName: "previous"; description: "Página anterior"; shortcutHint: "Alt+←"; enabled: control.backend.editable && control.backend.page > 1; onClicked: control.backend.goPage(control.backend.page - 1) }
            NumericField { id: pageField; objectName: "pageField"; theme: control.theme; width: 44; value: control.backend.page; minimum: 1; maximum: control.backend.pageCount; enabled: control.backend.editable; Accessible.name: "Página do PDF"; onCommitted: function(number) { control.backend.goPage(number); } }
            Text { textFormat: Text.PlainText; text: "/ " + control.backend.pageCount; color: control.theme.muted; font.family: control.theme.fontFamily; font.pixelSize: control.theme.captionSize; height: pageField.height; verticalAlignment: Text.AlignVCenter }
            ToolButton { theme: control.theme; iconName: "next"; description: "Próxima página"; shortcutHint: "Alt+→"; enabled: control.backend.editable && control.backend.page < control.backend.pageCount; onClicked: control.backend.goPage(control.backend.page + 1) }
        }
        ToolGroup {
            theme: control.theme; objectName: "zoomTools"
            ToolButton { theme: control.theme; iconName: "minus"; description: "Reduzir zoom"; enabled: control.backend.editable; onClicked: control.backend.setZoom(control.backend.zoom - 25) }
            NumericField { objectName: "zoomField"; theme: control.theme; width: 46; value: control.backend.zoom; minimum: 25; maximum: 300; enabled: control.backend.editable; Accessible.name: "Zoom percentual"; onCommitted: function(number) { control.backend.setZoom(number); } }
            Text { textFormat: Text.PlainText; text: "%"; color: control.theme.muted; font.family: control.theme.fontFamily; font.pixelSize: control.theme.captionSize; height: 32; verticalAlignment: Text.AlignVCenter }
            ToolButton { theme: control.theme; iconName: "plus"; description: "Ampliar zoom"; enabled: control.backend.editable; onClicked: control.backend.setZoom(control.backend.zoom + 25) }
            ToolButton {
                theme: control.theme; text: "Ajustar"; menuIndicator: true; description: "Ajustar visualização do PDF"
                enabled: control.backend.editable
                onClicked: fitMenu.open()
                SurfaceMenu {
                    id: fitMenu; objectName: "fitMenu"; theme: control.theme; y: parent.height + 4
                    SurfaceMenuItem { theme: control.theme; text: "À largura"; onTriggered: control.backend.fit("width") }
                    SurfaceMenuItem { theme: control.theme; text: "À página"; onTriggered: control.backend.fit("page") }
                }
            }
        }
    }
}
