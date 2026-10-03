"""Planner AGÉNTICO: el LLM descompone la pregunta en N subconsultas."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from src.common.config import Config
from src.common.types import Question
from src.generation.llm import LLMClient, LLMError
from src.planning.base import QueryPlanner

PROMPT = Path(__file__).resolve().parents[1] / "generation" / "prompts" / "planner" / "subqueries.md"

# El orden de las propiedades es el orden de generación: el problema jurídico y
# las figuras van antes de las subconsultas (paso 1 del ciclo del enunciado, B.5).
# Medido en sample_50: sin ellos las subconsultas repiten el vocabulario del caso
# y 679 no recupera la Ley 1581; con ellos sí, por ~1 s más. Con thinking de
# Qwen3 no mejora y tarda 2–4 veces más.
_SCHEMA = {
    "type": "object",
    "properties": {
        "problema_juridico": {"type": "string"},
        "figuras_juridicas": {"type": "array", "items": {"type": "string"}},
        "subconsultas": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["problema_juridico", "figuras_juridicas", "subconsultas"],
}

MAX_PALABRAS = 25  # una subconsulta larga vuelve a ser la pregunta narrativa


def normalizar(subconsultas, question: Question, n: int) -> list[str]:
    """Hasta n subconsultas no vacías, sin duplicados ni copias de la pregunta, acotadas en palabras."""
    vistas = {" ".join(question.pregunta.lower().split())}
    out: list[str] = []
    for s in subconsultas if isinstance(subconsultas, list) else []:
        if not isinstance(s, str):
            continue
        s = " ".join(s.split()[:MAX_PALABRAS])
        clave = s.lower()
        if s and clave not in vistas:
            vistas.add(clave)
            out.append(s)
    return out[:n]


class SubqueryPlanner(QueryPlanner):
    """Prompt: src/generation/prompts/planner/subqueries.md.

    En el reintento recibe el feedback del verificador (p. ej. "no apareció el
    cuerpo normativo aplicable") para orientar las nuevas subconsultas.

    Las subconsultas solo alimentan la recuperación; nunca entran a la respuesta,
    así que una norma inventada por el planner no puede volverse una cita.
    Con planner.incluir_pregunta (por defecto true) la pregunta original va
    primero. Si el LLM falla, devuelve [pregunta]: la recuperación del baseline.
    """

    def __init__(self, llm: LLMClient, n: int, cfg: Config) -> None:
        self.llm = llm
        self.n = n
        self.incluir_pregunta = cfg["planner"].get("incluir_pregunta", True)
        self.plantilla = PROMPT.read_text(encoding="utf-8")

    def construir_prompt(self, question: Question, feedback: Optional[str]) -> str:
        retro = f"\n# Intento anterior\n\n{feedback}\n" if feedback else ""
        return self.plantilla.format(pregunta=question.pregunta.strip(), n=self.n, retroalimentacion=retro)

    def plan(self, question: Question, feedback: Optional[str] = None,
             calls: Optional[list] = None) -> list[str]:
        base = question.texto_busqueda()
        intentos: list = []
        salida: dict = {}
        try:
            salida = self.llm.complete_json(self.construir_prompt(question, feedback), _SCHEMA, "planner", intentos)
            subs = normalizar(salida.get("subconsultas"), question, self.n)
        except LLMError:
            subs = []
        if calls is not None:
            calls.extend({"etapa": "planner", **c} for c in intentos)
            if salida and calls:
                calls[-1]["figuras_juridicas"] = salida.get("figuras_juridicas")
        if not subs:
            return [base]
        return [base, *subs] if self.incluir_pregunta else subs
