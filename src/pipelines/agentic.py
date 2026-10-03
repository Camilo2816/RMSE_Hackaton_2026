"""AGÉNTICO: baseline + planner de subconsultas + bucle acotado.

pregunta → recuperación del baseline (pregunta tal cual) → ¿evidencia débil?
(texto libre, sin lookup, mejor score del reranker bajo el umbral) → si sí:
planner(subconsultas, N, con el motivo como feedback) → por subconsulta:
híbrido + reranker → fusión (≤ 10) → LLM genera JSON → verificador → si
EVIDENCIA_INSUFICIENTE y queda iteración: re-planear y generar de nuevo →
abstención (texto libre) / responder igual (cerradas) → respuesta.

El re-planeo se reserva a los casos en que la primera recuperación resulta
insuficiente (enunciado, B.5): las cerradas y las preguntas con buena
evidencia siguen exactamente el camino del baseline y no pagan la llamada
extra. Como máximo verification.max_iter re-planeos en total.

El bucle lo controla el código; el LLM no decide cuándo parar.
"""
from __future__ import annotations

from src.common.timing import timed
from src.common.types import Answer, Passage, Question, Trace, Verdict
from src.pipelines.baseline import BaselinePipeline
from src.verification.abstention import evidencia_debil

FEEDBACK_SIN_RESPUESTA = ("Con los pasajes recuperados no se pudo responder la pregunta. "
                          "Busca la regla aplicable con otros términos.")


class AgenticPipeline(BaselinePipeline):
    """Reutiliza retrieve/answer/finalize de Pipeline; cambia recuperar() y run()."""

    def _puede_replanear(self, trace: Trace) -> bool:
        return trace.iterations - 1 < self.cfg["verification"].get("max_iter", 0)

    def _replanear(self, question: Question, motivo: str, trace: Trace) -> list[Passage]:
        trace.iterations += 1
        trace.replan_reasons.append(motivo)
        with timed(trace, "planner"):
            queries = self.stages.planner.plan(question, motivo, trace.llm_calls)
        return self.retrieve(question, queries, trace)

    def recuperar(self, question: Question, trace: Trace) -> list[Passage]:
        passages = self.retrieve(question, [question.texto_busqueda()], trace)
        trace.iterations = 1
        motivo = evidencia_debil(question, passages, self.cfg)
        if motivo is not None and self._puede_replanear(trace):
            passages = self._replanear(question, motivo, trace)
        return passages

    def run(self, question: Question) -> tuple[Answer, Trace]:
        trace = Trace(question_id=question.id)
        passages = self.recuperar(question, trace)
        answer, verdict = self.answer(question, passages, trace)
        if (verdict == Verdict.EVIDENCIA_INSUFICIENTE and question.formato != "multiple_choice"
                and self._puede_replanear(trace)):
            passages = self._replanear(question, FEEDBACK_SIN_RESPUESTA, trace)
            trace.abstention_reason = None
            answer, verdict = self.answer(question, passages, trace)
        return self.finalize(question, answer, verdict, passages, trace), trace
