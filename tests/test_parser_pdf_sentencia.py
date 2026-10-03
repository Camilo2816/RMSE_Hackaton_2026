"""Parser de sentencias de la Corte Suprema en PDF, sobre un PDF sintético."""
import pymupdf

from src.ingest.parsers import pdf_sentencia

PAGINAS = [
    ["JUAN PÉREZ GÓMEZ", "Magistrado ponente", "", "SL1234-2022", "Radicación n.° 99999", "Acta 26",
     "Bogotá, D. C., diez (10) de agosto de dos mil", "veintidós (2022).", "",
     "Decide la Sala el recurso de casación interpuesto por la", "demandante contra la sentencia del Tribunal.", "",
     "I. ANTECEDENTES", "", "La demandante pidió la pensión de", "sobrevivientes.", "2"],
    ["MARÍA LÓPEZ", "LA DEMANDA DE CASACIÓN", "", "CARGO PRIMERO", "",
     "Acusa la sentencia por vía directa.", "", "CONSIDERACIONES", "",
     "El accidente ocurrió en el trayecto al trabajo.", "3"],
    ["MARÍA LÓPEZ", "DECISIÓN", "", "En mérito de lo expuesto, la Corte NO CASA", "la sentencia.", "",
     "SALVAMENTO DE VOTO", "", "Me aparto de la decisión.", "4"],
    ["MARÍA LÓPEZ", "Firmas.", "5"],
]


def _pdf(tmp_path):
    doc = pymupdf.open()
    for lineas in PAGINAS:
        doc.new_page().insert_text((50, 60), "\n".join(lineas), fontsize=9)
    doc.save(tmp_path / "s.pdf")
    return pdf_sentencia.parsear_documento(tmp_path, ["s.pdf"])


def test_ficha(tmp_path):
    ficha = _pdf(tmp_path)["ficha"]
    assert ficha["ponentes"] == ["Juan Pérez Gómez"]
    assert ficha["referencia"] == "SL1234-2022"
    assert ficha["fecha"] == "Bogotá, D. C., diez (10) de agosto de dos mil veintidós (2022)"
    assert ficha["resuelve"] == ["En mérito de lo expuesto, la Corte NO CASA la sentencia."]


def test_secciones_y_encabezado_corrido(tmp_path):
    est = _pdf(tmp_path)
    secciones = {s["seccion"]: s["parrafos"] for s in est["secciones"]}
    assert list(secciones) == ["cuerpo", "antecedentes", "demanda", "consideraciones", "decision", "salvamento_voto"]
    assert secciones["antecedentes"][0]["texto"] == "La demandante pidió la pensión de sobrevivientes."
    assert secciones["demanda"][0] == {"texto": "Acusa la sentencia por vía directa.", "sub": "CARGO PRIMERO"}
    todo = " ".join(p["texto"] for ps in secciones.values() for p in ps)
    assert "MARÍA LÓPEZ" not in todo  # encabezado repetido en ≥ 3 páginas
    assert not est["qa"]["sin_decision"] and not est["qa"]["sin_texto"]
