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
    font: window.backend.nativeFont
    palette.window: theme.background
    palette.windowText: theme.text
    palette.base: theme.background
    palette.text: theme.text
    palette.button: theme.raised
    palette.buttonText: theme.text
    palette.highlight: theme.accent
    palette.highlightedText: theme.accentText
    Theme { id: theme; fontFamily: window.font.family; textScale: (window.font.pixelSize > 0 ? window.font.pixelSize : window.font.pointSize * 96 / 72) / window.backend.baseFontPixels; onTextScaleChanged: window.backend.setTextScale(textScale) }
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
    Connections {
        target: window.backend
        function onSnapshotRequested() { window.saveView(); }
        function onDocumentsRequested() { documents.open(); }
        function onBatchPreparationRequested() { preparation.open(); }
        function onCloseApproved() { window.closingApproved = true; window.close(); }
        function onDialogRequested(title, message, kind) {
            messageDialog.title = title; messageText.text = message;
            messageDialog.confirmation = kind === "confirm"; messageDialog.open();
        }
        function onLinkRequested(label) { linkLabel.text = label; linkDestination.text = ""; linkDialog.open(); linkDestination.forceActiveFocus(); }
        function onSelectionRequested(anchor, position) { editor.select(anchor, position); editor.forceActiveFocus(); }
        function onViewRestored(state) {
            let sequence = ++window.restoreSequence;
            window.pendingPreviewY = state.previewY || 0;
            window.restoring = true;
            window.pdfVisible = state.pdfVisible === undefined ? true : state.pdfVisible;
            window.follow = state.follow || false; window.tab = state.tab || 0;
            window.warningsExpanded = state.warningsExpanded || false;
            window.pdfFraction = state.pdfFraction || 0.4;
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
    Shortcut { sequence: "Ctrl+Z"; enabled: window.backend.editable && window.tab === 1; onActivated: window.backend.undo() }
    Shortcut { sequences: ["Ctrl+Shift+Z", "Ctrl+Y"]; enabled: window.backend.editable && window.tab === 1; onActivated: window.backend.redo() }

    ImportPage {
        id: importPage
        anchors.fill: parent
        visible: !window.backend.hasDocument || window.backend.worker.operation === "convert"
        fontFamily: theme.fontFamily; textScale: theme.textScale
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
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: header.implicitHeight + 24
            color: theme.background
            RowLayout {
                id: header
                anchors.fill: parent; anchors.margins: 12; spacing: 10
                Icon { tint: theme.accent; Layout.preferredWidth: 22; Layout.preferredHeight: 22 }
                ColumnLayout {
                    Layout.fillWidth: true; spacing: 2
                    Text {
                        text: window.backend.title; Accessible.name: window.backend.documentPath
                        color: theme.text; font.pixelSize: theme.bodySize + 1; font.weight: Font.DemiBold
                        elide: Text.ElideRight; Layout.fillWidth: true
                        HoverHandler { id: documentHover }
                        ToolTip.visible: documentHover.hovered
                        ToolTip.text: window.backend.documentPath
                    }
                    Text { text: window.backend.modified ? "Alterações não salvas" : "Salvo no vault"; color: theme.muted; font.pixelSize: theme.captionSize }
                }
                ActionButton { theme: theme; text: "Abrir ▾"; enabled: !window.backend.worker.busy; onClicked: openMenu.open();
                    Menu { id: openMenu; y: parent.height
                        MenuItem { text: "Abrir PDF…    Ctrl+O"; onTriggered: window.backend.openPdf() }
                        MenuItem { text: "Converter em lote…"; onTriggered: window.backend.newBatch() }
                    }
                }
                ActionButton { theme: theme; text: "Documentos (" + window.backend.documentCount + ")"; onClicked: documents.open() }
                ActionButton { theme: theme; text: window.backend.worker.operation === "export" ? "Salvando…" : "Salvar no vault…"; primary: true; enabled: window.backend.editable && window.backend.worker.workerAvailable; onClicked: window.backend.exportCurrent() }
                ActionButton { theme: theme; text: "⋯"; Accessible.name: "Opções de exportação"; onClicked: options.open() }
            }
        }
        Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: theme.border }
        Flow {
            Layout.fillWidth: true; Layout.margins: 10; spacing: 8
            ActionButton { theme: theme; text: window.pdfVisible ? "Ocultar PDF" : "Mostrar PDF"; onClicked: { window.pdfVisible = !window.pdfVisible; window.saveView(); } }
            Toggle { theme: theme; text: "Acompanhar página"; checked: window.follow; onToggled: { window.follow = checked; if (checked) window.backend.follow_page(); window.saveView(); } }
            ActionButton { theme: theme; text: "Imagens filtradas (" + window.backend.filteredCount + ")"; visible: window.backend.filteredCount > 0; enabled: window.backend.editable; onClicked: { window.backend.openFiltered(); filteredDialog.open(); } }
            ActionButton { theme: theme; text: "Avisos (" + window.backend.warnings.length + ") " + (window.warningsExpanded ? "⌃" : "⌄"); visible: window.backend.warnings.length > 0; onClicked: { window.warningsExpanded = !window.warningsExpanded; window.saveView(); } }
        }
        Rectangle {
            visible: window.warningsExpanded && window.backend.warnings.length > 0
            Layout.fillWidth: true; Layout.preferredHeight: Math.min(110, warningsList.contentHeight + 12)
            color: theme.surface
            ListView {
                id: warningsList; anchors.fill: parent; anchors.margins: 6; clip: true; model: window.backend.warnings
                ScrollBar.vertical: ScrollBar {}
                delegate: ItemDelegate {
                    id: warningRow
                    required property var modelData
                    width: ListView.view.width; height: Math.max(34, warningText.implicitHeight + 12)
                    contentItem: Text { id: warningText; text: "Página " + warningRow.modelData.page + " · " + warningRow.modelData.message; color: theme.muted; wrapMode: Text.Wrap; font.pixelSize: theme.captionSize }
                    onClicked: { window.pdfVisible = true; window.backend.goPage(modelData.page); }
                }
            }
        }
        SplitView {
            id: split
            Layout.fillWidth: true; Layout.fillHeight: true
            orientation: Qt.Horizontal
            handle: Rectangle {
                implicitWidth: 6; color: SplitHandle.hovered || SplitHandle.pressed ? theme.border : theme.background
                Accessible.name: "Ajustar divisão entre PDF e editor"
            }
            Rectangle {
                id: pdfPanel
                visible: window.pdfVisible
                SplitView.preferredWidth: split.width * window.pdfFraction
                SplitView.minimumWidth: 275
                color: theme.surface
                onWidthChanged: { if (!window.restoring && window.pdfVisible && split.width > 0) window.pdfFraction = width / split.width; }
                ColumnLayout {
                    anchors.fill: parent; spacing: 0
                    Flow {
                        Layout.fillWidth: true; Layout.margins: 8; spacing: 6
                        ActionButton { theme: theme; text: "‹"; Accessible.name: "Página anterior"; enabled: window.backend.editable && window.backend.page > 1; onClicked: window.backend.goPage(window.backend.page - 1) }
                        NumericField { id: pageField; objectName: "pageField"; theme: theme; width: 48; value: window.backend.page; minimum: 1; maximum: window.backend.pageCount; enabled: window.backend.editable; Accessible.name: "Página do PDF"; onCommitted: function(number) { window.backend.goPage(number); } }
                        Text { text: "/ " + window.backend.pageCount; color: theme.muted; font.pixelSize: theme.captionSize; height: pageField.height; verticalAlignment: Text.AlignVCenter }
                        ActionButton { theme: theme; text: "›"; Accessible.name: "Próxima página"; enabled: window.backend.editable && window.backend.page < window.backend.pageCount; onClicked: window.backend.goPage(window.backend.page + 1) }
                        ActionButton { theme: theme; text: "−"; Accessible.name: "Reduzir zoom"; enabled: window.backend.editable; onClicked: window.backend.setZoom(window.backend.zoom - 25) }
                        NumericField { objectName: "zoomField"; theme: theme; width: 58; value: window.backend.zoom; minimum: 25; maximum: 300; enabled: window.backend.editable; Accessible.name: "Zoom percentual"; onCommitted: function(number) { window.backend.setZoom(number); } }
                        ActionButton { theme: theme; text: "+"; Accessible.name: "Ampliar zoom"; enabled: window.backend.editable; onClicked: window.backend.setZoom(window.backend.zoom + 25) }
                        ActionButton { theme: theme; text: "Ajustar ▾"; onClicked: fitMenu.open()
                            Menu { id: fitMenu; y: parent.height
                                MenuItem { text: "À largura"; onTriggered: window.backend.fit("width") }
                                MenuItem { text: "À página"; onTriggered: window.backend.fit("page") }
                            }
                        }
                        Toggle { theme: theme; text: "Recortar"; checked: window.cropMode; enabled: window.backend.editable && !window.backend.rendering; onToggled: window.cropMode = checked }
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
                        ScrollBar.vertical: ScrollBar {}
                        ScrollBar.horizontal: ScrollBar {}
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
                                    color: "#33ff7869"; border.color: theme.accent
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
                    Text { Layout.fillWidth: true; Layout.margins: 8; text: window.backend.rendering ? "Renderizando página…" : window.cropMode ? "Arraste sobre o PDF para inserir um recorte." : "PDF original · somente leitura"; color: theme.muted; font.pixelSize: theme.captionSize; wrapMode: Text.Wrap }
                }
            }
            Rectangle {
                SplitView.fillWidth: true; SplitView.minimumWidth: 360
                color: theme.background
                ColumnLayout {
                    anchors.fill: parent; spacing: 0
                    RowLayout {
                        Layout.fillWidth: true; Layout.margins: 8; spacing: 6
                        ActionButton { theme: theme; text: "Markdown"; compact: true; selected: window.tab === 0; onClicked: { window.tab = 0; editor.forceActiveFocus(); window.saveView(); } }
                        ActionButton { theme: theme; text: "Prévia"; compact: true; selected: window.tab === 1; onClicked: { window.tab = 1; preview.forceActiveFocus(); window.saveView(); } }
                        Item { Layout.fillWidth: true }
                        ToolButton { theme: theme; objectName: "undoAction"; iconName: "undo"; description: "Desfazer"; shortcutHint: "Ctrl+Z"; Accessible.name: "Desfazer"; enabled: window.backend.canUndo; onClicked: window.backend.undo() }
                        ToolButton { theme: theme; objectName: "redoAction"; iconName: "redo"; description: "Refazer"; shortcutHint: "Ctrl+Shift+Z"; Accessible.name: "Refazer"; enabled: window.backend.canRedo; onClicked: window.backend.redo() }
                    }
                    Flow {
                        visible: window.tab === 0
                        objectName: "editorToolbar"
                        Layout.fillWidth: true; Layout.leftMargin: 8; Layout.rightMargin: 8; Layout.bottomMargin: 8; spacing: 4
                        enabled: window.backend.editable
                        Row {
                            spacing: 2
                            ToolButton { theme: theme; objectName: "styleAction"; text: "Estilo"; description: "Estilo do parágrafo"; menuIndicator: true; onClicked: styleMenu.open()
                                Menu { id: styleMenu; objectName: "styleMenu"; y: parent.height
                                    MenuItem { text: "Parágrafo"; onTriggered: window.format("heading", 0) }
                                    Repeater { model: 6; MenuItem { required property int index; text: "Título " + (index + 1); onTriggered: window.format("heading", index + 1) } }
                                }
                            }
                        }
                        Row {
                            objectName: "textTools"; spacing: 2
                            Rectangle { width: 1; height: 20; anchors.verticalCenter: parent.verticalCenter; color: theme.border; opacity: parent.x > 0 ? 1 : 0 }
                            ToolButton { theme: theme; objectName: "boldAction"; iconName: "bold"; description: "Negrito"; shortcutHint: "Ctrl+B"; onClicked: window.format("bold") }
                            ToolButton { theme: theme; objectName: "italicAction"; iconName: "italic"; description: "Itálico"; shortcutHint: "Ctrl+I"; onClicked: window.format("italic") }
                            ToolButton { theme: theme; objectName: "linkAction"; iconName: "link"; description: "Inserir link"; shortcutHint: "Ctrl+K"; onClicked: window.format("link") }
                        }
                        Row {
                            objectName: "paragraphTools"; spacing: 2
                            Rectangle { width: 1; height: 20; anchors.verticalCenter: parent.verticalCenter; color: theme.border; opacity: parent.x > 0 ? 1 : 0 }
                            ToolButton { theme: theme; objectName: "bulletAction"; iconName: "bullet"; description: "Lista com marcadores"; shortcutHint: ""; onClicked: window.format("bullet") }
                            ToolButton { theme: theme; objectName: "orderedAction"; iconName: "ordered"; description: "Lista numerada"; shortcutHint: ""; onClicked: window.format("ordered") }
                            ToolButton { theme: theme; objectName: "quoteAction"; iconName: "quote"; description: "Citação"; shortcutHint: ""; onClicked: window.format("quote") }
                            ToolButton { theme: theme; objectName: "alignAction"; iconName: "align"; description: "Alinhamento do parágrafo"; menuIndicator: true; onClicked: alignMenu.open()
                                Menu { id: alignMenu; objectName: "alignMenu"; y: parent.height
                                    MenuItem { text: "Esquerda"; onTriggered: window.format("align", "left") }
                                    MenuItem { text: "Centro"; onTriggered: window.format("align", "center") }
                                    MenuItem { text: "Direita"; onTriggered: window.format("align", "right") }
                                    MenuItem { text: "Justificado"; onTriggered: window.format("align", "justify") }
                                }
                            }
                        }
                    }
                    Flow {
                        visible: window.tab === 1
                        Layout.fillWidth: true; Layout.margins: 8; spacing: 8
                        Toggle { theme: theme; text: "Selecionar imagens"; checked: window.backend.selectionMode; enabled: window.backend.previewReady; onToggled: window.backend.setSelectionMode(checked) }
                        Text { visible: window.backend.selectionMode; text: window.backend.selectedImages + " selecionadas"; color: theme.muted; font.pixelSize: theme.captionSize; height: 32; verticalAlignment: Text.AlignVCenter }
                        ActionButton { theme: theme; visible: window.backend.selectionMode; text: "Remover selecionadas"; enabled: window.backend.previewReady && window.backend.selectedImages > 0; onClicked: window.backend.removeImages() }
                        ActionButton { theme: theme; visible: window.backend.selectionMode; text: "Limpar"; enabled: window.backend.selectedImages > 0; onClicked: window.backend.clearImages() }
                    }
                    Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: theme.border }
                    Item {
                        Layout.fillWidth: true; Layout.fillHeight: true
                        Flickable {
                            id: editorScroll
                            anchors.fill: parent; visible: window.tab === 0; clip: true
                            contentWidth: width; contentHeight: Math.max(height, editor.height + height - 60)
                            boundsBehavior: Flickable.StopAtBounds
                            ScrollBar.vertical: ScrollBar {}
                            TextEdit {
                                id: editor; objectName: "markdownEditor"
                                x: 18; y: 14; width: parent.width - 36
                                height: Math.max(contentHeight, editorScroll.height - 28)
                                textFormat: TextEdit.PlainText
                                wrapMode: TextEdit.Wrap
                                color: theme.text; selectionColor: theme.accent; selectedTextColor: theme.accentText
                                font.pixelSize: theme.bodySize; font.family: window.backend.editorFontFamily
                                selectByMouse: true; persistentSelection: true
                                readOnly: !window.backend.editable
                                Accessible.name: "Editor Markdown"
                                TapHandler { acceptedButtons: Qt.RightButton; onTapped: editorMenu.popup() }
                                Menu {
                                    id: editorMenu
                                    MenuItem { text: "Desfazer"; enabled: window.backend.canUndo; onTriggered: window.backend.undo() }
                                    MenuItem { text: "Refazer"; enabled: window.backend.canRedo; onTriggered: window.backend.redo() }
                                    MenuSeparator {}
                                    MenuItem { text: "Recortar"; enabled: window.backend.editable && editor.selectionStart !== editor.selectionEnd; onTriggered: editor.cut() }
                                    MenuItem { text: "Copiar"; enabled: editor.selectionStart !== editor.selectionEnd; onTriggered: editor.copy() }
                                    MenuItem { text: "Colar"; enabled: window.backend.editable && editor.canPaste; onTriggered: editor.paste() }
                                    MenuItem { text: "Selecionar tudo"; onTriggered: editor.selectAll() }
                                }
                                onCursorRectangleChanged: if (activeFocus && !window.restoring) {
                                    if (cursorRectangle.y + 30 > editorScroll.contentY + editorScroll.height) editorScroll.contentY = cursorRectangle.y + 30 - editorScroll.height;
                                    else if (cursorRectangle.y < editorScroll.contentY) editorScroll.contentY = cursorRectangle.y;
                                }
                            }
                        }
                        Text {
                            anchors.centerIn: parent
                            z: 1
                            visible: window.tab === 1 && window.backend.previewPending
                            text: "Preparando prévia…"
                            color: theme.muted
                            font.pixelSize: theme.captionSize
                        }
                        Flickable {
                            id: previewScroll
                            anchors.fill: parent; visible: window.tab === 1 && !window.backend.previewPending; clip: true
                            contentWidth: width; contentHeight: Math.max(height, preview.height + height - 60)
                            boundsBehavior: Flickable.StopAtBounds
                            ScrollBar.vertical: ScrollBar {}
                            TextEdit {
                                id: preview; objectName: "markdownPreview"
                                x: 18; y: 14; width: parent.width - 36
                                height: contentHeight
                                onWidthChanged: window.backend.previewResized()
                                textFormat: TextEdit.RichText
                                wrapMode: TextEdit.Wrap
                                readOnly: true; selectByMouse: true; persistentSelection: true
                                color: theme.text; selectionColor: theme.accent; selectedTextColor: theme.accentText
                                font.pixelSize: theme.bodySize
                                Accessible.name: "Prévia do Markdown"
                                TapHandler { acceptedButtons: Qt.RightButton; onTapped: previewMenu.popup() }
                                Menu {
                                    id: previewMenu
                                    MenuItem { text: "Copiar"; enabled: preview.selectionStart !== preview.selectionEnd; onTriggered: preview.copy() }
                                    MenuItem { text: "Selecionar tudo"; onTriggered: preview.selectAll() }
                                }
                                Repeater {
                                    model: window.backend.imageModel
                                    delegate: Rectangle {
                                        id: imageOverlay
                                        required property int position
                                        required property bool selected
                                        objectName: "previewImage-" + position
                                        property rect targetRect: { let layoutWidth = preview.width; let layoutHeight = preview.contentHeight; return preview.positionToRectangle(position); }
                                        property rect endRect: { let layoutWidth = preview.width; let layoutHeight = preview.contentHeight; return preview.positionToRectangle(position + 1); }
                                        x: targetRect.x; y: targetRect.y
                                        width: Math.max(16, endRect.x - targetRect.x)
                                        height: targetRect.height
                                        visible: window.backend.selectionMode && window.backend.previewReady
                                        color: imageOverlay.selected ? "#22ff7869" : "transparent"
                                        border.width: imageOverlay.selected ? 2 : 0
                                        border.color: theme.accent
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
            Text { id: statusText; anchors.fill: parent; anchors.margins: 8; text: window.backend.message || "Processamento local e offline"; color: theme.muted; font.pixelSize: theme.captionSize; elide: Text.ElideRight }
        }
    }

    SurfaceDialog {
        id: preparation; objectName: "preparation"; theme: theme; title: "Preparar conversão em lote"
        width: Math.min(window.width - 48, 700); height: Math.min(window.height - 48, 500)
        ColumnLayout {
            anchors.fill: parent; spacing: 12
            Text { text: window.backend.pendingCount + " documento(s). Remova os arquivos que não deseja converter."; color: theme.muted; font.pixelSize: theme.bodySize; wrapMode: Text.Wrap; Layout.fillWidth: true }
            ListView {
                Layout.fillWidth: true; Layout.fillHeight: true; clip: true; model: window.backend.pendingModel; spacing: 8
                ScrollBar.vertical: ScrollBar {}
                delegate: RowLayout {
                    id: pendingRow
                    required property string key
                    required property string name
                    width: ListView.view.width
                    Text { text: pendingRow.name; color: theme.text; font.pixelSize: theme.bodySize; elide: Text.ElideMiddle; Layout.fillWidth: true }
                    ActionButton { theme: theme; text: "Remover"; onClicked: window.backend.removePending(pendingRow.key) }
                }
            }
            RowLayout {
                ActionButton { theme: theme; text: "Adicionar PDFs…"; onClicked: window.backend.addPending() }
                Item { Layout.fillWidth: true }
                ActionButton { theme: theme; text: "Cancelar"; onClicked: preparation.close() }
                ActionButton { theme: theme; text: "Converter " + window.backend.pendingCount + " documento(s)"; primary: true; enabled: window.backend.pendingCount > 0; onClicked: { preparation.close(); window.backend.beginBatch(); } }
            }
        }
    }
    SurfaceDialog {
        id: documents; objectName: "documents"; theme: theme; title: "Documentos da sessão"
        width: Math.min(window.width - 48, 850); height: Math.min(window.height - 48, 610)
        closePolicy: window.backend.batchRunning ? Popup.NoAutoClose : Popup.CloseOnEscape
        ColumnLayout {
            Keys.onEscapePressed: if (window.backend.batchRunning) window.backend.cancelBatch()
            anchors.fill: parent; spacing: 12
            Text { text: window.backend.batchMessage || "Revise cada documento antes de publicar no vault."; color: theme.muted; wrapMode: Text.Wrap; Layout.fillWidth: true; font.pixelSize: theme.bodySize }
            ProgressBar { visible: window.backend.batchRunning; Layout.fillWidth: true; from: 0; to: Math.max(1, window.backend.batchTotal); value: window.backend.batchCurrent; indeterminate: window.backend.batchTotal === 0 }
            ListView {
                id: documentList; objectName: "documentList"
                Layout.fillWidth: true; Layout.fillHeight: true; clip: true
                model: window.backend.documentModel; spacing: 6
                ScrollBar.vertical: ScrollBar {}
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
                    radius: 8; color: theme.raised; border.color: theme.border
                    RowLayout {
                        anchors.fill: parent; anchors.margins: 10; spacing: 10
                        Toggle { theme: theme; text: ""; Accessible.name: "Incluir " + row.name + " na exportação"; checked: row.included; visible: !row.external; enabled: !window.backend.worker.busy && row.ready; onToggled: window.backend.include(row.key, checked) }
                        ColumnLayout {
                            id: rowText; Layout.fillWidth: true; spacing: 3
                            Text { text: row.name; color: theme.text; font.pixelSize: theme.bodySize; elide: Text.ElideMiddle; Layout.fillWidth: true }
                            Text { text: row.status; color: theme.muted; font.pixelSize: theme.captionSize }
                            Text { visible: row.detail.length > 0; text: row.detail; color: theme.muted; font.pixelSize: theme.captionSize; wrapMode: Text.Wrap; Layout.fillWidth: true }
                        }
                        ActionButton { theme: theme; text: "Revisar"; enabled: row.ready && !window.backend.worker.busy; onClicked: window.changeDocument(row.key) }
                    }
                }
            }
            Flow {
                Layout.fillWidth: true; spacing: 8
                ActionButton { theme: theme; text: "Novo lote…"; enabled: !window.backend.worker.busy; onClicked: window.backend.newBatch() }
                ActionButton { theme: theme; text: "Exportar selecionados (" + window.backend.selectedDocuments + ")…"; primary: true; enabled: !window.backend.worker.busy && window.backend.selectedDocuments > 0; onClicked: window.backend.exportBatch() }
                ActionButton { theme: theme; text: window.backend.batchRunning ? (window.backend.batchCancelling ? "Cancelando…" : "Cancelar operação") : "Fechar"; enabled: !window.backend.batchCancelling; onClicked: { if (window.backend.batchRunning) window.backend.cancelBatch(); else documents.close(); } }
            }
        }
    }
    SurfaceDialog {
        id: filteredDialog; objectName: "filteredDialog"; onClosed: window.backend.closeFiltered(); theme: theme; title: "Imagens filtradas nas margens"
        width: Math.min(window.width - 48, 750); height: Math.min(window.height - 48, 560)
        ColumnLayout {
            anchors.fill: parent; spacing: 12
            Text { text: "Elementos recorrentes omitidos. Restaurar insere a figura ao final do trecho da página."; color: theme.muted; wrapMode: Text.Wrap; Layout.fillWidth: true; font.pixelSize: theme.bodySize }
            ListView {
                Layout.fillWidth: true; Layout.fillHeight: true; clip: true
                model: window.backend.filteredModel; spacing: 8; ScrollBar.vertical: ScrollBar {}
                delegate: Rectangle {
                    id: filteredRow
                    required property string key
                    required property int page
                    required property string reason
                    required property string thumbnail
                    required property bool restorable
                    required property string issue
                    Component.onCompleted: window.backend.reviewFiltered(Number(key))
                    width: ListView.view.width; height: Math.max(125, filteredText.implicitHeight + 20)
                    radius: 8; color: theme.raised
                    RowLayout {
                        anchors.fill: parent; anchors.margins: 10; spacing: 12
                        Image { source: filteredRow.thumbnail; Layout.preferredWidth: 100; Layout.preferredHeight: 70; fillMode: Image.PreserveAspectFit; sourceSize.width: 200; sourceSize.height: 140 }
                        ColumnLayout {
                            id: filteredText; Layout.fillWidth: true
                            Text { text: "Página " + filteredRow.page; color: theme.text; font.pixelSize: theme.bodySize }
                            Text { text: filteredRow.reason; color: theme.muted; wrapMode: Text.Wrap; Layout.fillWidth: true; font.pixelSize: theme.captionSize }
                            Text { visible: filteredRow.issue.length > 0; text: filteredRow.issue; color: theme.muted; wrapMode: Text.Wrap; Layout.fillWidth: true; font.pixelSize: theme.captionSize }
                            RowLayout {
                                ActionButton { theme: theme; text: "Ver no PDF"; enabled: window.backend.editable; onClicked: { window.pdfVisible = true; window.backend.goPage(filteredRow.page); filteredDialog.close(); } }
                                ActionButton { theme: theme; text: "Restaurar"; enabled: window.backend.editable && filteredRow.restorable; onClicked: window.backend.restoreImage(Number(filteredRow.key)) }
                            }
                        }
                    }
                }
            }
            ActionButton { theme: theme; text: "Fechar"; onClicked: filteredDialog.close() }
        }
    }
    SurfaceDialog {
        id: messageDialog; objectName: "messageDialog"; theme: theme
        width: Math.min(window.width - 48, 560)
        property bool confirmation: false
        onRejected: if (confirmation) window.backend.answer(false)
        contentItem: ColumnLayout {
            spacing: 20
            Text { id: messageText; color: theme.text; font.pixelSize: theme.bodySize; wrapMode: Text.Wrap; Layout.fillWidth: true }
            RowLayout {
                Item { Layout.fillWidth: true }
                ActionButton { theme: theme; text: messageDialog.confirmation ? "Cancelar" : "OK"; onClicked: { if (messageDialog.confirmation) window.backend.answer(false); messageDialog.close(); } }
                ActionButton { theme: theme; visible: messageDialog.confirmation; text: "Descartar"; onClicked: { messageDialog.close(); window.backend.answer(true); } }
            }
        }
    }
    SurfaceDialog {
        id: linkDialog; objectName: "linkDialog"; theme: theme; onClosed: editor.forceActiveFocus(); title: "Inserir link"; width: Math.min(window.width - 48, 500)
        contentItem: ColumnLayout {
            spacing: 12
            Text { text: "Texto"; color: theme.muted; font.pixelSize: theme.bodySize }
            Field { id: linkLabel; theme: theme; Layout.fillWidth: true; Accessible.name: "Texto do link" }
            Text { text: "Destino"; color: theme.muted; font.pixelSize: theme.bodySize }
            Field { id: linkDestination; theme: theme; Layout.fillWidth: true; Accessible.name: "Destino do link"; placeholderText: "https://… ou caminho relativo" }
            RowLayout {
                Item { Layout.fillWidth: true }
                ActionButton { theme: theme; text: "Cancelar"; onClicked: linkDialog.close() }
                ActionButton { theme: theme; text: "Inserir link"; primary: true; enabled: linkDestination.text.trim().length > 0; onClicked: { window.backend.insertLink(linkLabel.text, linkDestination.text); linkDialog.close(); } }
            }
        }
    }
    SurfaceDialog {
        id: options; objectName: "options"; theme: theme; title: "Opções de exportação"; width: Math.min(window.width - 48, 500)
        contentItem: ColumnLayout {
            spacing: 12
            Toggle { theme: theme; text: "Remover marcações de página na exportação"; checked: window.backend.stripMarkers; enabled: window.backend.editable; onToggled: window.backend.setStripMarkers(checked) }
            Text { text: "Afeta somente a cópia salva no vault."; color: theme.muted; font.pixelSize: theme.captionSize; wrapMode: Text.Wrap; Layout.fillWidth: true }
            ActionButton { theme: theme; text: "Fechar"; onClicked: options.close() }
        }
    }
}
