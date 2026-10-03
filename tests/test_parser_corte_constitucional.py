"""Parser de la relatoría de la Corte Constitucional y segmentación de sentencias.

Página sintética con la estructura del HTML exportado de Word que publica la
relatoría: descriptores, encabezado, SENTENCIA, secciones en romanos, subtítulos
numerados, cierre con firmas, índice final, voto particular y notas al pie.
"""
import pytest

from src.ingest import segmentar
from src.ingest.parsers import corte_constitucional as cc

PAGINA = """<script language='JavaScript1.2' src='/relatoria/encabezado.js'></script>
<a href='/sentencias/2020/C-100-20.rtf'>C-100-20</a><div class='amplia'><br><hr>
<html><head><meta http-equiv=Content-Type content="text/html; charset=windows-1252">
<style>p.MsoNormal {margin:0}</style></head><body><div class=WordSection1>
<p class=MsoNormal>TEMAS-SUBTEMAS</p>
<p class=MsoNormal>Sentencia C-100/20</p>
<p class=MsoNormal>DERECHO DE PRUEBA-Alcance</p>
<p class=MsoNormal>La Corte reitera que el derecho de prueba integra el debido proceso.</p>
<p class=MsoHeader>REPÚBLICA DE COLOMBIA</p>
<p class=MsoHeader>CORTE CONSTITUCIONAL</p>
<p class=MsoNormal>Referencia: expediente D-99999</p>
<p class=MsoNormal>Demandante: Persona de Prueba</p>
<p class=MsoNormal>Magistrada ponente:</p>
<p class=MsoNormal>ANA MARÍA DE PRUEBA</p>
<p class=MsoNormal>Bogotá, D.C., diez (10) de marzo de dos mil veinte (2020)</p>
<p class=MsoNormal>SENTENCIA</p>
<p class=MsoNormal>I. ANTECEDENTES</p>
<p class=MsoNormal>El ciudadano demandó el artículo 1 de la Ley 1 de 2000.<a href="#_ftn1" name="_ftnref1">[1]</a></p>
<p class=MsoNormal>IV. INTERVENCIONES</p>
<p class=MsoNormal>13. Intervención ciudadana de Fulano</p>
<p class=MsoNormal>Fulano pidió declarar la exequibilidad.</p>
<p class=MsoNormal>VI. CONSIDERACIONES Y FUNDAMENTOS</p>
<p class=MsoNormal>2. PROBLEMA JURÍDICO</p>
<p class=MsoNormal>Corresponde a la Sala determinar si la norma viola el artículo 29 de la Constitución.</p>
<p class=MsoNormal>8. Síntesis de la decisión</p>
<p class=MsoNormal>La norma es compatible con la Carta.</p>
<p class=MsoNormal>VII. DECISIÓN</p>
<p class=MsoNormal>RESUELVE:</p>
<p class=MsoNormal>PRIMERO. Declarar EXEQUIBLE el artículo 1 de la Ley 1 de 2000.</p>
<p class=MsoNormal>Notifíquese, comuníquese y cúmplase.</p>
<p class=MsoNormal>ANA MARÍA DE PRUEBA</p>
<p class=MsoNormal>Magistrada</p>
<p class=MsoNormal>II. PRUEBAS SOLICITADAS POR LA SALA 16</p>
<p class=MsoNormal>I. ANTECEDENTES.............................. 3</p>
<p class=MsoNormal>SALVAMENTO DE VOTO DEL MAGISTRADO</p>
<p class=MsoNormal>JUAN DISIDENTE</p>
<p class=MsoNormal>Me aparto de la decisión mayoritaria.</p>
</div>
<div id=ftn1><p class=MsoFootnoteText>[1] Nota al pie que no debe entrar.</p></div>
</body></html>"""

DOC = {"doc_id": "sentencia_c_100_2020", "nombre_citable": "Sentencia C-100 de 2020",
       "tipo": "sentencia", "numero": "C-100", "anio": "2020",
       "organo_emisor": "Corte Constitucional", "canonico": ["jurisprudencia", "C-100", "2020"]}


@pytest.fixture
def estructura(tmp_path):
    (tmp_path / "C-100-20.htm").write_bytes(PAGINA.encode("cp1252"))
    est = cc.parsear_documento(tmp_path, ["C-100-20.htm"])
    return {**est, "parser": "corte_constitucional",
            "url": "https://www.corteconstitucional.gov.co/relatoria/2020/C-100-20.htm"}


def test_ficha(estructura):
    f = estructura["ficha"]
    assert f["ponentes"] == ["ANA MARÍA DE PRUEBA"]
    assert f["fecha"].startswith("Bogotá, D.C., diez (10) de marzo")
    assert f["referencia"] == "Referencia: expediente D-99999"
    assert any(x.startswith("PRIMERO. Declarar EXEQUIBLE") for x in f["resuelve"])
    assert estructura["descriptores"][0] == "DERECHO DE PRUEBA-Alcance"


def test_secciones(estructura):
    orden = [s["seccion"] for s in estructura["secciones"]]
    # Subtítulos numerados no abren sección; el índice final tras la decisión tampoco.
    assert orden == ["antecedentes", "intervenciones", "consideraciones", "decision",
                     "salvamento_voto"]
    cons = next(s for s in estructura["secciones"] if s["seccion"] == "consideraciones")
    assert "2. PROBLEMA JURÍDICO" in {p["sub"] for p in cons["parrafos"]}


def test_limpieza(estructura):
    todo = " ".join(p["texto"] for s in estructura["secciones"] for p in s["parrafos"])
    assert "Nota al pie" not in todo and "[1]" not in todo
    assert "Magistrada" not in todo.replace("Magistrada ponente", "")  # firmas fuera
    assert "......" not in todo


def test_segmentacion(estructura):
    frags = segmentar.fragmentos_sentencia(DOC, estructura)
    assert segmentar.verificar_encabezados(DOC, frags) == []
    assert all(f["texto"].startswith("Sentencia C-100 de 2020, Corte Constitucional. ") for f in frags)
    ficha = next(f for f in frags if f["seccion"] == "ficha")
    assert "Magistrado ponente: ANA MARÍA DE PRUEBA" in ficha["texto"]
    assert "Decisión: PRIMERO. Declarar EXEQUIBLE" in ficha["texto"]
    cons = next(f for f in frags if f["seccion"] == "consideraciones")
    assert "Consideraciones" in cons["texto"][:80]
    assert len({f["frag_id"] for f in frags}) == len(frags)
    assert all(f["articulo"] is None and f["seccion"] for f in frags)
