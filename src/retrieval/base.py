"""Interfaz de los recuperadores."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

import numpy as np

from src.common.types import Passage


class Retriever(ABC):
    """Busca pasajes para una consulta. Orden determinista: desempate por (doc_id, chunk_id).

    `mascara` (bool por chunk_id) restringe la búsqueda a las filas en True: las cuotas
    la usan para garantizar candidatos de norma primaria (src/retrieval/cuotas.py).
    """

    @abstractmethod
    def search(self, query: str, k: int, mascara: Optional[np.ndarray] = None) -> list[Passage]:
        raise NotImplementedError
