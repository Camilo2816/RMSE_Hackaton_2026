"""Medición de tiempo por etapa.

Uso previsto:
    with timed(trace, "retrieval"):
        ...
Presupuesto objetivo: ≤ 10 s por pregunta en total.
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Iterator

from src.common.types import Trace


@contextmanager
def timed(trace: Trace, etapa: str) -> Iterator[None]:
    """Suma a trace.timings[etapa] los segundos del bloque (time.perf_counter)."""
    t0 = time.perf_counter()
    try:
        yield
    finally:
        trace.timings[etapa] = trace.timings.get(etapa, 0.0) + time.perf_counter() - t0
