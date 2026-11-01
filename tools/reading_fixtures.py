"""Entradas sintéticas compartilhadas pelos testes e pela comparação."""
import pymupdf


def generate(root):
    cases = []
    for name, columns, title, rotation in (
            ("single", ((40, "A"),), False, 0),
            ("balanced", ((40, "A"), (330, "B")), False, 0),
            ("asymmetric", ((40, "A"), (230, "B")), False, 0),
            ("title", ((40, "A"), (330, "B")), True, 0),
            ("crop", ((40, "A"), (330, "B")), False, 0)):
        source = root / (name + ".pdf")
        expected = []
        with pymupdf.open() as doc:
            page = doc.new_page()
            if title:
                page.insert_text((40, 60), "Titulo transversal de uma pagina sintetica para estudo", fontsize=18)
            for x, side in columns:
                for i in range(6):
                    token = f"COLUNA{side}TRECHO{i}"
                    expected.append(token)
                    page.insert_text((x, 100 + i * 30), token + ".")
            if name == "crop":
                page.set_cropbox(pymupdf.Rect(10, 10, 585, 832))
            page.set_rotation(rotation)
            doc.save(source)
        cases.append((name, source, expected))
    return cases
