"""Planner que reescribe la consulta con terminología jurídica (una sola consulta)."""
from __future__ import annotations

from typing import Optional

from src.common.config import Config
from src.common.types import Question
from src.generation.llm import LLMClient
from src.planning.base import QueryPlanner


class ReformulatePlanner(QueryPlanner):
    """Prompt: src/generation/prompts/planner/reformulate.md."""

    def __init__(self, llm: LLMClient, cfg: Config) -> None:
        raise NotImplementedError

    def plan(self, question: Question, feedback: Optional[str] = None) -> list[str]:
        raise NotImplementedError
