"""Decisión de abstención. La decide el código, nunca el LLM.

multiple_choice: nunca se abstiene (abstention.closed = never).
Texto libre: se abstiene si el veredicto es EVIDENCIA_INSUFICIENTE, que se da
- sin pasajes;
- si el mejor score del reranker queda bajo abstention.free_text_min_rerank_score
  (null = desactivado, por calibrar); estos dos se revisan antes de llamar al LLM;
- si el LLM devolvió vacía la respuesta principal (verifier.respuesta_vacia).
"""
from __future__ import annotations

from typing import Optional

from src.common.config import Config
from src.common.types import Passage, Question, Verdict


def mejor_score_rerank(passages: list[Passage]) -> Optional[float]:
    """Máximo score del cross-encoder; los hits del lookup (BM25) y los valores fijos no cuentan."""
    scores = [p.score for p in passages if p.fuente_query not in ("lookup", "valores")]
    return max(scores) if scores else None


def evidencia_insuficiente(question: Question, passages: list[Passage], cfg: Config) -> Optional[str]:
    """Motivo de abstención que se conoce antes de generar (texto libre), o None."""
    if question.formato == "multiple_choice":
        return None
    if not passages:
        return "sin_pasajes"
    umbral = cfg["abstention"].get("free_text_min_rerank_score")
    mejor = mejor_score_rerank(passages)
    if umbral is not None and mejor is not None and mejor < umbral:
        return "score_bajo"
    return None


MOTIVO_DEBIL = ("Ningún pasaje recuperado con la pregunta tal cual responde directamente. "
                "Busca la regla aplicable con otros términos.")


def evidencia_debil(question: Question, passages: list[Passage], cfg: Config) -> Optional[str]:
    """Motivo para re-planear antes de generar (agéntico), o None si la evidencia basta.

    Débil = texto libre, sin hits del lookup (la pregunta no nombra una norma que
    ya se haya traído) y el mejor score del reranker bajo
    verification.replan_min_rerank_score. Calibrado sobre sample_50 (35 ítems de
    texto libre): con 0,75 se activa en 8, entre ellos los dos fallos de
    recuperación (247: 0,61; 679: 0,62); el siguiente score por encima es 0,82.
    El motivo va al planner como retroalimentación. Es fijo a propósito: si
    listara las normas recuperadas, cualquier cambio en la primera pasada (p. ej.
    rerank.fusionar_con_hibrido) cambiaría las subconsultas (medido: 679 y 879
    pierden la norma).
    """
    umbral = cfg["verification"].get("replan_min_rerank_score")
    if umbral is None or question.formato == "multiple_choice" or not passages:
        return None
    if any(p.fuente_query == "lookup" for p in passages):
        return None
    mejor = mejor_score_rerank(passages)
    if mejor is not None and mejor >= umbral:
        return None
    return MOTIVO_DEBIL


def decide(question: Question, verdict: Verdict, passages: list[Passage], cfg: Config) -> bool:
    if question.formato == "multiple_choice":
        return False  # abstention.closed = never (enunciado: siempre elegir una letra)
    return verdict == Verdict.EVIDENCIA_INSUFICIENTE
