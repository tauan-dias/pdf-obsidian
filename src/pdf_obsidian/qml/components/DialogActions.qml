import QtQuick

Flow {
    required property Theme theme
    padding: theme.dialogPadding
    topPadding: 12
    spacing: 8
    layoutDirection: Qt.RightToLeft
}
