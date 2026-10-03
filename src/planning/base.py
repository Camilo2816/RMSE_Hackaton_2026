"""Interfaz del planner: convierte una pregunta en consultas de recuperación."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.common.types import Question


class QueryPlanner(ABC):
    """Etapa 1 del pipeline."""

    @abstractmethod
    def plan(self, question: Question, feedback: Optional[str] = None) -> list[str]:
        """Consultas para el recuperador.

        feedback: descripción de por qué la evidencia fue insuficiente en la
        iteración anterior (solo en el re-planeo agéntico).
        """
        raise NotImplementedError
