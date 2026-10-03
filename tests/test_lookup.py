"""retrieval/lookup.py: normas y artículos nombrados en la consulta (solo si el índice existe)."""
import pytest

from src.common import rutas
from src.common.config import load_config

if not (rutas.INDEX / "config.json").exists():
    pytest.skip("índice sin construir (python -m src.index.construir)", allow_module_level=True)

from src.index.cargar import cargar  # noqa: E402
from src.retrieval.lookup import LookupRetriever  # noqa: E402

CFG = load_config("configs/baseline.yaml")


@pytest.fixture(scope="module")
def lk():
    return LookupRetriever(cargar(denso=False, bm25=True), CFG)


def test_articulo_nombrado_primero(lk):
    ps = lk.search("¿Qué establece el artículo 1502 del Código Civil?", 10)
    assert (ps[0].doc_id, ps[0].articulo) == ("codigo_civil", "1502")
    assert all(p.fuente_query == "lookup" for p in ps)


def test_varios_articulos_y_tope_de_partes(lk):
    ps = lk.search("artículos 1502 y 1503 del Código Civil", 10)
    assert [p.articulo for p in ps] == ["1502", "1503"]
    assert len(lk.search("artículo 240 del Estatuto Tributario", 10)) <= CFG["lookup"]["partes_por_articulo"]


def test_articulos_compuestos(lk):
    assert {p.articulo for p in lk.search("art. 240-1 del Estatuto Tributario", 10)} == {"240-1"}
    ps = lk.search("artículo 1.1.1.1 del Decreto 1072 de 2015", 10)
    assert (ps[0].doc_id, ps[0].articulo) == ("decreto_1072_2015", "1.1.1.1")


def test_sentencia_nombrada_trae_la_ficha(lk):
    ps = lk.search("En la Sentencia C-355 de 2006, ¿cuál fue el problema jurídico?", 10)
    assert ps[0].doc_id == "sentencia_c_355_2006" and "Ficha" in ps[0].texto[:60]
    assert all(p.doc_id == "sentencia_c_355_2006" for p in ps)


def test_constitucion_de_la_sociedad_no_es_la_constitucion(lk):
    assert lk.search("Requisitos para la constitución de la sociedad por acciones simplificada", 10) == []
    assert lk.search("¿Qué dice el artículo 86 de la Constitución Política?", 10)[0].articulo == "86"


def test_sin_normas_y_tope(lk):
    assert lk.search("contrato de arrendamiento de vivienda urbana", 10) == []
    q = "artículos 1502, 1503, 1504, 1505 y 1506 del Código Civil"
    assert len(lk.search(q, 10)) == CFG["lookup"]["max_hits"]
    assert lk.search(q, 10) == lk.search(q, 10)
