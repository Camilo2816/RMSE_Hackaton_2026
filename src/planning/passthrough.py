"""Planner del BASELINE: la pregunta tal cual, sin LLM."""
from __future__ import annotations

from typing import Optional

from src.common.config import Config
from src.common.types import Question
from src.planning.base import QueryPlanner


class PassthroughPlanner(QueryPlanner):
    """Devuelve [pregunta] (+ texto de las opciones si es multiple_choice). Ignora feedback."""

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg

    def plan(self, question: Question, feedback: Optional[str] = None) -> list[str]:
        return [question.texto_busqueda()]
