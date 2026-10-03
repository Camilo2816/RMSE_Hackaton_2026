"""Pipeline.retrieve con reranker: ≤ 10 pasajes, lookup primero, determinista (índice y GPU/CPU)."""
import pytest

from src.common import rutas
from src.common.config import load_config
from src.common.types import Question, Trace

if not (rutas.INDEX / "config.json").exists():
    pytest.skip("índice sin construir (python -m src.index.construir)", allow_module_level=True)

from src.pipelines.registry import build_pipeline  # noqa: E402

Q = Question(id=1, formato="semi_open",
             pregunta="¿Qué requisitos exige el artículo 1502 del Código Civil para que una persona se obligue?")


@pytest.fixture(scope="module")
def pipe():
    return build_pipeline(load_config("configs/baseline.yaml"), generador=False)


def _correr(pipe):
    trace = Trace(question_id=Q.id)
    return pipe.retrieve(Q, pipe.stages.planner.plan(Q), trace), trace


def test_retrieve_lookup_primero_y_tope(pipe):
    pasajes, trace = _correr(pipe)
    assert 0 < len(pasajes) <= 10
    assert (pasajes[0].doc_id, pasajes[0].articulo) == ("codigo_civil", "1502")
    assert trace.fused_passages == pasajes
    assert {"lookup", "retrieval", "rerank", "fusion"} <= set(trace.timings)


def test_retrieve_determinista(pipe):
    a, _ = _correr(pipe)
    b, _ = _correr(pipe)
    assert [(p.clave, round(p.score, 6)) for p in a] == [(p.clave, round(p.score, 6)) for p in b]


def test_reranker_reordena_por_score(pipe):
    """Orden del reranker, con el score × factor de vigencia (derogados e inexequibles bajan)."""
    _, trace = _correr(pipe)
    lista = trace.passages_by_query[Q.pregunta]
    assert len(lista) == 10
    factores = pipe.factor_vigencia
    ajustado = [round(p.score * factores.get(p.vigencia or "", 1.0), 6) for p in lista]
    assert ajustado == sorted(ajustado, reverse=True)
    assert all(p.vigencia for p in lista)  # el índice entrega la vigencia de cada fragmento
