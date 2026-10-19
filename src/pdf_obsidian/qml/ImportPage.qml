pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "components"

FocusScope {
    id: window
    objectName: "importPage"
    property string fontFamily: "sans-serif"
    property real textScale: 1.0
    property bool demo: false
    property bool converting: false
    property bool cancelling: false
    property bool canImport: true
    property bool documentsEnabled: true
    property int documentCount: 0
    property string sourceName: ""
    property int progressCurrent: 0
    property int progressTotal: 0
    property string feedback: ""
    signal openPdfRequested()
    signal batchRequested()
    signal documentsRequested()
    signal cancelRequested()

    function focusPrimaryAction() {
        if (converting)
            cancelAction.forceActiveFocus(Qt.TabFocusReason);
        else
            openAction.forceActiveFocus(Qt.TabFocusReason);
    }

    Theme { id: tokens; fontFamily: window.fontFamily; textScale: window.textScale }
    Rectangle { anchors.fill: parent; color: tokens.background }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: Math.max(60, headerRow.implicitHeight + 24)
            color: tokens.background
            RowLayout {
                id: headerRow
                anchors.fill: parent
                anchors.leftMargin: tokens.large
                anchors.rightMargin: tokens.large
                spacing: 12
                Icon {
                    tint: tokens.accent
                    Layout.preferredWidth: 20
                    Layout.preferredHeight: 20
                }
                Text {
                    text: "PDF → Obsidian"
                    color: tokens.text
                    font.family: tokens.fontFamily
                    font.pixelSize: tokens.bodySize
                    font.weight: Font.DemiBold
                    Layout.fillWidth: true
                }
                Button {
                    id: documentsButton
                    objectName: "documentsAction"
                    visible: window.documentCount > 0
                    enabled: window.documentsEnabled
                    text: "Documentos (" + window.documentCount + ")"
                    activeFocusOnTab: true
                    onClicked: window.documentsRequested()
                    contentItem: Text {
                        text: documentsButton.text
                        color: documentsButton.enabled ? tokens.text : tokens.disabled
                        font.family: tokens.fontFamily
                        font.pixelSize: tokens.captionSize
                    }
                    background: Rectangle {
                        color: documentsButton.hovered ? tokens.hover : tokens.raised
                        radius: 6
                        border.color: documentsButton.visualFocus ? tokens.accent : tokens.border
                    }
                }
                Text {
                    visible: window.demo
                    text: "PROTÓTIPO QML"
                    color: tokens.muted
                    font.family: tokens.fontFamily
                    font.pixelSize: tokens.captionSize
                    font.letterSpacing: 1
                }
            }
            Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: tokens.border }
        }

        ScrollView {
            id: scroll
            implicitWidth: 0
            implicitHeight: 0
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            contentWidth: availableWidth
            contentHeight: page.height
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
            Item {
                id: page
                width: scroll.availableWidth
                height: Math.max(scroll.availableHeight, mainColumn.implicitHeight + 64)
                ColumnLayout {
                    id: mainColumn
                    width: Math.min(600, parent.width - 48)
                    anchors.centerIn: parent
                    spacing: tokens.large
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 12
                        Text {
                            text: window.converting ? "CONVERSÃO LOCAL" : "IMPORTAR DOCUMENTO"
                            color: tokens.accent
                            font.family: tokens.fontFamily
                            font.pixelSize: tokens.captionSize
                            font.weight: Font.DemiBold
                            font.letterSpacing: 1.5
                        }
                        Text {
                            text: window.converting ? (window.cancelling ? "Cancelando…" : "Preparando seu Markdown.") : "Do PDF ao seu vault."
                            color: tokens.text
                            font.family: tokens.fontFamily
                            font.pixelSize: tokens.titleSize
                            font.weight: Font.DemiBold
                            Layout.fillWidth: true
                            wrapMode: Text.WordWrap
                        }
                        Text {
                            text: window.converting ? "Aguarde a extração do conteúdo. Depois, revise antes de salvar no vault." : "Importe seus documentos, revise o Markdown e salve no Obsidian. Tudo no seu computador."
                            color: tokens.muted
                            font.family: tokens.fontFamily
                            font.pixelSize: tokens.bodySize
                            lineHeight: 1.4
                            Layout.fillWidth: true
                            wrapMode: Text.WordWrap
                        }
                    }
                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: cardContent.implicitHeight + tokens.medium * 2
                        radius: tokens.panelRadius
                        color: tokens.surface
                        border.color: tokens.border
                        ColumnLayout {
                            id: cardContent
                            anchors.fill: parent
                            anchors.margins: tokens.medium
                            spacing: 12
                            ImportAction {
                                id: openAction
                                objectName: "openPdfAction"
                                visible: !window.converting
                                enabled: window.canImport
                                theme: tokens
                                text: "Abrir PDF"
                                description: "Comece com um documento"
                                shortcutHint: "Ctrl O"
                                primary: true
                                Layout.fillWidth: true
                                onClicked: window.openPdfRequested()
                            }
                            ImportAction {
                                objectName: "batchAction"
                                visible: !window.converting
                                enabled: window.canImport
                                theme: tokens
                                text: "Converter em lote…"
                                description: "Vários documentos, uma revisão por vez"
                                iconName: "stack"
                                Layout.fillWidth: true
                                onClicked: window.batchRequested()
                            }
                            ColumnLayout {
                                visible: window.converting
                                Layout.fillWidth: true
                                spacing: tokens.medium
                                Text {
                                    objectName: "sourceLabel"
                                    text: window.sourceName
                                    color: tokens.text
                                    font.family: tokens.fontFamily
                                    font.pixelSize: tokens.bodySize
                                    Layout.fillWidth: true
                                    wrapMode: Text.Wrap
                                }
                                ProgressBar {
                                    id: progress
                                    objectName: "conversionProgress"
                                    Layout.fillWidth: true
                                    from: 0
                                    to: Math.max(1, window.progressTotal)
                                    value: Math.min(window.progressCurrent, Math.max(1, window.progressTotal))
                                    indeterminate: window.progressTotal <= 0
                                    Accessible.name: "Progresso da conversão"
                                    background: Rectangle {
                                        implicitHeight: 6
                                        color: tokens.border
                                        radius: 3
                                    }
                                    contentItem: Item {
                                        implicitHeight: 6
                                        clip: true
                                        Rectangle {
                                            id: indicator
                                            width: progress.indeterminate ? parent.width * 0.3 : parent.width * progress.visualPosition
                                            height: parent.height
                                            radius: 3
                                            color: tokens.accent
                                            x: 0
                                            NumberAnimation on x {
                                                from: -indicator.width
                                                to: progress.width
                                                duration: 1000
                                                loops: Animation.Infinite
                                                running: window.converting && progress.indeterminate
                                                onStopped: indicator.x = 0
                                            }
                                        }
                                    }
                                }
                                Text {
                                    objectName: "progressLabel"
                                    text: window.cancelling ? "Aguardando o processamento terminar com segurança…"
                                        : window.progressTotal > 0 ? Math.round(Math.min(1, window.progressCurrent / window.progressTotal) * 100) + "% concluído"
                                        : "Iniciando processamento…"
                                    color: tokens.muted
                                    font.family: tokens.fontFamily
                                    font.pixelSize: tokens.captionSize
                                    Layout.fillWidth: true
                                    wrapMode: Text.Wrap
                                }
                                ImportAction {
                                    id: cancelAction
                                    objectName: "cancelAction"
                                    theme: tokens
                                    text: window.cancelling ? "Cancelando…" : "Cancelar conversão"
                                    iconName: "close"
                                    showArrow: false
                                    enabled: !window.cancelling
                                    implicitHeight: 44 * window.textScale
                                    padding: 12
                                    Layout.fillWidth: true
                                    onClicked: window.cancelRequested()
                                }
                            }
                            Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: tokens.border }
                            RowLayout {
                                spacing: 8
                                Icon {
                                    name: "shield"
                                    tint: tokens.muted
                                    Layout.preferredWidth: 16
                                    Layout.preferredHeight: 16
                                }
                                Text {
                                    text: "Seus PDFs originais permanecem intactos."
                                    color: tokens.muted
                                    font.family: tokens.fontFamily
                                    font.pixelSize: tokens.captionSize
                                    Layout.fillWidth: true
                                    wrapMode: Text.WordWrap
                                }
                            }
                        }
                    }
                    Text {
                        objectName: "importFeedback"
                        visible: window.feedback.length > 0
                        text: window.feedback
                        color: tokens.muted
                        font.family: tokens.fontFamily
                        font.pixelSize: tokens.captionSize
                        lineHeight: 1.4
                        Layout.fillWidth: true
                        Layout.minimumHeight: 42 * window.textScale
                        wrapMode: Text.WordWrap
                        Accessible.role: Accessible.StaticText
                        Accessible.name: text
                    }
                }
            }
        }
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: Math.max(44, footer.implicitHeight + 24)
            color: tokens.background
            RowLayout {
                id: footer
                anchors.fill: parent
                anchors.leftMargin: tokens.large
                anchors.rightMargin: tokens.large
                Text {
                    text: "Local e offline"
                    color: tokens.muted
                    font.family: tokens.fontFamily
                    font.pixelSize: tokens.captionSize
                    Layout.fillWidth: true
                }
                Text {
                    text: window.demo ? "Estudo visual · sem conversão" : "PDFs originais preservados"
                    color: tokens.muted
                    font.family: tokens.fontFamily
                    font.pixelSize: tokens.captionSize
                }
            }
        }
    }
}
