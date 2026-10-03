"""Carga el índice congelado de corpus/index/.

Verifica que cada parte (denso, BM25) se construyó sobre el mismo
fragmentos.jsonl que está en metadata.jsonl y con la versión actual del
tokenizador: un índice desalineado devolvería pasajes que no corresponden a sus
vectores, y la verificación en vivo no reproduciría la entrega.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Optional

import numpy as np

from src.common import io
from src.common.types import Passage
from src.index import tokenizar
from src.index.construir import BM25_DIR, CONFIG_INDEX, EMBEDDINGS, METADATA, sha256


@dataclass
class Indice:
    config: dict[str, Any]
    metadata: list[dict[str, Any]]  # fila i = chunk_id i
    embeddings: Optional[np.ndarray]  # float32 (n, dim), normalizados
    bm25: Optional[Any]  # bm25s.BM25

    def __len__(self) -> int:
        return len(self.metadata)

    def pasaje(self, chunk_id: int, score: float, fuente_query: Optional[str] = None) -> Passage:
        f = self.metadata[chunk_id]
        return Passage(doc_id=f["doc_id"], chunk_id=chunk_id, norma=f["norma"],
                       articulo=f.get("articulo"), texto=f["texto"], inicio=f.get("inicio"),
                       fin=f.get("fin"), score=float(score), fuente_query=fuente_query,
                       vigencia=f.get("vigencia"))


def _verificar(config: dict[str, Any], parte: str, huella: str) -> None:
    if parte not in config:
        raise FileNotFoundError(f"índice sin parte '{parte}': python -m src.index.construir --partes {parte}")
    if config[parte]["sha256_fragmentos"] != huella:
        raise ValueError(f"la parte '{parte}' no corresponde a metadata.jsonl; reconstruir el índice")


@lru_cache(maxsize=2)
def cargar(denso: bool = True, bm25: bool = True) -> Indice:
    """Índice de corpus/index/ (en caché: el pipeline, la API y los tests comparten una copia)."""
    config = io.read_json(CONFIG_INDEX)
    huella = sha256(METADATA)
    metadata = io.read_jsonl(METADATA)

    embeddings = None
    if denso:
        _verificar(config, "denso", huella)
        embeddings = np.load(EMBEDDINGS).astype(np.float32)
        if embeddings.shape[0] != len(metadata):
            raise ValueError(f"embeddings.npy tiene {embeddings.shape[0]} filas y metadata {len(metadata)}")

    modelo_bm25 = None
    if bm25:
        import bm25s

        _verificar(config, "bm25", huella)
        if config["bm25"]["tokenizador_version"] != tokenizar.VERSION:
            raise ValueError("el tokenizador cambió desde que se construyó BM25; reconstruir con --partes bm25")
        modelo_bm25 = bm25s.BM25.load(str(BM25_DIR))

    return Indice(config=config, metadata=metadata, embeddings=embeddings, bm25=modelo_bm25)
