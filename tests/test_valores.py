"""retrieval/valores.py: reglas de valores vigentes sobre el índice real."""
import pytest

from src.common.config import load_config

pytest.importorskip("bm25s")


@pytest.fixture(scope="module")
def valores():
    from src.index.cargar import cargar
    from src.retrieval.valores import ValoresRetriever

    try:
        idx = cargar(denso=False)
    except FileNotFoundError:
        pytest.skip("sin índice en corpus/index/")
    return ValoresRetriever(idx, load_config("configs/agentic.yaml"))


def test_cuantia_en_pesos_trae_el_smlmv(valores):
    ps = valores.search("Si un proceso declarativo tiene pretensiones por un monto de 30.000.000 COP ¿a qué cuantía corresponde?")
    assert [p.doc_id for p in ps] == ["decreto_159_2026"]
    assert ps[0].texto.startswith("Decreto 159 de 2026") and "$1.750.905" in ps[0].texto
    assert ps[0].fuente_query == "valores"


def test_uvt_y_transporte(valores):
    assert [p.doc_id for p in valores.search("¿Cuántas UVT ...?")] == ["resolucion_238_2025"]
    assert [p.doc_id for p in valores.search("auxilio de transporte")] == ["decreto_1470_2025"]


def test_sin_disparador_no_agrega(valores):
    assert valores.search("¿Qué es la acción de tutela?") == []
    assert valores.search("artículo 25 del Código General del Proceso") == []
