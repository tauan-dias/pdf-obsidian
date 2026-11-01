"""Inspeciona células de tabelas sintéticas sem carregar OCR."""
import json
import tempfile
from pathlib import Path
import pymupdf


def main():
    results = []
    with tempfile.TemporaryDirectory(prefix="native-tables-") as folder:
        for borders in (False, True, "merged"):
            path = Path(folder) / f"table-{borders}.pdf"
            with pymupdf.open() as doc:
                page = doc.new_page()
                for row in range(5):
                    for col in range(3):
                        if not (borders == "merged" and row == 0 and col == 1):
                            page.insert_text((55 + col * 130, 95 + row * 30), f"R{row}C{col}")
                if borders:
                    for row in range(6):
                        page.draw_line((45, 75 + row * 30), (435, 75 + row * 30))
                    for col in range(4):
                        top = 105 if borders == "merged" and col == 1 else 75
                        page.draw_line((45 + col * 130, top), (45 + col * 130, 225))
                doc.save(path)
            try:
                import onnxruntime
                onnxruntime.disable_telemetry_events()
                from markitdown import MarkItDown
            except ImportError:
                pass
            else:
                results.append(dict(borders=borders, engine="markitdown",
                                    markdown=MarkItDown(enable_plugins=False).convert_local(str(path)).markdown))
            with pymupdf.open(path) as doc:
                for strategy in ("lines", "text"):
                    tables = doc[0].find_tables(strategy=strategy, use_layout=False).tables
                    results.append(dict(borders=borders, strategy=strategy,
                                        cells=[table.extract() for table in tables]))
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
