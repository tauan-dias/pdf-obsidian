import QtQuick

Field {
    id: control
    required property int value
    required property int minimum
    required property int maximum
    property bool edited: false
    signal committed(int number)
    text: String(value)
    validator: IntValidator { bottom: control.minimum; top: control.maximum }
    function reset() {
        edited = false;
        text = Qt.binding(function() { return String(control.value); });
    }
    function finish() {
        const apply = edited && enabled && acceptableInput;
        const number = Number(text);
        reset();
        if (apply) committed(number);
    }
    onTextEdited: edited = true
    onEditingFinished: finish()
    // Invalid input does not emit editingFinished on every Qt path.
    onActiveFocusChanged: if (!activeFocus) finish()
    onEnabledChanged: if (!enabled) reset()
}
