import QtQuick
import "Tokens.js" as Tokens

QtObject {
    readonly property color background: Tokens.colors.background
    readonly property color surface: Tokens.colors.surface
    readonly property color raised: Tokens.colors.raised
    readonly property color hover: Tokens.colors.hover
    readonly property color border: Tokens.colors.border
    readonly property color text: Tokens.colors.text
    readonly property color muted: Tokens.colors.muted
    readonly property color disabled: Tokens.colors.disabled
    readonly property color accent: Tokens.colors.accent
    readonly property color accentHover: Tokens.colors.accentHover
    readonly property color accentPressed: Tokens.colors.accentPressed
    readonly property color accentText: Tokens.colors.on_accent
    readonly property int small: Tokens.metrics.small
    readonly property int medium: Tokens.metrics.medium
    readonly property int large: Tokens.metrics.large
    readonly property int controlRadius: Tokens.metrics.controlRadius
    readonly property int panelRadius: Tokens.metrics.panelRadius
    readonly property int controlHeight: Tokens.metrics.controlHeight
    property string fontFamily: "sans-serif"
    // Explicit multiplier permits a repeatable enlarged-font visual check.
    property real textScale: 1.0
    readonly property real bodySize: Tokens.metrics.bodySize * textScale
    readonly property real captionSize: Tokens.metrics.captionSize * textScale
    readonly property real titleSize: Tokens.metrics.titleSize * textScale
}
