import QtQuick
import QtQuick.Controls.Basic
import "../../src/pdf_obsidian/qml" as Shared

ApplicationWindow {
    id: window
    objectName: "importPrototype"
    width: 1120
    height: 760
    minimumWidth: 560
    minimumHeight: 480
    visible: true
    title: "PDF → Obsidian · Estudo QML"
    property real textScale: 1.0
    property string feedback: "As ações desta prévia são demonstrativas. Nenhum arquivo será aberto."
    signal importRequested(string mode)
    Shortcut { sequence: "Ctrl+O"; onActivated: window.importRequested("single") }
    Shared.ImportPage {
        anchors.fill: parent
        demo: true
        fontFamily: window.font.family
        textScale: window.textScale
        feedback: window.feedback
        onOpenPdfRequested: window.importRequested("single")
        onBatchRequested: window.importRequested("batch")
    }
}
