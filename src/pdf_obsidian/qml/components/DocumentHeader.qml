import QtQuick
import QtQuick.Layouts

Rectangle {
    id: control
    required property Theme theme
    required property var backend
    signal documentsRequested()
    signal optionsRequested()
    readonly property bool narrow: width < headerActions.implicitWidth + 280 * theme.textScale + theme.medium * 2 + theme.large
    implicitHeight: contents.implicitHeight + theme.medium * 2
    color: theme.background
    TextMetrics {
        id: saveLabelMetrics
        text: "Salvar no vault…"
        font.family: control.theme.fontFamily
        font.pixelSize: control.theme.labelSize
        font.weight: Font.DemiBold
    }
    GridLayout {
        id: contents
        anchors.fill: parent
        anchors.margins: control.theme.medium
        columns: control.narrow ? 1 : 2
        columnSpacing: control.theme.large
        rowSpacing: 12
        RowLayout {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            spacing: 12
            Rectangle {
                Layout.preferredWidth: 36; Layout.preferredHeight: 36
                radius: 6; color: "transparent"; border.color: "transparent"
                Icon { anchors.centerIn: parent; width: 20; height: 20; tint: control.theme.accent }
            }
            ColumnLayout {
                Layout.fillWidth: true; Layout.minimumWidth: 0; spacing: 4
                Text {
                    textFormat: Text.PlainText
                    objectName: "documentTitle"
                    text: control.backend.title
                    Accessible.name: control.backend.documentPath
                    color: control.theme.text; font.pixelSize: control.theme.bodySize + 1
                    font.family: control.theme.fontFamily; font.weight: Font.DemiBold
                    elide: Text.ElideMiddle; Layout.fillWidth: true; Layout.minimumWidth: 0
                    HoverHandler { id: documentHover }
                    Hint { theme: control.theme; visible: documentHover.hovered; text: control.backend.documentPath }
                }
                StatusLabel {
                    objectName: "documentSaveStatus"
                    theme: control.theme
                    text: control.backend.worker.operation === "export" ? "Salvando no vault…" : control.backend.modified ? "Alterações não salvas" : "Salvo no vault"
                    tone: control.backend.worker.operation === "export" ? "neutral" : control.backend.modified ? "warning" : "success"
                }
            }
        }
        RowLayout {
            id: headerActions
            Layout.alignment: control.narrow ? Qt.AlignLeft : Qt.AlignRight
            spacing: 8
            ToolButton {
                theme: control.theme; text: "Abrir"; compact: false; menuIndicator: true; description: "Abrir PDF ou converter em lote"
                enabled: !control.backend.worker.busy
                onClicked: openMenu.open()
                SurfaceMenu {
                    id: openMenu; objectName: "openMenu"; theme: control.theme; y: parent.height + 4
                    SurfaceMenuItem { theme: control.theme; text: "Abrir PDF…    Ctrl+O"; onTriggered: control.backend.openPdf() }
                    SurfaceMenuItem { theme: control.theme; text: "Converter em lote…"; onTriggered: control.backend.newBatch() }
                }
            }
            ActionButton {
                objectName: "headerDocumentsAction"
                theme: control.theme; text: "Documentos (" + control.backend.documentCount + ")"
                enabled: !control.backend.worker.busy || control.backend.batchRunning
                onClicked: control.documentsRequested()
            }
            ActionButton {
                objectName: "saveAction"
                implicitWidth: Math.max(control.theme.controlHeight, saveLabelMetrics.advanceWidth + 20)
                theme: control.theme; text: control.backend.worker.operation === "export" ? "Salvando…" : "Salvar no vault…"
                primary: true; description: "Salvar o documento ativo no vault"; shortcutHint: "Ctrl+S"
                enabled: control.backend.editable && control.backend.worker.workerAvailable
                onClicked: control.backend.exportCurrent()
            }
            ToolButton {
                objectName: "headerOptionsAction"
                theme: control.theme; iconName: "more"; description: "Opções de exportação"
                enabled: !control.backend.worker.busy
                onClicked: control.optionsRequested()
            }
        }
    }
}
