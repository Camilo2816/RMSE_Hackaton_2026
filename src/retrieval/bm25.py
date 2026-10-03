"""Recuperación léxica con bm25s y stemmer Snowball español (tokenización en src/index/tokenizar.py)."""
from __future__ import annotations

from typing import Optional

import numpy as np

from src.common.config import Config
from src.common.types import Passage
from src.index.cargar import Indice
from src.index.tokenizar import tokenizar
from src.retrieval.base import Retriever
from src.retrieval.fusion import ordenar
from src.retrieval.relatoria import mascara_bm25


class BM25Retriever(Retriever):
    def __init__(self, index: Indice, cfg: Config) -> None:
        if index.bm25 is None:
            raise ValueError("el índice se cargó sin la parte BM25")
        self.index = index
        self.vocab = index.bm25.vocab_dict
        self.mascara = mascara_bm25(index, cfg)  # None: todo el índice (lookup usa index.bm25 sin máscara)

    def search(self, query: str, k: int, mascara: Optional[np.ndarray] = None) -> list[Passage]:
        tokens = [t for t in tokenizar(query) if t in self.vocab]
        if not tokens:
            return []
        scores = np.asarray(self.index.bm25.get_scores(tokens), dtype=np.float32)
        validas = self.mascara if mascara is None else mascara if self.mascara is None else self.mascara & mascara
        if validas is not None:
            scores = np.where(validas, scores, np.float32(0))
        positivos = int((scores > 0).sum())
        k = min(k, positivos)
        if k == 0:
            return []
        m = min(k + 20, positivos)
        cand = np.argpartition(-scores, m - 1)[:m] if m < len(scores) else np.arange(len(scores))
        pasajes = [self.index.pasaje(int(i), float(scores[i]), query) for i in cand if scores[i] > 0]
        return ordenar(pasajes)[:k]
