"""Parser del Senado y segmentación, sobre una página sintética con los casos difíciles.

No usa red: reproduce la estructura real de basedoc (marcadores de documento,
anclas bookmarkaj, títulos centrados, notas en JS compañero, tachados, firmas).
"""
import json

import pytest

from src.common import rutas
from src.ingest import fuentes, segmentar
from src.ingest.parsers import senado

PAGINA = """<html><head><meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1"></head>
<body><script>var inyectado = "ARTICULO 999. basura de un proxy";</script>
<p>Índice: ARTICULO 1 ARTICULO 2</p>
<!--Inicio documento-->
<p style="text-align:center;"><a class=antsig href="ley_0001_2000_pr001.html">Siguiente</a></p>
<p>LEY 1 DE 2000</p>
<p>Por la cual se prueba el parser.</p>
<div><a class="caja_vja_encabezado" href="javascript:insRow1()">Resumen de Notas de Vigencia</a></div>
<table id="Table1" class="caja_vja_v" cellPadding=10 width="100%"></table>
<p class="centrado"><a class="bookmarkaj" name="T&Iacute;TULO I">T&Iacute;TULO I. </A></p>
<p class="centrado"><span class="b_aj">DISPOSICIONES GENERALES. </span></p>
<p><a class="bookmarkaj" name="1">ART&Iacute;CULO 1o. OBJETO.</A> Esta ley tiene objeto. <s>Texto tachado.</s> Sigue vigente.</p>
<div><a class="caja_vja_encabezado" href="javascript:insRow2()">Notas de Vigencia</a></div>
<table id="Table2" class="caja_vja_v" cellPadding=10 width="100%"></table>
<div><a class="caja_vja_encabezado" href="javascript:insRow3()">Legislaci&oacute;n Anterior</a></div>
<table id="Table3" class="caja_vja_la" cellPadding=10 width="100%"></table>
<p>ART&Iacute;CULO 2o. SIN ANCLA. El Senado no le puso ancla a este art&iacute;culo.</p>
<p><a class="bookmarkaj" name="3">ART&Iacute;CULO 3o. REFORMA.</A> Modif&iacute;case el art&iacute;culo 50 de la Ley 9 de 1999, el cual quedar&aacute; as&iacute;:</p>
<p>ART&Iacute;CULO 50. Texto citado de otra ley.</p>
<p>Art&iacute;culo 199. Otro citado, en min&uacute;scula.</p>
<p><a class="bookmarkaj" name="T1">ARTICULO TRANSITORIO 1o.</A> Transitorio.</p>
<p class="centrado">El Presidente del honorable Senado de la Rep&uacute;blica,</p>
<p>FULANO DE TAL</p>
<!--Fin documento-->
</body></html>"""

JS = """function insRow1()
{
var description = new Array();
description[0] = "<tbody><tr><td><p>- Modificada por la Ley 2 de 2001.</p> </td></tr></tbody>";
var z=document.getElementById('Table1').rows[0];
}
function insRow2()
{
var description = new Array();
description[0] = "<tbody><tr><td><p>- Art&iacute;culo modificado por el art&iacute;culo 5 de la Ley 3 de 2002.</p></td></tr></tbody>";
var z=document.getElementById('Table2').rows[0];
}
function insRow3()
{
var description = new Array();
description[0] = "<tbody><tr><td><p>ART&Iacute;CULO 1. Texto viejo que no debe entrar.</p></td></tr></tbody>";
var z=document.getElementById('Table3').rows[0];
}
"""

DOC = {"doc_id": "ley_1_2000", "nombre_citable": "Ley 1 de 2000", "tipo": "ley", "numero": "1",
       "anio": "2000", "organo_emisor": "Congreso de la República",
       "canonico": ["ley", "1", "2000"]}


@pytest.fixture
def estructura(tmp_path):
    (tmp_path / "js").mkdir()
    (tmp_path / "ley_0001_2000.html").write_bytes(PAGINA.encode("cp1252"))
    (tmp_path / "js" / "ley_0001_2000.js").write_bytes(JS.encode("cp1252"))
    est = senado.parsear_documento(tmp_path, ["ley_0001_2000.html"])
    return {**est, "parser": "senado",
            "url": "http://www.secretariasenado.gov.co/senado/basedoc/ley_0001_2000.html"}


def _todo(est) -> str:
    return json.dumps(est, ensure_ascii=False)


def test_articulos_detectados(estructura):
    assert [a["articulo"] for a in estructura["articulos"]] == ["1", "2", "3", "TRANSITORIO 1"]
    assert estructura["qa"]["sin_ancla_aceptados"] == ["2"]


def test_citados_no_abren_articulo(estructura):
    art3 = estructura["articulos"][2]["parrafos"]
    assert any(p.startswith("ARTÍCULO 50.") for p in art3)
    assert any(p.startswith("Artículo 199.") for p in art3)


def test_limpieza(estructura):
    texto = _todo(estructura)
    assert "Texto tachado" not in texto
    assert "basura de un proxy" not in texto
    assert "Índice" not in texto
    assert "FULANO" not in json.dumps(estructura["articulos"], ensure_ascii=False)
    # La legislación anterior se conserva como metadato, pero no entra al texto indexado.
    assert "legislación anterior" in estructura["articulos"][0]["notas"]
    frags = segmentar.fragmentos_ley(DOC, estructura)
    assert not any("Texto viejo" in f["texto"] for f in frags)


def test_ruta_epigrafe_y_notas(estructura):
    art1 = estructura["articulos"][0]
    assert art1["ruta"] == ["TÍTULO I. DISPOSICIONES GENERALES"]
    assert estructura["epigrafe"] == "Por la cual se prueba el parser."
    assert "Ley 3 de 2002" in art1["notas"]["notas de vigencia"][0]
    assert "Ley 2 de 2001" in estructura["preambulo"]["notas"]["resumen de notas de vigencia"][0]


def test_numero_articulo():
    casos = {"ARTICULO 1o. OBJETO": "1", "ARTÍCULO 240-1. X": "240-1", "ARTÍCULO 5A. X": "5A",
             "ARTÍCULO 26 BIS. X": "26 BIS", "ARTICULO TRANSITORIO 3o. X": "TRANSITORIO 3",
             "ARTÍCULO TRANSITORIO. X": "TRANSITORIO", "Artículo 10°. X": "10",
             "ARTICULADO del código": None}
    for texto, esperado in casos.items():
        assert senado.numero_articulo(texto) == esperado, texto


def test_segmentacion_y_offsets(estructura, tmp_path, monkeypatch):
    monkeypatch.setattr(rutas, "PROCESSED", tmp_path / "processed")
    monkeypatch.setattr(rutas, "FRAGMENTOS_DIR", tmp_path / "processed" / "fragmentos")
    frags = segmentar.fragmentos_ley(DOC, estructura)
    assert segmentar.verificar_encabezados(DOC, frags) == []
    assert all(f["texto"].startswith("Ley 1 de 2000. ") for f in frags)
    segmentar.escribir_documento(DOC, frags)
    txt = (tmp_path / "processed" / "ley_1_2000.txt").read_text(encoding="utf-8")
    for f in frags:
        assert txt[f["inicio"]:f["fin"]] == f["texto"]
    art1 = next(f for f in frags if f["articulo"] == "1")
    assert art1["vigencia"] == "modificado"
    assert "Notas de vigencia: Artículo modificado por el artículo 5 de la Ley 3 de 2002" in art1["texto"]
    # La nota hace que la ley modificatoria cuente como respaldo del pasaje.
    assert ["ley", "3", "2002"] in art1["cuerpos"]


def test_articulo_largo_se_parte_con_encabezado(estructura):
    largo = dict(estructura)
    largo["articulos"] = [{"articulo": "7", "ruta": [], "notas": {}, "pagina": "x.html",
                           "parrafos": ["ARTÍCULO 7. LARGO."] + [("Frase de prueba. " * 60)] * 4}]
    frags = segmentar.fragmentos_ley(DOC, largo)
    arts = [f for f in frags if f["articulo"] == "7"]
    assert len(arts) > 1 and all(f["n_partes"] == len(arts) for f in arts)
    assert "ARTÍCULO 7 (continuación)" in arts[1]["texto"]
    assert all(len(f["texto"]) <= segmentar.MAX_CHARS for f in arts)
    assert segmentar.verificar_encabezados(DOC, arts) == []


@pytest.mark.parametrize("inicio_anexo", [
    '<p class="centrado"><span class="b_aj"><A name="SENTENCIA C-748-11">SENTENCIA C-748-11.</A> </span></p>',
    '<p class="centrado">Corte Constitucional</p><p class="centrado">SENTENCIA N&Uacute;MERO C-274 DE 2013</p>',
])
def test_sentencia_transcrita_tras_las_firmas_no_entra(tmp_path, inicio_anexo):
    """Leyes estatutarias (1581, 1712): el Senado copia la sentencia de control previo tras
    las firmas. Sus "TÍTULO I" y "ARTÍCULO 4" no reabren el articulado ni se pegan al último artículo."""
    anexo = (inicio_anexo + '<p class="centrado">T&Iacute;TULO I</p><p class="centrado">DE LA SENTENCIA</p>'
             '<p>Art&iacute;culo 1&deg;. Texto del proyecto dentro de la sentencia.</p>'
             '<p><a class="bookmarkaj" name="4">ART&Iacute;CULO 4.</A> Ancla dentro de la sentencia.</p>')
    pagina = PAGINA.replace("<!--Fin documento-->", anexo + "\n<!--Fin documento-->")
    (tmp_path / "js").mkdir()
    (tmp_path / "ley_0001_2000.html").write_bytes(pagina.encode("cp1252"))
    (tmp_path / "js" / "ley_0001_2000.js").write_bytes(JS.encode("cp1252"))
    est = senado.parsear_documento(tmp_path, ["ley_0001_2000.html"])
    assert [a["articulo"] for a in est["articulos"]] == ["1", "2", "3", "TRANSITORIO 1"]
    assert "sentencia" not in _todo(est["articulos"]).lower()
    assert est["qa"]["anexo_descartado"].upper().startswith(("SENTENCIA C-", "CORTE CONSTITUCIONAL"))
