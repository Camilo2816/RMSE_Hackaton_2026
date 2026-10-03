"""Recuperación híbrida: RRF entre DenseRetriever y BM25Retriever (usa fusion.rrf)."""
from __future__ import annotations

from typing import Optional

import numpy as np

from src.common.types import Passage
from src.retrieval.base import Retriever
from src.retrieval.bm25 import BM25Retriever
from src.retrieval.dense import DenseRetriever
from src.retrieval.fusion import rrf


class HybridRetriever(Retriever):
    """Cada recuperador trae top_k_per_query; se fusionan con RRF (rrf_k)."""

    def __init__(self, dense: DenseRetriever, bm25: BM25Retriever, rrf_k: int, top_k: int = 50) -> None:
        self.dense = dense
        self.bm25 = bm25
        self.rrf_k = rrf_k
        self.top_k = top_k

    def search(self, query: str, k: int, mascara: Optional[np.ndarray] = None) -> list[Passage]:
        n = max(k, self.top_k)
        return rrf([self.dense.search(query, n, mascara), self.bm25.search(query, n, mascara)], self.rrf_k)[:k]
