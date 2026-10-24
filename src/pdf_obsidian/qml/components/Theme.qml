import QtQuick
import "Tokens.js" as Tokens

QtObject {
    readonly property var colors: Tokens.colors
    readonly property real readingWidth: Tokens.reviewMetrics.readingWidth * textScale
    readonly property real editorSize: Tokens.reviewMetrics.editorSize * textScale
    readonly property color background: colors.background
    readonly property color surface: colors.surface
    readonly property color raised: colors.raised
    readonly property color hover: colors.hover
    readonly property color border: colors.border
    readonly property color controlBorder: colors.controlBorder
    readonly property color controlBorderHover: colors.controlBorderHover
    readonly property color text: colors.text
    readonly property color muted: colors.muted
    readonly property color disabled: colors.disabled
    readonly property color accent: colors.accent
    readonly property color accentHover: colors.accentHover
    readonly property color accentPressed: colors.accentPressed
    readonly property color accentText: colors.on_accent
    readonly property int small: Tokens.metrics.small
    readonly property int medium: Tokens.metrics.medium
    readonly property int large: Tokens.metrics.large
    readonly property int controlRadius: Tokens.metrics.controlRadius
    readonly property int panelRadius: Tokens.metrics.panelRadius
    readonly property int controlHeight: Tokens.metrics.controlHeight
    readonly property color canvas: colors.canvas
    readonly property color selection: colors.selection
    readonly property color success: colors.success
    readonly property color warning: colors.warning
    readonly property color danger: colors.danger
    readonly property color successSurface: colors.successSurface
    readonly property color warningSurface: colors.warningSurface
    readonly property color dangerSurface: colors.dangerSurface
    readonly property color overlay: colors.overlay
    readonly property color imageSelection: colors.imageSelection
    readonly property int menuWidth: Tokens.metrics.menuWidth
    readonly property int iconSize: Tokens.metrics.iconSize
    readonly property int statusIconSize: Tokens.metrics.statusIconSize
    readonly property int importIconSize: Tokens.metrics.importIconSize
    readonly property int chevronSize: Tokens.metrics.chevronSize
    readonly property int listPadding: Tokens.metrics.listPadding
    readonly property int mediaRowHeight: Tokens.metrics.mediaRowHeight
    readonly property int menuItemRadius: Tokens.metrics.menuItemRadius
    property bool reducedMotion: false
    readonly property int motionDuration: reducedMotion ? 0 : Tokens.metrics.motionDuration
    readonly property int dialogPadding: Tokens.metrics.dialogPadding
    readonly property int readingInset: Tokens.reviewMetrics.readingInset
    property string fontFamily: "sans-serif"
    // Explicit multiplier permits a repeatable enlarged-font visual check.
    property real textScale: 1.0
    readonly property real labelSize: Tokens.metrics.labelSize * textScale
    readonly property real sectionSize: Tokens.metrics.sectionSize * textScale
    readonly property real bodySize: Tokens.metrics.bodySize * textScale
    readonly property real captionSize: Tokens.metrics.captionSize * textScale
    readonly property real titleSize: Tokens.metrics.titleSize * textScale
}
