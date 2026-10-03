"""Índice de corpus/index/ y recuperadores (solo si el índice ya se construyó)."""
import pytest

from src.common import rutas
from src.common.config import load_config

if not (rutas.INDEX / "config.json").exists():
    pytest.skip("índice sin construir (python -m src.index.construir)", allow_module_level=True)

from src.index.cargar import cargar  # noqa: E402
from src.retrieval.bm25 import BM25Retriever  # noqa: E402

CFG = load_config("configs/baseline.yaml")


def test_filas_alineadas():
    idx = cargar(denso=False, bm25=True)
    assert all(f["chunk_id"] == i for i, f in enumerate(idx.metadata))
    assert idx.config["n_fragmentos"] == len(idx)


def test_bm25_trae_la_norma_nombrada():
    bm25 = BM25Retriever(cargar(denso=False, bm25=True), CFG)
    pasajes = bm25.search("Ley 472 de 1998 acciones populares y de grupo", 10)
    assert any(p.doc_id == "ley_472_1998" for p in pasajes)
    assert len(pasajes) == 10 and pasajes == bm25.search("Ley 472 de 1998 acciones populares y de grupo", 10)


def test_bm25_consulta_vacia():
    assert BM25Retriever(cargar(denso=False, bm25=True), CFG).search("de la los", 10) == []


def test_hibrido_determinista():
    if "denso" not in cargar(denso=False, bm25=True).config:
        pytest.skip("índice sin parte densa")
    from src.retrieval.dense import DenseRetriever
    from src.retrieval.hybrid import HybridRetriever

    idx = cargar(denso=True, bm25=True)
    h = HybridRetriever(DenseRetriever(idx, CFG), BM25Retriever(idx, CFG), CFG["retrieval"]["rrf_k"])
    q = "¿Cuál es el término para interponer la acción de tutela contra providencias judiciales?"
    a, b = h.search(q, 10), h.search(q, 10)
    assert len(a) == 10 and [p.clave for p in a] == [p.clave for p in b]
