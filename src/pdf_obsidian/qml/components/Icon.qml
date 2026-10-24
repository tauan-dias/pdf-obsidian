import QtQuick
import "Tokens.js" as Tokens

Item {
    id: icon
    property string name: "document"
    property color tint: Tokens.colors.muted
    implicitWidth: 20
    implicitHeight: 20
    Image {
        anchors.fill: parent
        source: "image://ui/" + icon.name + "/" + icon.tint.toString().slice(1)
        sourceSize.width: Math.ceil(width * Screen.devicePixelRatio)
        sourceSize.height: Math.ceil(height * Screen.devicePixelRatio)
        fillMode: Image.PreserveAspectFit
        smooth: true
    }
}
