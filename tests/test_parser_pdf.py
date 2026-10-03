"""Parser de normas en PDF (Decisiones Andinas), sobre un PDF sintético."""
import pymupdf
import pytest

from src.ingest import segmentar
from src.ingest.parsers import pdf

# Como en los PDF reales de la CAN: párrafos separados por líneas con un espacio,
# el nombre del título en su propio párrafo y literales "a)" en línea aparte.
_P = "\n \n".join
TEXTO = [
    _P(["DECISION 999", "Régimen de Prueba", "LA COMISION DE LA COMUNIDAD ANDINA,", "DECIDE:",
        "TITULO I", "DISPOSICIONES GENERALES", "Del Objeto",
        "Artículo 1.- Esta Decisión regula la prueba\ncon líneas partidas.",
        "Artículo 2.- No podrán registrarse los signos que:", "a)", "carezcan de distintividad;",
        "- 2 -"]),
    _P(["CAPITULO I", "DE LAS MARCAS", "Artículo 3.- Texto del tercero.",
        "DISPOSICIONES TRANSITORIAS", "PRIMERA.- Régimen de transición.",
        "Dada en la ciudad de Lima, Perú, a los catorce días del mes de septiembre."]),
]


@pytest.fixture
def estructura(tmp_path):
    doc = pymupdf.open()
    for t in TEXTO:
        doc.new_page().insert_text((50, 60), t, fontsize=9)
    doc.save(tmp_path / "DEC999.pdf")
    return {**pdf.parsear_documento(tmp_path, ["DEC999.pdf"]), "parser": "pdf",
            "url": "https://www.comunidadandina.org/StaticFiles/DocOf/DEC999.pdf"}


def test_articulos_y_ruta(estructura):
    arts = {a["articulo"]: a for a in estructura["articulos"]}
    assert list(arts) == ["1", "2", "3", "TRANSITORIA PRIMERA"]
    assert arts["1"]["ruta"] == ["TITULO I. DISPOSICIONES GENERALES", "Del Objeto"]
    assert arts["3"]["ruta"] == ["TITULO I. DISPOSICIONES GENERALES", "CAPITULO I. DE LAS MARCAS"]
    assert arts["1"]["parrafos"] == ["Artículo 1.- Esta Decisión regula la prueba con líneas partidas."]
    assert "a) carezcan de distintividad;" in arts["2"]["parrafos"]
    assert estructura["epigrafe"] == "Régimen de Prueba"
    assert estructura["qa"]["n_parrafos_firma"] == 1


def test_sin_numeros_de_pagina_ni_simbolos(estructura):
    todo = " ".join(p for a in estructura["articulos"] for p in a["parrafos"])
    assert "- 2 -" not in todo and "Dada en" not in todo
    assert pdf._sin_simbolos("") == "DEC"


def test_segmenta_como_ley(estructura):
    doc = {"doc_id": "decision_999", "nombre_citable": "Decisión 999 de la Comunidad Andina",
           "tipo": "decision_andina", "canonico": None}
    frags = segmentar.fragmentos_ley(doc, estructura)
    assert all(f["texto"].startswith("Decisión 999 de la Comunidad Andina. ") for f in frags)
    assert {f["articulo"] for f in frags} >= {"1", "2", "3", "TRANSITORIA PRIMERA"}
