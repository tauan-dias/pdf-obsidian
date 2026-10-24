"""Um processo auxiliar possui todos os objetos PyMuPDF."""
from pathlib import Path
import traceback


def run(commands, events, cancel):
    from .converter import convert, make_crop, ConversionCancelled
    from .pdf import render
    from .exporter import export_document, export_signature, export_intact
    while True:
        command = commands.get()
        if command[0] == "stop":
            return
        if command[0] == "review_filtered":
            _, token, session_id, revision, index, result, markdown = command
            from .restoration import restoration_edit
            try:
                restoration_edit(result, markdown, result.filtered_images[index])
                issue = ""
            except Exception as exc:
                issue = str(exc)
            events.put(("filtered_checked", token, session_id, revision, index, issue))
            continue
        if command[0] in ("session_convert", "session_crop"):
            task, token, source, workspace, *args = command
            def session_emit(kind, *data):
                events.put(("session_event", token, kind, *data))
            try:
                if task == "session_convert":
                    result = convert(Path(source), Path(workspace),
                                     lambda n, total: session_emit("progress", n, total), cancel.is_set,
                                     options=args[0] if args else None, stage=lambda text: session_emit("stage", text))
                    session_emit("converted", result)
                else:
                    page, bbox = args
                    session_emit("cropped", make_crop(source, workspace, page, bbox))
            except ConversionCancelled:
                session_emit("cancelled")
            except Exception as exc:
                session_emit("error", str(exc))
            continue
        if command[0] == "session_export":
            _, token, session_id, revision, vault, result, markdown, strip, removals, record = command
            try:
                signature = export_signature(result, markdown, strip_page_markers=strip,
                                             cleanup_removals=removals)
                unchanged = bool(record and record.signature == signature and export_intact(record, vault))
                manifest = dict(record.manifest) if unchanged else {}
                target = record.target if unchanged else export_document(
                    result, vault, markdown, strip_page_markers=strip, cleanup_removals=removals, manifest=manifest)
                divergent = bool(record and record.signature == signature and not unchanged)
                events.put(("session_export", token, session_id, revision, True, signature, str(target), unchanged, manifest, divergent))
            except Exception as exc:
                events.put(("session_export", token, session_id, revision, False, str(exc), "", False))
            continue
        if command[0].startswith("batch_"):
            task, token, item_id, *args = command
            def emit(kind, *data):
                events.put(("batch", token, item_id, kind, *data))
            try:
                if cancel.is_set():
                    raise ConversionCancelled()
                if task == "batch_convert":
                    source, workspace, *option_args = args
                    result = convert(Path(source), Path(workspace),
                                     lambda n, total: emit("progress", n, total), cancel.is_set,
                                     options=option_args[0] if option_args else None, stage=lambda text: emit("stage", text))
                    emit("converted", result)
                else:
                    if task == "batch_check":
                        result, markdown, strip, removals, record = args
                    else:
                        vault, result, markdown, strip, removals = args
                    signature = export_signature(result, markdown, strip_page_markers=strip,
                                                 cleanup_removals=removals)
                    if cancel.is_set():
                        raise ConversionCancelled()
                    if task == "batch_check":
                        unchanged = bool(record and record.signature == signature and export_intact(record, record.target.parent.parent))
                        emit("checked", signature, unchanged, str(record.target) if unchanged else "")
                    else:
                        manifest = {}
                        target = export_document(result, vault, markdown, strip_page_markers=strip,
                                                 cleanup_removals=removals, manifest=manifest)
                        emit("exported", signature, str(target), manifest)
            except ConversionCancelled:
                emit("cancelled")
            except Exception as exc:
                emit("error", str(exc))
            continue
        try:
            match command:
                case ("convert", source, workspace, *option_args):
                    result = convert(Path(source), Path(workspace),
                                     lambda n, total: events.put(("progress", n, total)), cancel.is_set,
                                     options=option_args[0] if option_args else None, stage=lambda text: events.put(("stage", text)))
                    events.put(("converted", result))
                case ("render", request_id, source, page, dpi, destination):
                    rect = render(Path(source), page, Path(destination), dpi=dpi)
                    events.put(("rendered", request_id, page, destination, rect))
                case ("crop", source, workspace, page, bbox):
                    asset = make_crop(source, workspace, page, bbox)
                    events.put(("cropped", asset))
        except ConversionCancelled:
            events.put(("cancelled",))
        except Exception as exc:
            if command[0] == "render":
                events.put(("render_error", command[1], str(exc), traceback.format_exc()))
            else:
                events.put(("error", str(exc), traceback.format_exc()))
