import QtQuick
import QtQuick.Shapes

Item {
    id: icon
    property string name: "document"
    property color tint: "#b0b3bc"
    implicitWidth: 24
    implicitHeight: 24
    // Local vector paths, normalized to a 24 × 24 viewbox; no fonts or network.
    readonly property string pathData: {
        switch (name) {
        case "chevron": return "M6 9L12 15L18 9";
        case "bold": return "M7 4H13C19 4 19 12 13 12H7V4 M7 12H14C21 12 21 20 14 20H7V12";
        case "italic": return "M11 4H19 M5 20H13 M15 4L9 20";
        case "link": return "M9 15L15 9 M9 17L7 19C4 22 0 17 3 13L7 9 M15 7L17 5C20 2 24 7 21 11L17 15";
        case "bullet": return "M9 6H21 M9 12H21 M9 18H21 M3 6H4 M3 12H4 M3 18H4";
        case "ordered": return "M10 6H21 M10 12H21 M10 18H21 M3 3H4V8 M2 12C6 9 7 13 2 17H6 M2 20H6";
        case "quote": return "M4 7H10V13H5C5 16 7 17 9 17 M14 7H20V13H15C15 16 17 17 19 17";
        case "align": return "M3 5H21 M3 10H15 M3 15H21 M3 20H15";
        case "undo": return "M8 4L3 9L8 14 M3 9H14C23 9 23 20 14 20";
        case "redo": return "M16 4L21 9L16 14 M21 9H10C1 9 1 20 10 20";
        case "close": return "M6 6L18 18 M18 6L6 18";
        case "arrow": return "M5 12H19 M13 6L19 12L13 18";
        case "stack": return "M8 3H20V17 M4 7H16V21H4Z M7 11H13 M7 15H11";
        case "shield": return "M12 3L20 6V12C20 17 16 20 12 22C8 20 4 17 4 12V6Z M8 12L11 15L16 10";
        default: return "M14 3H6V21H18V7Z M14 3V7H18 M9 11H15 M9 15H15";
        }
    }
    Item {
        width: 24
        height: 24
        scale: Math.min(icon.width, icon.height) / 24
        transformOrigin: Item.TopLeft
        Shape {
            anchors.fill: parent
            ShapePath {
                strokeColor: icon.tint
                strokeWidth: 1.6
                fillColor: "transparent"
                capStyle: ShapePath.RoundCap
                joinStyle: ShapePath.RoundJoin
                PathSvg { path: icon.pathData }
            }
        }
    }
}
