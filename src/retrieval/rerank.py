"""Reordenamiento con cross-encoder abierto (bge-reranker-v2-m3)."""
from __future__ import annotations

from dataclasses import replace
from functools import lru_cache

from src.common.config import Config
from src.common.types import Passage
from src.retrieval.fusion import ordenar


@lru_cache(maxsize=1)
def cargar_modelo(nombre: str, max_length: int):
    import torch
    from sentence_transformers import CrossEncoder

    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if device == "cuda" else torch.float32
    return CrossEncoder(nombre, device=device, max_length=max_length, model_kwargs={"torch_dtype": dtype})


class Reranker:
    """Puntúa (consulta, pasaje) conjuntamente. Desempate estable por (doc_id, chunk_id).

    Con rerank.enabled = false el registry no construye Reranker (None). Reordena
    los `rerank.candidates` primeros del híbrido; el score del pasaje pasa a ser
    el del cross-encoder (sigmoide, 0–1), que es el que usa la abstención.
    """

    def __init__(self, cfg: Config) -> None:
        params = cfg["rerank"]
        self.batch_size = params.get("batch_size", 8)
        self.modelo = cargar_modelo(params["model"], params.get("max_length", 512))

    def rerank(self, query: str, passages: list[Passage], top_n: int) -> list[Passage]:
        if not passages:
            return []
        # Entrada en orden canónico: los lotes (y su relleno) no dependen del orden del híbrido.
        canonico = sorted(passages, key=lambda p: p.clave)
        scores = self.modelo.predict([(query, p.texto) for p in canonico], batch_size=self.batch_size,
                                     show_progress_bar=False, convert_to_numpy=True)
        return ordenar([replace(p, score=float(s)) for p, s in zip(canonico, scores)])[:top_n]
