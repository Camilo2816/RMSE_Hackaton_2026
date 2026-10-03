"""Recuperación densa con el encoder de cfg["retrieval"]["encoder"] (bge-m3 / e5).

Si el encoder es E5, las consultas llevan el prefijo "query: ". Búsqueda exacta:
producto interno contra la matriz normalizada (equivale a FAISS IndexFlatIP).

`retrieval.denso_relatoria_secciones` (src/retrieval/relatoria.py): la relatoría
cosechada solo entra al denso con esas secciones. Como la búsqueda es exacta, la
máscara equivale a indexar solo esas filas.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

import numpy as np

from src.common.config import Config
from src.common.types import Passage
from src.index.cargar import Indice
from src.retrieval.base import Retriever
from src.retrieval.fusion import ordenar
from src.retrieval.relatoria import mascara_denso


@lru_cache(maxsize=2)
def cargar_encoder(nombre: str, max_seq_length: int, dtype: str):
    """Encoder de consultas, cargado una sola vez y con el mismo dtype del índice."""
    import torch
    from sentence_transformers import SentenceTransformer

    device = "cuda" if torch.cuda.is_available() else "cpu"
    torch_dtype = getattr(torch, dtype) if device == "cuda" else torch.float32
    modelo = SentenceTransformer(nombre, device=device, model_kwargs={"torch_dtype": torch_dtype})
    modelo.max_seq_length = max_seq_length
    return modelo


class DenseRetriever(Retriever):
    def __init__(self, index: Indice, cfg: Config) -> None:
        if index.embeddings is None:
            raise ValueError("el índice se cargó sin la parte densa")
        meta = index.config["denso"]
        if meta["encoder"] != cfg["retrieval"]["encoder"]:
            raise ValueError(f"el índice usa {meta['encoder']} y la config pide {cfg['retrieval']['encoder']}")
        self.index = index
        self.prefijo = meta["prefijos"]["query"]
        self.encoder = cargar_encoder(meta["encoder"], meta["max_seq_length"], meta["dtype_modelo"])
        self.mascara = mascara_denso(index, cfg)  # None: todo el índice

    def embed(self, query: str) -> np.ndarray:
        vec = self.encoder.encode([self.prefijo + query], batch_size=1, normalize_embeddings=True,
                                  convert_to_numpy=True, show_progress_bar=False)
        return vec[0].astype(np.float32)

    def search(self, query: str, k: int, mascara: Optional[np.ndarray] = None) -> list[Passage]:
        scores = self.index.embeddings @ self.embed(query)
        validas = self.mascara if mascara is None else mascara if self.mascara is None else self.mascara & mascara
        if validas is not None:
            scores = np.where(validas, scores, -np.inf)
        k = min(k, len(scores) if validas is None else int(validas.sum()))
        if k == 0:
            return []
        # Candidatos con margen para que el corte en k no dependa del orden de empates.
        cand = np.argpartition(-scores, min(k + 20, len(scores) - 1))[: k + 20]
        pasajes = [self.index.pasaje(int(i), float(scores[i]), query) for i in cand if np.isfinite(scores[i])]
        return ordenar(pasajes)[:k]

