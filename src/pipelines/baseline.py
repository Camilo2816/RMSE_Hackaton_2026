"""BASELINE: una sola pasada.

pregunta → planner(passthrough) → lookup + híbrido (denso + BM25, RRF) → reranker
→ ≤ 10 pasajes → LLM genera JSON → verificador filtra citas → respuesta
"""
from __future__ import annotations

from src.common.types import Answer, Question, Trace
from src.pipelines.base import Pipeline


class BaselinePipeline(Pipeline):
    def run(self, question: Question) -> tuple[Answer, Trace]:
        trace = Trace(question_id=question.id)
        queries = self.stages.planner.plan(question)
        passages = self.retrieve(question, queries, trace)
        answer, verdict = self.answer(question, passages, trace)
        return self.finalize(question, answer, verdict, passages, trace), trace
