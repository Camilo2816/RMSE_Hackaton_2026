"""Parser del Gestor Normativo de Función Pública, sobre una página sintética."""
import pytest

from src.ingest import fuentes, segmentar
from src.ingest.parsers import funcion_publica as fp

PAGINA = """<!doctype html><html><head>
<meta http-equiv="Content-Type" content="text/html; charset=ISO-8859-1" /><meta charset="utf-8">
<title>Ley 9 de 1990 - Gestor Normativo</title></head><body>
<div class="descripcion-contenido">
<p>LEY 9 DE 1990</p>
<p>por la cual se prueba el parser.</p>
<p>DECRETA:</p>
<p>TÍTULO I</p>
<p>DISPOSICIONES GENERALES</p>
<p><strong><em>ARTÍCULO <a id="1"></a>1. </em></strong>Objeto de la ley.</p>
<p>NOTA: Artículo declarado EXEQUIBLE por la Corte Constitucional mediante Sentencia C-100 de 2020.</p>
<p>ARTÍCULO 2º. El artículo 23 del Código Sustantivo del Trabajo quedará así:</p>
<p>Artículo 23. Elementos esenciales.</p>
<p>Artículo 3o</p>
<p>. Modificado por el art. 1, Ley 979 de 2005. Texto del tercero.</p>
<ol><li>primer literal;</li><li>segundo literal.</li></ol>
<p>ARTÍCULO 4. La presente ley rige desde su promulgación.</p>
<p>Dada en Bogotá, D.E., a 28 de diciembre de 1990.</p>
<p>FULANO DE TAL</p>
</div></body></html>"""

DOC = {"doc_id": "ley_9_1990", "nombre_citable": "Ley 9 de 1990", "tipo": "ley", "numero": "9",
       "anio": "1990", "organo_emisor": "Congreso de la República", "canonico": ["ley", "9", "1990"]}


@pytest.fixture
def estructura(tmp_path):
    (tmp_path / "norma.php").write_bytes(PAGINA.encode("utf-8"))
    return {**fp.parsear_documento(tmp_path, ["norma.php"]), "parser": "funcion_publica",
            "url": "https://www.funcionpublica.gov.co/eva/gestornormativo/norma.php?i=1"}


def test_articulos(estructura):
    arts = {a["articulo"]: a for a in estructura["articulos"]}
    assert list(arts) == ["1", "2", "3", "4"]  # "Artículo 23." citado no abre artículo
    assert arts["2"]["parrafos"][1] == "Artículo 23. Elementos esenciales."
    assert arts["3"]["parrafos"][0].startswith("Artículo 3o Modificado por el art. 1")
    assert "primer literal;" in arts["3"]["parrafos"]
    assert arts["1"]["ruta"] == ["TÍTULO I. DISPOSICIONES GENERALES"]
    assert "Sentencia C-100 de 2020" in arts["1"]["notas"]["notas de vigencia"][0]
    assert estructura["epigrafe"] == "por la cual se prueba el parser."


def test_utf8_y_firmas(estructura):
    todo = " ".join(p for a in estructura["articulos"] for p in a["parrafos"])
    assert "ARTÍCULO" in todo and "Ã" not in todo  # UTF-8 aunque declare ISO-8859-1
    assert "FULANO" not in todo and "Dada en" not in todo


def test_numeracion_decretos_unicos():
    assert fp._numero("ARTÍCULO 2.2.1.1.1.1. Objeto.") == "2.2.1.1.1.1"
    assert fp._sigue_secuencia((2, 2, 1, 2), (2, 2, 1, 1))
    assert not fp._sigue_secuencia((1, 1, 1), (2, 2, 1, 1))
    assert not fp._sigue_secuencia((78,), (7,))
    assert not fp._sigue_secuencia((2, 2, 4, 1), (1,))  # decreto corto que reproduce un DUR


def test_segmenta(estructura):
    frags = segmentar.fragmentos_ley(DOC, estructura)
    assert segmentar.verificar_encabezados(DOC, frags) == []
    art1 = next(f for f in frags if f["articulo"] == "1")
    assert "Notas de vigencia:" in art1["texto"]
    # La nota hace que la sentencia cuente como respaldo del pasaje.
    assert ("jurisprudencia", "C-100", "2020") in fuentes.canonico_de(art1["texto"])


def test_articulo_1_sin_ancla_tras_decreta(tmp_path):
    """"DECRETA:" es la fórmula de promulgación: el artículo 1 sin ancla que la sigue sí abre artículo
    (Decreto 1572 de 2024, salario mínimo). "… quedará así:" sigue sin abrirlo."""
    pagina = PAGINA.replace('<p><strong><em>ARTÍCULO <a id="1"></a>1. </em></strong>Objeto de la ley.</p>',
                            "<p><strong>ARTÍCULO 1. Salario mínimo.</strong> Fijar la suma de $1.423.500.</p>")
    pagina = pagina.replace("<p>TÍTULO I</p>\n<p>DISPOSICIONES GENERALES</p>\n", "")
    (tmp_path / "norma.php").write_bytes(pagina.encode("utf-8"))
    arts = [a["articulo"] for a in fp.parsear_documento(tmp_path, ["norma.php"])["articulos"]]
    assert arts[0] == "1" and "23" not in arts
