pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "components"

ApplicationWindow {
    id: window
    objectName: "quickWindow"
    required property var backend
    width: 1300; height: 850
    minimumWidth: 800; minimumHeight: 600
    visible: true
    title: window.backend.hasDocument ? window.backend.title + " — PDF → Obsidian" : "PDF → Obsidian"
    color: theme.background
    property bool closingApproved: false
    property bool pdfVisible: true
    property bool follow: false
    property bool warningsExpanded: false
    property int tab: 0
    onTabChanged: window.backend.setPreviewVisible(tab === 1)
    property real pdfFraction: 0.4
    property bool restoring: false
    property int restoreSequence: 0
    property real pendingPreviewY: -1
    property bool cropMode: false
    property var messageQueue: []
    font: window.backend.nativeFont
    palette.window: theme.background
    palette.windowText: theme.text
    palette.base: theme.background
    palette.text: theme.text
    palette.button: theme.raised
    palette.buttonText: theme.text
    palette.highlight: theme.accent
    palette.highlightedText: theme.accentText
    Theme { id: theme; reducedMotion: window.backend.visualSettings.reducedMotion; fontFamily: window.font.family; textScale: (window.font.pixelSize > 0 ? window.font.pixelSize : window.font.pointSize * 96 / 72) / window.backend.baseFontPixels; onTextScaleChanged: window.backend.setTextScale(textScale) }
    onClosing: function(event) { event.accepted = closingApproved; if (!closingApproved) window.backend.requestClose(); }
    Component.onCompleted: { window.backend.attach(editor, preview); window.backend.setTextScale(theme.textScale); importPage.focusPrimaryAction(); }

    function saveView() {
        if (!restoring) window.backend.saveView({pdfVisible: pdfVisible, follow: follow, tab: tab,
            warningsExpanded: warningsExpanded, pdfFraction: pdfFraction,
            editorY: editorScroll.contentY, previewY: previewScroll.contentY,
            pdfCenterX: (pdfScroll.contentX + pdfScroll.width / 2) / Math.max(1, pdfScroll.contentWidth),
            pdfCenterY: (pdfScroll.contentY + pdfScroll.height / 2) / Math.max(1, pdfScroll.contentHeight)});
    }
    function changeDocument(key) { saveView(); window.backend.activate(key); documents.close(); }
    function format(command, value) { window.backend.format(command, value === undefined ? null : value); }
    function showMessage(title, message, kind) {
        if (messageDialog.visible && messageDialog.confirmation && kind === "info") {
            messageQueue.push({title: title, message: message, kind: kind});
            return;
        }
        messageDialog.title = title; messageText.text = message;
        messageDialog.kind = kind; messageDialog.confirmation = kind === "confirm"; messageDialog.open();
    }
    Connections {
        target: window.backend
        function onSnapshotRequested() { window.saveView(); }
        function onDocumentsRequested() { documents.open(); }
        function onBatchPreparationRequested() { preparation.open(); }
        function onCloseApproved() { window.closingApproved = true; window.close(); }
        function onDialogRequested(title, message, kind) {
            window.showMessage(title, message, kind);
        }
        function onLinkRequested(label) { linkLabel.text = label; linkDestination.text = ""; linkDialog.open(); (label.length > 0 ? linkDestination : linkLabel).forceActiveFocus(); }
        function onSelectionRequested(anchor, position) {
            // Assign the cursor explicitly, including a collapsed selection.
            editor.cursorPosition = position;
            editor.select(anchor, position);
            editor.forceActiveFocus();
        }
        function onViewRestored(state) {
            let sequence = ++window.restoreSequence;
            window.pendingPreviewY = state.previewY || 0;
            window.restoring = true;
            window.pdfVisible = state.pdfVisible === undefined ? true : state.pdfVisible;
            window.follow = state.follow || false; window.tab = state.tab || 0;
            window.warningsExpanded = state.warningsExpanded || false;
            window.pdfFraction = state.pdfFraction || 0.4;
            pdfPanel.SplitView.preferredWidth = split.width * window.pdfFraction;
            Qt.callLater(function() {
                if (sequence !== window.restoreSequence) return;
                editorScroll.contentY = state.editorY || 0; previewScroll.contentY = state.previewY || 0;
                pdfScroll.restoreX = state.pdfCenterX === undefined ? -1 : state.pdfCenterX;
                pdfScroll.restoreY = state.pdfCenterY === undefined ? -1 : state.pdfCenterY;
                pdfScroll.restorePending = true;
                window.restoring = false;
            });
        }
        function onPreviewReplacing() {
            if (window.pendingPreviewY < 0) window.pendingPreviewY = previewScroll.contentY;
        }
        function onPreviewRebuilt() {
            let sequence = window.restoreSequence;
            let targetY = window.pendingPreviewY;
            Qt.callLater(function() {
                if (sequence !== window.restoreSequence) return;
                if (targetY >= 0) previewScroll.contentY = Math.max(0, Math.min(targetY, previewScroll.contentHeight - previewScroll.height));
                window.pendingPreviewY = -1;
                if (window.follow) window.backend.follow_page();
            });
        }
        function onPdfReplacing() {
            if (!pdfScroll.restorePending && pdfImage.status === Image.Ready) {
                pdfScroll.restoreX = (pdfScroll.contentX + pdfScroll.width / 2) / Math.max(1, pdfScroll.contentWidth);
                pdfScroll.restoreY = (pdfScroll.contentY + pdfScroll.height / 2) / Math.max(1, pdfScroll.contentHeight);
            }
        }
        function onFollowRequested(editorPosition, previewPosition) {
            if (!window.follow) return;
            let e = editor.positionToRectangle(editorPosition);
            editorScroll.contentY = Math.max(0, Math.min(e.y, editorScroll.contentHeight - editorScroll.height));
            let p = preview.positionToRectangle(previewPosition);
            previewScroll.contentY = Math.max(0, Math.min(p.y, previewScroll.contentHeight - previewScroll.height));
        }
    }
    Shortcut { sequence: "Ctrl+O"; enabled: !window.backend.worker.busy; onActivated: window.backend.openPdf() }
    Shortcut { sequence: "Ctrl+S"; enabled: window.backend.editable; onActivated: window.backend.exportCurrent() }
    Shortcut { sequence: "Alt+Left"; enabled: window.backend.editable; onActivated: window.backend.goPage(window.backend.page - 1) }
    Shortcut { sequence: "Alt+Right"; enabled: window.backend.editable; onActivated: window.backend.goPage(window.backend.page + 1) }
    Shortcut { sequence: "Ctrl+B"; enabled: window.backend.editable && editor.activeFocus; onActivated: window.format("bold") }
    Shortcut { sequence: "Ctrl+I"; enabled: window.backend.editable && editor.activeFocus; onActivated: window.format("italic") }
    Shortcut { sequence: "Ctrl+K"; enabled: window.backend.editable && editor.activeFocus; onActivated: window.format("link") }
    Shortcut { sequence: "Ctrl+Z"; enabled: window.backend.editable && (window.tab === 1 || !editor.activeFocus); onActivated: window.backend.undo() }
    Shortcut { sequences: ["Ctrl+Shift+Z", "Ctrl+Y"]; enabled: window.backend.editable && (window.tab === 1 || !editor.activeFocus); onActivated: window.backend.redo() }

    ImportPage {
        id: importPage
        anchors.fill: parent
        visible: !window.backend.hasDocument || window.backend.worker.operation === "convert"
        ocrMode: window.backend.worker.ocrMode
        ocrStatus: window.backend.worker.recognitionStatus
        conversionStage: window.backend.worker.conversionStage
        onOcrModeRequested: function(enabled) { window.backend.worker.setOcrMode(enabled ? "auto" : "off"); }
        fontFamily: theme.fontFamily; textScale: theme.textScale
        reducedMotion: theme.reducedMotion
        converting: window.backend.worker.operation === "convert"
        cancelling: window.backend.worker.cancellationRequested
        canImport: window.backend.worker.workerAvailable && !window.backend.worker.busy
        documentsEnabled: !window.backend.worker.busy || window.backend.batchRunning
        documentCount: window.backend.documentCount
        sourceName: window.backend.worker.sourceName
        progressCurrent: window.backend.worker.progressCurrent; progressTotal: window.backend.worker.progressTotal
        feedback: window.backend.message
        onOpenPdfRequested: window.backend.openPdf()
        onBatchRequested: window.backend.newBatch()
        onDocumentsRequested: documents.open()
        onCancelRequested: window.backend.worker.cancelConversion()
    }
    ColumnLayout {
        anchors.fill: parent
        spacing: 0
        visible: window.backend.hasDocument && window.backend.worker.operation !== "convert"
        DocumentHeader {
            theme: theme; backend: window.backend
            Layout.fillWidth: true
            onDocumentsRequested: documents.open()
            onOptionsRequested: options.open()
        }
        Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: theme.border }
        Flow {
            Layout.fillWidth: true; Layout.leftMargin: 12; Layout.rightMargin: 12; Layout.topMargin: 6; Layout.bottomMargin: 6; spacing: 8
            ToolButton { theme: theme; text: window.pdfVisible ? "Ocultar PDF" : "Mostrar PDF"; enabled: !window.backend.batchRunning; onClicked: { window.pdfVisible = !window.pdfVisible; window.saveView(); } }
            Toggle { theme: theme; text: "Acompanhar página"; checked: window.follow; enabled: !window.backend.batchRunning; onToggled: { window.follow = checked; if (checked) window.backend.follow_page(); window.saveView(); } }
            ToolButton { theme: theme; iconName: "image"; text: "Imagens filtradas (" + window.backend.filteredCount + ")"; visible: window.backend.filteredCount > 0; enabled: window.backend.editable; onClicked: { window.backend.openFiltered(); filteredDialog.open(); } }
            ToolButton { theme: theme; iconName: "warning"; text: "Avisos (" + window.backend.warnings.length + ")"; selected: window.warningsExpanded; menuIndicator: true; expanded: window.warningsExpanded; visible: window.backend.warnings.length > 0; onClicked: { window.warningsExpanded = !window.warningsExpanded; window.saveView(); } }
        }
        Rectangle {
            visible: window.warningsExpanded && window.backend.warnings.length > 0
            Layout.fillWidth: true; Layout.preferredHeight: Math.min(110, warningsList.contentHeight + 12)
            color: theme.warningSurface
            ListView {
                id: warningsList; objectName: "warningsList"; anchors.fill: parent; anchors.margins: 6; clip: true; model: window.backend.warnings
                ScrollBar.vertical: SurfaceScrollBar { theme: theme }
                delegate: ItemDelegate {
                    id: warningRow
                    required property var modelData
                    objectName: "warning-" + modelData.page
                    enabled: modelData.page > 0
                    width: ListView.view.width; height: Math.max(34, warningText.implicitHeight + 12)
                    contentItem: Text { textFormat: Text.PlainText; id: warningText; text: (warningRow.modelData.page > 0 ? "Página " + warningRow.modelData.page : "Geral") + " · " + warningRow.modelData.message; color: theme.warning; wrapMode: Text.Wrap; font.pixelSize: theme.captionSize }
                    background: Rectangle { color: warningRow.hovered ? theme.raised : "transparent"; border.color: warningRow.visualFocus ? theme.accent : "transparent"; radius: 6 }
                    Accessible.name: warningText.text
                    Accessible.role: modelData.page > 0 ? Accessible.Button : Accessible.StaticText
                    onClicked: if (modelData.page > 0) { window.pdfVisible = true; window.backend.goPage(modelData.page); }
                }
            }
        }
        SplitView {
            id: split
            Layout.fillWidth: true; Layout.fillHeight: true
            orientation: Qt.Horizontal
            onWidthChanged: pdfPanel.SplitView.preferredWidth = width * window.pdfFraction
            handle: Rectangle {
                objectName: "comparisonDivider"
                implicitWidth: 6
                activeFocusOnTab: window.pdfVisible
                color: activeFocus ? theme.accent : SplitHandle.hovered || SplitHandle.pressed ? theme.border : theme.background
                Accessible.role: Accessible.Splitter
                Accessible.name: "Ajustar divisão entre PDF e editor"
                Accessible.description: "Use as setas esquerda e direita para ajustar os painéis."
                Keys.onLeftPressed: { pdfPanel.SplitView.preferredWidth = Math.max(275, pdfPanel.width - split.width * 0.05); Qt.callLater(window.saveView); }
                Keys.onRightPressed: { pdfPanel.SplitView.preferredWidth = Math.min(split.width - 366, pdfPanel.width + split.width * 0.05); Qt.callLater(window.saveView); }
            }
            Rectangle {
                id: pdfPanel
                objectName: "pdfPanel"
                visible: window.pdfVisible
                SplitView.preferredWidth: split.width * window.pdfFraction
                SplitView.minimumWidth: 275
                color: theme.canvas
                onWidthChanged: { if (!window.restoring && window.pdfVisible && split.width > 0) window.pdfFraction = width / split.width; }
                ColumnLayout {
                    anchors.fill: parent; spacing: 0
                    PdfToolbar {
                        theme: theme; backend: window.backend
                        Layout.fillWidth: true; Layout.margins: 10
                        cropMode: window.cropMode
                        onCropToggled: function(checked) { window.cropMode = checked; }
                    }
                    Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: theme.border }
                    Flickable {
                        id: pdfScroll
                        objectName: "pdfScroll"
                        Layout.fillWidth: true; Layout.fillHeight: true
                        clip: true; boundsBehavior: Flickable.StopAtBounds
                        contentWidth: Math.max(width, pdfImage.width + 24)
                        contentHeight: Math.max(height, pdfImage.height + 24)
                        property real restoreX: -1
                        property real restoreY: -1
                        property bool restorePending: true
                        onWidthChanged: window.backend.viewport(width, height)
                        onHeightChanged: window.backend.viewport(width, height)
                        ScrollBar.vertical: SurfaceScrollBar { theme: theme }
                        ScrollBar.horizontal: SurfaceScrollBar { theme: theme }
                        Image {
                            id: pdfImage
                            objectName: "pdfImage"
                            x: Math.max(12, (pdfScroll.width - width) / 2); y: 12
                            source: window.backend.pdfImage
                            cache: false; asynchronous: false
                            width: implicitWidth; height: implicitHeight
                            onStatusChanged: if (status === Image.Ready) {
                                pdfScroll.contentX = Math.max(0, Math.min(pdfScroll.restoreX * pdfScroll.contentWidth - pdfScroll.width / 2, Math.max(0, pdfScroll.contentWidth - pdfScroll.width)));
                                pdfScroll.contentY = Math.max(0, Math.min(pdfScroll.restoreY * pdfScroll.contentHeight - pdfScroll.height / 2, Math.max(0, pdfScroll.contentHeight - pdfScroll.height)));
                                pdfScroll.restorePending = false;
                            }
                            MouseArea {
                                id: cropArea
                                anchors.fill: parent
                                enabled: window.cropMode && window.backend.editable && !window.backend.rendering
                                cursorShape: Qt.CrossCursor
                                preventStealing: true
                                property real startX: 0; property real startY: 0
                                property real endX: 0; property real endY: 0
                                onPressed: function(mouse) { startX = endX = mouse.x; startY = endY = mouse.y; }
                                onPositionChanged: function(mouse) { endX = Math.max(0, Math.min(width, mouse.x)); endY = Math.max(0, Math.min(height, mouse.y)); }
                                onReleased: {
                                    if (Math.abs(endX - startX) >= 5 && Math.abs(endY - startY) >= 5)
                                        window.backend.crop(Math.min(startX, endX) / width, Math.min(startY, endY) / height, Math.abs(endX - startX) / width, Math.abs(endY - startY) / height);
                                    window.cropMode = false;
                                }
                                Rectangle {
                                    visible: cropArea.pressed
                                    x: Math.min(cropArea.startX, cropArea.endX); y: Math.min(cropArea.startY, cropArea.endY)
                                    width: Math.abs(cropArea.endX - cropArea.startX); height: Math.abs(cropArea.endY - cropArea.startY)
                                    color: theme.imageSelection; border.color: theme.accent
                                }
                            }
                        }
                        Keys.onPressed: function(event) {
                            if (event.modifiers & Qt.ControlModifier) {
                                if (event.key === Qt.Key_Plus || event.key === Qt.Key_Equal) { window.backend.setZoom(window.backend.zoom + 25); event.accepted = true; }
                                if (event.key === Qt.Key_Minus) { window.backend.setZoom(window.backend.zoom - 25); event.accepted = true; }
                                if (event.key === Qt.Key_0) { window.backend.fit("width"); event.accepted = true; }
                            }
                        }
                        TapHandler { onTapped: pdfScroll.forceActiveFocus() }
                    }
                    Text { textFormat: Text.PlainText; Layout.fillWidth: true; Layout.margins: 8; text: window.backend.rendering ? "Renderizando página…" : window.cropMode ? "Arraste sobre o PDF para inserir um recorte." : "PDF original · somente leitura"; color: theme.muted; font.pixelSize: theme.captionSize; wrapMode: Text.Wrap }
                }
            }
            Rectangle {
                SplitView.fillWidth: true; SplitView.minimumWidth: 360
                color: theme.background
                ColumnLayout {
                    anchors.fill: parent; spacing: 0
                    RowLayout {
                        Layout.fillWidth: true; Layout.leftMargin: 8; Layout.rightMargin: 8; Layout.topMargin: 4; Layout.bottomMargin: 4; spacing: 6
                        TabButton { id: markdownTab; objectName: "markdownTab"; theme: theme; text: "Markdown"; compact: true; Accessible.role: Accessible.PageTab; Accessible.selected: selected; Keys.onRightPressed: { window.tab = 1; previewTab.forceActiveFocus(); window.saveView(); } selected: window.tab === 0; onClicked: { window.tab = 0; editor.forceActiveFocus(); window.saveView(); } }
                        TabButton { id: previewTab; objectName: "previewTab"; theme: theme; text: "Prévia"; compact: true; Accessible.role: Accessible.PageTab; Accessible.selected: selected; Keys.onLeftPressed: { window.tab = 0; markdownTab.forceActiveFocus(); window.saveView(); } selected: window.tab === 1; onClicked: { window.tab = 1; preview.forceActiveFocus(); window.saveView(); } }
                        Item { Layout.fillWidth: true }
                        ToolGroup { theme: theme
                        ToolButton { theme: theme; objectName: "undoAction"; iconName: "undo"; description: "Desfazer"; shortcutHint: "Ctrl+Z"; Accessible.name: "Desfazer"; enabled: window.backend.canUndo; onClicked: window.backend.undo() }
                        ToolButton { theme: theme; objectName: "redoAction"; iconName: "redo"; description: "Refazer"; shortcutHint: "Ctrl+Shift+Z"; Accessible.name: "Refazer"; enabled: window.backend.canRedo; onClicked: window.backend.redo() }
                        }
                    }
                    Flow {
                        visible: window.tab === 0
                        objectName: "editorToolbar"
                        Layout.fillWidth: true; Layout.leftMargin: 8; Layout.rightMargin: 8; Layout.bottomMargin: 8; spacing: 8
                        enabled: window.backend.editable
                        ToolGroup {
                            theme: theme
                            ToolButton { theme: theme; objectName: "styleAction"; text: "Estilo"; description: "Estilo do parágrafo"; menuIndicator: true; onClicked: styleMenu.open()
                                SurfaceMenu { theme: theme; id: styleMenu; objectName: "styleMenu"; y: parent.height
                                    SurfaceMenuItem { theme: theme; text: "Parágrafo"; onTriggered: window.format("heading", 0) }
                                    Repeater { model: 6; SurfaceMenuItem { theme: theme; required property int index; text: "Título " + (index + 1); onTriggered: window.format("heading", index + 1) } }
                                }
                            }
                        }
                        ToolGroup {
                            theme: theme; objectName: "textTools"
                            ToolButton { theme: theme; objectName: "boldAction"; iconName: "bold"; description: "Negrito"; shortcutHint: "Ctrl+B"; onClicked: window.format("bold") }
                            ToolButton { theme: theme; objectName: "italicAction"; iconName: "italic"; description: "Itálico"; shortcutHint: "Ctrl+I"; onClicked: window.format("italic") }
                            ToolButton { theme: theme; objectName: "linkAction"; iconName: "link"; description: "Inserir link"; shortcutHint: "Ctrl+K"; onClicked: window.format("link") }
                        }
                        ToolGroup {
                            theme: theme; objectName: "paragraphTools"
                            ToolButton { theme: theme; objectName: "bulletAction"; iconName: "bullet"; description: "Lista com marcadores"; shortcutHint: ""; onClicked: window.format("bullet") }
                            ToolButton { theme: theme; objectName: "orderedAction"; iconName: "ordered"; description: "Lista numerada"; shortcutHint: ""; onClicked: window.format("ordered") }
                            ToolButton { theme: theme; objectName: "quoteAction"; iconName: "quote"; description: "Citação"; shortcutHint: ""; onClicked: window.format("quote") }
                            ToolButton { theme: theme; objectName: "alignAction"; iconName: "align"; description: "Alinhamento do parágrafo"; menuIndicator: true; onClicked: alignMenu.open()
                                SurfaceMenu { theme: theme; id: alignMenu; objectName: "alignMenu"; y: parent.height
                                    SurfaceMenuItem { theme: theme; text: "Esquerda"; onTriggered: window.format("align", "left") }
                                    SurfaceMenuItem { theme: theme; text: "Centro"; onTriggered: window.format("align", "center") }
                                    SurfaceMenuItem { theme: theme; text: "Direita"; onTriggered: window.format("align", "right") }
                                    SurfaceMenuItem { theme: theme; text: "Justificado"; onTriggered: window.format("align", "justify") }
                                }
                            }
                        }
                    }
                    Flow {
                        visible: window.tab === 1
                        Layout.fillWidth: true; Layout.leftMargin: 8; Layout.rightMargin: 8; Layout.bottomMargin: 4; spacing: 4
                        Toggle { objectName: "selectImagesAction"; theme: theme; text: "Selecionar imagens"; checked: window.backend.selectionMode; enabled: window.backend.previewReady; onToggled: window.backend.setSelectionMode(checked) }
                        Text { textFormat: Text.PlainText; visible: window.backend.selectionMode; text: window.backend.selectedImages + " selecionadas"; color: theme.muted; font.pixelSize: theme.captionSize; height: 32; verticalAlignment: Text.AlignVCenter }
                        ActionButton { theme: theme; objectName: "removeImagesAction"; visible: window.backend.selectionMode; text: "Remover selecionadas"; destructive: true; description: "Remover as imagens selecionadas; use Desfazer para restaurar"; enabled: window.backend.previewReady && window.backend.selectedImages > 0; onClicked: window.backend.removeImages() }
                        ActionButton { theme: theme; visible: window.backend.selectionMode; text: "Limpar seleção"; compact: true; enabled: window.backend.selectedImages > 0; onClicked: window.backend.clearImages() }
                    }
                    Text {
                        textFormat: Text.PlainText
                        Layout.fillWidth: true; Layout.leftMargin: 12; Layout.rightMargin: 12; Layout.bottomMargin: 8
                        visible: window.tab === 1 && window.backend.selectionMode
                        text: "Clique nas imagens para selecionar. A remoção pode ser desfeita."
                        color: theme.muted; font.pixelSize: theme.captionSize; wrapMode: Text.WordWrap
                    }
                    Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: theme.border }
                    Item {
                        Layout.fillWidth: true; Layout.fillHeight: true
                        Flickable {
                            id: editorScroll
                            anchors.fill: parent; visible: window.tab === 0; clip: true
                            contentWidth: width; contentHeight: Math.max(height, editor.height + height - 60)
                            boundsBehavior: Flickable.StopAtBounds
                            ScrollBar.vertical: SurfaceScrollBar { theme: theme }
                            TextEdit {
                                id: editor; objectName: "markdownEditor"
                                x: (parent.width - width) / 2; y: 28
                                width: Math.max(1, Math.min(theme.readingWidth, parent.width - theme.readingInset * 2))
                                height: Math.max(contentHeight, editorScroll.height - 28)
                                textFormat: TextEdit.PlainText
                                wrapMode: TextEdit.Wrap
                                color: theme.text; selectionColor: theme.selection; selectedTextColor: theme.text
                                font.pixelSize: theme.editorSize; font.family: window.backend.editorFontFamily
                                selectByMouse: true; persistentSelection: true
                                readOnly: !window.backend.editable
                                Accessible.name: "Editor Markdown"
                                TapHandler { acceptedButtons: Qt.RightButton; onTapped: editorMenu.popup() }
                                SurfaceMenu { theme: theme;
                                    id: editorMenu; objectName: "editorMenu"
                                    SurfaceMenuItem { theme: theme; text: "Desfazer"; enabled: window.backend.canUndo; onTriggered: window.backend.undo() }
                                    SurfaceMenuItem { theme: theme; text: "Refazer"; enabled: window.backend.canRedo; onTriggered: window.backend.redo() }
                                    SurfaceMenuSeparator { theme: theme }
                                    SurfaceMenuItem { theme: theme; text: "Recortar"; enabled: window.backend.editable && editor.selectionStart !== editor.selectionEnd; onTriggered: editor.cut() }
                                    SurfaceMenuItem { theme: theme; text: "Copiar"; enabled: editor.selectionStart !== editor.selectionEnd; onTriggered: editor.copy() }
                                    SurfaceMenuItem { theme: theme; text: "Colar"; enabled: window.backend.editable && editor.canPaste; onTriggered: editor.paste() }
                                    SurfaceMenuItem { theme: theme; text: "Selecionar tudo"; onTriggered: editor.selectAll() }
                                }
                                onCursorRectangleChanged: if (activeFocus && !window.restoring) {
                                    if (cursorRectangle.y + 30 > editorScroll.contentY + editorScroll.height) editorScroll.contentY = cursorRectangle.y + 30 - editorScroll.height;
                                    else if (cursorRectangle.y < editorScroll.contentY) editorScroll.contentY = cursorRectangle.y;
                                }
                            }
                        }
                        Column {
                            anchors.centerIn: parent
                            z: 1; spacing: 12
                            width: Math.min(220, parent.width - 48)
                            visible: window.tab === 1 && window.backend.previewPending
                            OperationProgress { theme: theme; width: parent.width; indeterminate: true; Accessible.name: "Preparando prévia" }
                            Text { textFormat: Text.PlainText; width: parent.width; horizontalAlignment: Text.AlignHCenter; text: "Preparando prévia…"; color: theme.muted; font.pixelSize: theme.captionSize }
                        }
                        Flickable {
                            id: previewScroll
                            anchors.fill: parent; visible: window.tab === 1 && !window.backend.previewPending; clip: true
                            contentWidth: width; contentHeight: Math.max(height, preview.height + height - 60)
                            boundsBehavior: Flickable.StopAtBounds
                            ScrollBar.vertical: SurfaceScrollBar { theme: theme }
                            TextEdit {
                                id: preview; objectName: "markdownPreview"
                                x: (parent.width - width) / 2; y: 28
                                width: Math.max(1, Math.min(theme.readingWidth, parent.width - theme.readingInset * 2))
                                height: contentHeight
                                onWidthChanged: window.backend.previewResized()
                                textFormat: TextEdit.RichText
                                wrapMode: TextEdit.Wrap
                                readOnly: true; selectByMouse: true; persistentSelection: true
                                color: theme.text; selectionColor: theme.selection; selectedTextColor: theme.text
                                font.pixelSize: theme.editorSize
                                Accessible.name: "Prévia do Markdown"
                                TapHandler { acceptedButtons: Qt.RightButton; onTapped: previewMenu.popup() }
                                SurfaceMenu { theme: theme;
                                    id: previewMenu; objectName: "previewMenu"
                                    SurfaceMenuItem { theme: theme; text: "Copiar"; enabled: preview.selectionStart !== preview.selectionEnd; onTriggered: preview.copy() }
                                    SurfaceMenuItem { theme: theme; text: "Selecionar tudo"; onTriggered: preview.selectAll() }
                                }
                                Repeater {
                                    model: window.backend.imageModel
                                    delegate: Rectangle {
                                        id: imageOverlay
                                        required property int position
                                        required property bool selected
                                        objectName: "previewImage-" + position
                                        readonly property bool validPosition: position >= 0 && position + 1 <= preview.length
                                        property rect targetRect: { let layoutWidth = preview.width; let layoutHeight = preview.contentHeight; return validPosition ? preview.positionToRectangle(position) : Qt.rect(0, 0, 0, 0); }
                                        property rect endRect: { let layoutWidth = preview.width; let layoutHeight = preview.contentHeight; return validPosition ? preview.positionToRectangle(position + 1) : Qt.rect(0, 0, 0, 0); }
                                        x: targetRect.x; y: targetRect.y
                                        width: Math.max(16, endRect.x - targetRect.x)
                                        height: targetRect.height
                                        visible: validPosition && window.backend.selectionMode && window.backend.previewReady
                                        color: imageOverlay.selected ? theme.imageSelection : "transparent"
                                        border.width: imageOverlay.selected || imageOverlay.activeFocus ? 2 : 0
                                        border.color: imageOverlay.activeFocus ? theme.text : theme.accent
                                        Accessible.role: Accessible.CheckBox
                                        Accessible.name: "Imagem na prévia"
                                        Accessible.checkable: true; Accessible.checked: imageOverlay.selected
                                        activeFocusOnTab: true
                                        Keys.onSpacePressed: window.backend.toggleImage(imageOverlay.position)
                                        TapHandler { onTapped: window.backend.toggleImage(imageOverlay.position) }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        Rectangle {
            Layout.fillWidth: true; implicitHeight: statusText.implicitHeight + 16
            color: theme.surface
            Text { textFormat: Text.PlainText; id: statusText; anchors.fill: parent; anchors.margins: 8; text: window.backend.message || "Local e offline · PDFs originais preservados"; color: theme.muted; font.pixelSize: theme.captionSize; elide: Text.ElideRight
                HoverHandler { id: statusHover }
                Hint { theme: theme; visible: statusHover.hovered && statusText.truncated; text: statusText.text }
                Accessible.name: text
            }
        }
    }

    SurfaceDialog {
        id: preparation; objectName: "preparation"; theme: theme; title: "Preparar conversão em lote"
        footer: DialogActions {
            theme: theme
            ActionButton { theme: theme; text: "Converter " + window.backend.pendingCount + " documento(s)"; primary: true; enabled: window.backend.pendingCount > 0; onClicked: { preparation.close(); window.backend.beginBatch(); } }
            ActionButton { theme: theme; text: "Cancelar"; onClicked: preparation.close() }
            ActionButton { theme: theme; text: "Adicionar PDFs…"; onClicked: window.backend.addPending() }
        }
        width: Math.min(window.width - 48, 700); height: Math.min(window.height - 48, 500)
        ColumnLayout {
            anchors.fill: parent; spacing: 12
            Toggle { objectName: "batchOcrModeAction"; theme: theme; text: "OCR automático · texto, tabelas e fórmulas"; checked: window.backend.worker.ocrMode === "auto"; enabled: !window.backend.worker.busy; onToggled: window.backend.worker.setOcrMode(checked ? "auto" : "off"); Layout.fillWidth: true }
            Text { textFormat: Text.PlainText; text: window.backend.worker.recognitionStatus; color: theme.muted; font.pixelSize: theme.captionSize; wrapMode: Text.WordWrap; Layout.fillWidth: true }
            Text { textFormat: Text.PlainText; text: window.backend.pendingCount + " documento(s). Remova os arquivos que não deseja converter."; color: theme.muted; font.pixelSize: theme.bodySize; wrapMode: Text.Wrap; Layout.fillWidth: true }
            ListView {
                id: pendingList
                Layout.fillWidth: true; Layout.fillHeight: true; clip: true; model: window.backend.pendingModel; spacing: 8
                Text { textFormat: Text.PlainText; anchors.centerIn: parent; width: parent.width - 32; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap; text: "Adicione PDFs para preparar a conversão."; visible: pendingList.count === 0; color: theme.muted; font.pixelSize: theme.bodySize }
                ScrollBar.vertical: SurfaceScrollBar { theme: theme }
                delegate: RowLayout {
                    id: pendingRow
                    required property string key
                    required property string name
                    width: ListView.view.width - (pendingList.ScrollBar.vertical.size < 0.999 ? 14 : 0)
                    Text { textFormat: Text.PlainText; text: pendingRow.name; color: theme.text; font.pixelSize: theme.bodySize; elide: Text.ElideMiddle; Layout.fillWidth: true }
                    ActionButton { theme: theme; text: "Remover"; compact: true; destructive: true; onClicked: window.backend.removePending(pendingRow.key) }
                }
            }
        }
    }
    SurfaceDialog {
        id: documents; objectName: "documents"; theme: theme; title: "Documentos da sessão"
        footer: DialogActions {
            theme: theme
            Keys.onEscapePressed: if (window.backend.batchRunning) window.backend.cancelBatch()
            ActionButton { theme: theme; text: "Exportar selecionados (" + window.backend.selectedDocuments + ")…"; primary: true; enabled: !window.backend.worker.busy && window.backend.selectedDocuments > 0; onClicked: window.backend.exportBatch() }
            ActionButton { objectName: "batchCancelAction"; theme: theme; text: window.backend.batchRunning ? (window.backend.batchCancelling ? "Cancelando…" : "Cancelar operação") : "Fechar"; enabled: !window.backend.batchCancelling; onClicked: { if (window.backend.batchRunning) window.backend.cancelBatch(); else documents.close(); } }
            ActionButton { theme: theme; text: "Novo lote…"; enabled: !window.backend.worker.busy; onClicked: window.backend.newBatch() }
        }
        width: Math.min(window.width - 48, 850); height: Math.min(window.height - 48, 610)
        closePolicy: window.backend.batchRunning ? Popup.NoAutoClose : Popup.CloseOnEscape
        ColumnLayout {
            Keys.onEscapePressed: if (window.backend.batchRunning) window.backend.cancelBatch()
            anchors.fill: parent; spacing: 12
            Text { textFormat: Text.PlainText; text: window.backend.batchMessage || "Revise cada documento antes de publicar no vault."; color: theme.muted; wrapMode: Text.Wrap; Layout.fillWidth: true; font.pixelSize: theme.bodySize }
            OperationProgress { theme: theme; visible: window.backend.batchRunning; Layout.fillWidth: true; from: 0; to: Math.max(1, window.backend.batchTotal); value: window.backend.batchCurrent; indeterminate: window.backend.batchTotal === 0 }
            ListView {
                id: documentList; objectName: "documentList"
                Text { textFormat: Text.PlainText; anchors.centerIn: parent; width: parent.width - 32; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap; text: "Nenhum documento nesta sessão.\nUse Novo lote para adicionar PDFs e iniciar a revisão."; visible: documentList.count === 0; color: theme.muted; font.pixelSize: theme.bodySize }
                Layout.fillWidth: true; Layout.fillHeight: true; clip: true
                model: window.backend.documentModel; spacing: 6
                ScrollBar.vertical: SurfaceScrollBar { theme: theme }
                delegate: Rectangle {
                    id: row
                    required property string key
                    required property string name
                    required property string status
                    required property string detail
                    required property bool included
                    required property bool ready
                    required property bool external
                    width: ListView.view.width; height: Math.max(72, rowText.implicitHeight + 20)
                    radius: 0; color: rowHover.hovered ? theme.surface : "transparent"
                    HoverHandler { id: rowHover }
                    Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: theme.border }
                    RowLayout {
                        anchors.fill: parent; anchors.margins: 10; anchors.rightMargin: documentList.ScrollBar.vertical.size < 0.999 ? 16 : 10; spacing: 10
                        Toggle { theme: theme; text: ""; Accessible.name: "Incluir " + row.name + " na exportação"; checked: row.included; visible: !row.external; enabled: !window.backend.worker.busy && row.ready; onToggled: window.backend.include(row.key, checked) }
                        ColumnLayout {
                            id: rowText; Layout.fillWidth: true; spacing: 3
                            Text { textFormat: Text.PlainText; text: row.name; color: theme.text; font.pixelSize: theme.bodySize; elide: Text.ElideMiddle; Layout.fillWidth: true }
                            StatusLabel {
                                theme: theme; text: row.status
                                tone: row.status.indexOf("Falhou") >= 0 ? "danger" : (row.status === "Salvo" || row.status === "Já salvo" || row.status.indexOf("· Salvo") >= 0) ? "success" : (row.status.indexOf("Não salvo") >= 0 || row.status === "Cancelado" || row.status === "Não executado" || row.status === "Não exportado") ? "warning" : "neutral"
                            }
                            Text { textFormat: Text.PlainText; visible: row.ready && !row.included && !row.external; text: "Fora da exportação"; color: theme.warning; font.pixelSize: theme.captionSize; Layout.fillWidth: true; wrapMode: Text.WordWrap }
                            Text { textFormat: Text.PlainText; visible: row.detail.length > 0; text: row.detail; color: theme.muted; font.pixelSize: theme.captionSize; wrapMode: Text.Wrap; Layout.fillWidth: true }
                        }
                        ActionButton { theme: theme; text: "Revisar"; enabled: row.ready && !window.backend.worker.busy; onClicked: window.changeDocument(row.key) }
                    }
                }
            }

        }
    }
    SurfaceDialog {
        id: filteredDialog; objectName: "filteredDialog"; onClosed: window.backend.closeFiltered(); theme: theme; title: "Imagens filtradas nas margens"
        footer: DialogActions {
            theme: theme
            ActionButton { theme: theme; text: "Fechar"; onClicked: filteredDialog.close() }
        }
        width: Math.min(window.width - 48, 750); height: Math.min(window.height - 48, 560)
        ColumnLayout {
            anchors.fill: parent; spacing: 12
            Text { textFormat: Text.PlainText; text: "Elementos recorrentes omitidos. Restaurar insere a figura ao final do trecho da página."; color: theme.muted; wrapMode: Text.Wrap; Layout.fillWidth: true; font.pixelSize: theme.bodySize }
            ListView {
                id: filteredList
                Layout.fillWidth: true; Layout.fillHeight: true; clip: true
                model: window.backend.filteredModel; spacing: 8; ScrollBar.vertical: SurfaceScrollBar { theme: theme }
                Text { textFormat: Text.PlainText; anchors.centerIn: parent; width: parent.width - 32; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap; text: "Nenhuma imagem filtrada neste documento."; visible: filteredList.count === 0; color: theme.muted; font.pixelSize: theme.bodySize }
                delegate: Rectangle {
                    id: filteredRow
                    required property string key
                    required property int page
                    required property string reason
                    required property string thumbnail
                    required property bool restorable
                    required property string issue
                    Component.onCompleted: window.backend.reviewFiltered(Number(key))
                    width: ListView.view.width - (filteredList.ScrollBar.vertical.size < 0.999 ? 14 : 0); height: Math.max(theme.mediaRowHeight, filteredText.implicitHeight + theme.listPadding * 2)
                    radius: theme.controlRadius; color: theme.raised
                    RowLayout {
                        anchors.fill: parent; anchors.margins: theme.listPadding; spacing: 12
                        Image { source: filteredRow.thumbnail; Layout.preferredWidth: 100; Layout.preferredHeight: 70; fillMode: Image.PreserveAspectFit; sourceSize.width: 200; sourceSize.height: 140 }
                        ColumnLayout {
                            id: filteredText; Layout.fillWidth: true
                            Text { textFormat: Text.PlainText; text: "Página " + filteredRow.page; color: theme.text; font.pixelSize: theme.bodySize }
                            Text { textFormat: Text.PlainText; text: filteredRow.reason; color: theme.muted; wrapMode: Text.Wrap; Layout.fillWidth: true; font.pixelSize: theme.captionSize }
                            Text { textFormat: Text.PlainText; visible: filteredRow.issue.length > 0; text: filteredRow.issue; color: theme.muted; wrapMode: Text.Wrap; Layout.fillWidth: true; font.pixelSize: theme.captionSize }
                            Flow {
                                Layout.fillWidth: true; spacing: 8
                                ActionButton { theme: theme; text: "Ver no PDF"; enabled: window.backend.editable; onClicked: { window.pdfVisible = true; window.backend.goPage(filteredRow.page); filteredDialog.close(); } }
                                ActionButton { theme: theme; text: "Restaurar"; description: "Restaurar imagem no Markdown; a ação pode ser desfeita"; enabled: window.backend.editable && filteredRow.restorable; onClicked: window.backend.restoreImage(Number(filteredRow.key)) }
                            }
                        }
                    }
                }
            }
        }
    }
    SurfaceDialog {
        id: messageDialog; objectName: "messageDialog"; theme: theme
        width: Math.min(window.width - 48, 560)
        height: Math.min(implicitHeight, window.height - 48)
        property bool confirmation: false
        property string kind: "info"
        tone: kind === "error" ? "danger" : confirmation ? "warning" : "info"
        onOpened: messageCancel.forceActiveFocus(Qt.PopupFocusReason)
        onRejected: if (confirmation) window.backend.answer(false)
        onClosed: {
            if (confirmation) window.backend.answer(false);
            Qt.callLater(function() {
                if (!messageDialog.visible && window.messageQueue.length) {
                    let next = window.messageQueue.shift();
                    window.showMessage(next.title, next.message, next.kind);
                }
            });
        }
        contentItem: ScrollView {
            id: messageScroll
            implicitHeight: messageText.implicitHeight
            contentWidth: availableWidth
            clip: true
            ScrollBar.vertical: SurfaceScrollBar { theme: theme }
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
            TextEdit {
                textFormat: TextEdit.PlainText
                readOnly: true; selectByMouse: true; persistentSelection: true
                selectionColor: theme.selection; selectedTextColor: theme.text
                id: messageText; objectName: "messageText"
                width: messageScroll.availableWidth
                color: theme.text; font.pixelSize: theme.bodySize
                wrapMode: TextEdit.Wrap
            }
        }
        footer: DialogActions {
            theme: theme
            ActionButton { objectName: "discardAction"; theme: theme; visible: messageDialog.confirmation; text: "Descartar"; destructive: true; onClicked: { messageDialog.confirmation = false; messageDialog.close(); window.backend.answer(true); } }
            ActionButton { id: messageCancel; objectName: "messageCancelAction"; theme: theme; text: messageDialog.confirmation ? "Cancelar" : "OK"; primary: !messageDialog.confirmation; onClicked: { if (messageDialog.confirmation) window.backend.answer(false); messageDialog.close(); } }
        }
    }
    SurfaceDialog {
        id: linkDialog; objectName: "linkDialog"; theme: theme; onClosed: editor.forceActiveFocus(); title: "Inserir link"
        width: Math.min(window.width - 48, 500)
        height: Math.min(implicitHeight, window.height - 48)
        contentItem: ScrollView {
            id: linkScroll
            implicitHeight: linkFields.implicitHeight
            contentWidth: availableWidth
            clip: true
            ScrollBar.vertical: SurfaceScrollBar { theme: theme }
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
            ColumnLayout {
                id: linkFields; width: linkScroll.availableWidth; spacing: 12
                Text { textFormat: Text.PlainText; text: "Texto"; color: theme.muted; font.pixelSize: theme.labelSize; font.weight: Font.Medium }
                Field { id: linkLabel; objectName: "linkLabel"; theme: theme; Layout.fillWidth: true; Accessible.name: "Texto do link"; onAccepted: if (linkDestination.text.trim().length > 0) { window.backend.insertLink(linkLabel.text, linkDestination.text); linkDialog.close(); } else linkDestination.forceActiveFocus() }
                Text { textFormat: Text.PlainText; text: "Destino"; color: theme.muted; font.pixelSize: theme.labelSize; font.weight: Font.Medium }
                Field { id: linkDestination; objectName: "linkDestination"; theme: theme; Layout.fillWidth: true; Accessible.name: "Destino do link"; placeholderText: "https://… ou caminho relativo"; onAccepted: if (linkDestination.text.trim().length > 0) { window.backend.insertLink(linkLabel.text, linkDestination.text); linkDialog.close(); } }
            }
        }
        footer: DialogActions {
            theme: theme
            ActionButton { theme: theme; text: "Inserir link"; primary: true; enabled: linkDestination.text.trim().length > 0; onClicked: { window.backend.insertLink(linkLabel.text, linkDestination.text); linkDialog.close(); } }
            ActionButton { theme: theme; text: "Cancelar"; onClicked: linkDialog.close() }
        }
    }
    SurfaceDialog {
        id: options; objectName: "options"; theme: theme; title: "Opções"
        width: Math.min(window.width - 48, 500)
        height: Math.min(implicitHeight, window.height - 48)
        contentItem: ScrollView {
            id: optionsScroll
            implicitHeight: optionsFields.implicitHeight
            contentWidth: availableWidth
            clip: true
            ScrollBar.vertical: SurfaceScrollBar { theme: theme }
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
            ColumnLayout {
                id: optionsFields; width: optionsScroll.availableWidth; spacing: 12
                Toggle { objectName: "nextOcrModeAction"; theme: theme; Layout.fillWidth: true; text: "OCR automático nas próximas conversões"; checked: window.backend.worker.ocrMode === "auto"; enabled: !window.backend.worker.busy; onToggled: window.backend.worker.setOcrMode(checked ? "auto" : "off") }
                Text { textFormat: Text.PlainText; Layout.fillWidth: true; text: window.backend.worker.recognitionStatus + " Não altera o documento atual."; color: theme.muted; font.pixelSize: theme.captionSize; wrapMode: Text.WordWrap }
                Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: theme.border }
                Toggle { objectName: "reducedMotionAction"; theme: theme; Layout.fillWidth: true; text: "Reduzir movimento"; checked: window.backend.visualSettings.reducedMotion; onToggled: window.backend.visualSettings.setReducedMotion(checked) }
                Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: theme.border }
                Toggle { theme: theme; Layout.fillWidth: true; text: "Remover marcações de página na exportação"; checked: window.backend.stripMarkers; enabled: window.backend.editable; onToggled: window.backend.setStripMarkers(checked) }
                Text { textFormat: Text.PlainText; text: "Afeta somente a cópia salva no vault. Os marcadores continuam disponíveis durante a revisão."; color: theme.muted; font.pixelSize: theme.captionSize; wrapMode: Text.Wrap; Layout.fillWidth: true }
            }
        }
        footer: DialogActions {
            theme: theme
            ActionButton { theme: theme; text: "Fechar"; onClicked: options.close() }
        }
    }
}
