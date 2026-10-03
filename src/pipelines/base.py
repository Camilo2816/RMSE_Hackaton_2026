"""Pipeline con etapas intercambiables.

Stages agrupa las implementaciones elegidas por la config. Los pasos comunes
(recuperar, generar, verificar) viven aquí para que baseline y agentic no
dupliquen código: la diferencia está en las etapas y en el bucle.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from src.common.config import Config
from src.common.timing import timed
from src.common.types import Answer, Passage, Question, Trace, Verdict
from src.generation.answer import AnswerGenerator
from src.planning.base import QueryPlanner
from src.retrieval.base import Retriever
from src.retrieval.fusion import fuse, limitar_por_documento, penalizar_vigencia, reordenar_con
from src.retrieval.lookup import LookupRetriever
from src.retrieval.rerank import Reranker
from src.retrieval.cuotas import Cuotas
from src.retrieval.valores import ValoresRetriever


@dataclass
class Stages:
    planner: QueryPlanner
    lookup: Optional[LookupRetriever]  # None si lookup.enabled = false
    retriever: Retriever  # HybridRetriever
    reranker: Optional[Reranker]  # None si rerank.enabled = false
    generator: Optional[AnswerGenerator]  # None solo al medir la recuperación (eval/retrieval_ceiling.py)
    valores: Optional[ValoresRetriever] = None  # None si valores.enabled = false
    cuotas: Optional[Cuotas] = None  # None si cuotas.enabled = false
    jurisprudencia: Optional[object] = None  # JurisprudenciaPorNormas; None si jurisprudencia.enabled = false
    compresor: Optional[object] = None  # generation.compresion.Compresor; None si compresion.enabled = false
    extension: Optional[object] = None  # generation.extension.Extension; None si verification.extension.enabled = false


class Pipeline(ABC):
    def __init__(self, stages: Stages, cfg: Config) -> None:
        self.stages = stages
        self.cfg = cfg
        self.max_passages = cfg["fusion"]["max_passages"]
        self.candidatos = cfg["rerank"].get("candidates", 30)
        self.top_n = cfg["rerank"]["top_n"]
        self.max_por_documento = cfg["fusion"].get("max_por_documento")  # None: sin tope
        self.factor_vigencia = cfg["fusion"].get("factor_vigencia") or {}  # {}: sin penalización

    @abstractmethod
    def run(self, question: Question) -> tuple[Answer, Trace]:
        raise NotImplementedError

    def recuperar(self, question: Question, trace: Trace) -> list[Passage]:
        """Planificación + recuperación hasta los ≤ 10 pasajes que verá el LLM.

        Es lo que mide eval/retrieval_ceiling.py; el agéntico la sobrescribe con
        su re-planeo previo a la generación.
        """
        return self.retrieve(question, self.stages.planner.plan(question), trace)

    def retrieve(self, question: Question, queries: list[str], trace: Trace) -> list[Passage]:
        """Lookup + (híbrido + rerank + vigencia + tope por documento) por consulta + valores + fusion.fuse → ≤ 10 pasajes.

        Con tope o penalización de vigencia, el reranker devuelve todos los
        candidatos y se reordena antes de cortar en top_n: sobre los 10 primeros no
        habría alternativas donde elegir. El lookup no se penaliza: la pregunta
        nombra esa norma.
        """
        s = self.stages
        lookup_hits: list[Passage] = []
        if s.lookup is not None:
            with timed(trace, "lookup"):
                texto_bm25 = question.pregunta if self.cfg["lookup"].get("bm25_solo_pregunta") else None
                lookup_hits = s.lookup.search(question.texto_busqueda(), self.max_passages, texto_bm25)
            trace.passages_by_query["lookup"] = lookup_hits

        listas: dict[str, list[Passage]] = {}
        con_hibrido = s.reranker is not None and self.cfg["rerank"].get("fusionar_con_hibrido", False)
        vig = self.factor_vigencia
        for q in queries:
            tope = self.max_por_documento
            with timed(trace, "retrieval"):
                if s.cuotas is not None and s.reranker is not None:
                    # Preselección: los candidatos del reranker, con tope por tipo, de un híbrido 3 veces más largo.
                    cands = s.cuotas.aplicar(s.retriever.search(q, 3 * self.candidatos), q, self.candidatos,
                                             factor=self.candidatos / self.max_passages)
                    if s.cuotas.min_primarias:
                        # Con ~97 % de sentencias el híbrido puede no traer ninguna norma primaria.
                        primarias = s.retriever.search(q, s.cuotas.min_primarias, mascara=s.cuotas.primaria)
                        cands = s.cuotas.garantizar(cands, primarias, self.candidatos)
                else:
                    cands = s.retriever.search(q, self.candidatos if s.reranker or tope else self.max_passages)
                if s.jurisprudencia is not None and q == question.texto_busqueda() and s.jurisprudencia.aplica(q):
                    # Pide jurisprudencia sin nombrar sentencia: la relatoría entra por las normas que cita.
                    ya = {p.clave for p in cands}
                    extra = [p for p in s.jurisprudencia.candidatos(q, cands) if p.clave not in ya]
                    trace.passages_by_query["jurisprudencia"] = extra
                    cands = cands + extra
            if s.reranker is not None:
                hibrido = cands
                completo = tope or con_hibrido or s.cuotas is not None  # el tope necesita reemplazos
                with timed(trace, "rerank"):
                    cands = s.reranker.rerank(q, cands, len(cands) if completo or vig else self.top_n)
                if vig:
                    cands = penalizar_vigencia(cands, vig)
                    if not completo:
                        cands = cands[: self.top_n]
                if con_hibrido and q == question.texto_busqueda():
                    cands = reordenar_con(cands, [hibrido], self.cfg["retrieval"]["rrf_k"])
                    if not tope:
                        cands = cands[: self.top_n]
            elif vig:
                cands = penalizar_vigencia(cands, vig)
            if tope:
                cands = limitar_por_documento(cands, tope, self.top_n)
            listas[q] = cands  # con cuotas, todos los candidatos: la fusión necesita reemplazos
            trace.passages_by_query[q] = cands[: self.top_n]
        trace.subqueries.extend(queries)

        fijos: list[Passage] = []
        if s.valores is not None:
            with timed(trace, "valores"):
                fijos = s.valores.search(question.texto_busqueda())
            if fijos:
                trace.passages_by_query["valores"] = fijos

        with timed(trace, "fusion"):
            if s.cuotas is not None:
                # Lista larga (todos los candidatos en su orden), tope por tipo y corte en 10.
                largo = fuse(listas, lookup_hits, len(lookup_hits) + sum(len(l) for l in listas.values()))
                trace.passages_by_query["sin_cuotas"] = largo[: self.max_passages]
                fused = fuse({"cuotas": s.cuotas.aplicar(largo, question.texto_busqueda(), self.max_passages)},
                             [], self.max_passages, fijos)
            else:
                fused = fuse(listas, lookup_hits, self.max_passages, fijos)
        trace.fused_passages = fused
        return fused

    def answer(self, question: Question, passages: list[Passage], trace: Trace) -> tuple[Answer, Verdict]:
        """Genera con el LLM y verifica citas.

        En texto libre, sin pasajes o con el mejor score del reranker bajo el
        umbral, no se llama al LLM: EVIDENCIA_INSUFICIENTE directo. Si el LLM
        falla dos veces (LLMError), se usa la respuesta de respaldo determinista
        armada con los pasajes y se marca en trace.fallback.
        """
        from src.generation.llm import LLMError
        from src.generation.respaldo import CAMPO_REFERENCIA, completar_referencia, respuesta_respaldo
        from src.verification.abstention import evidencia_insuficiente
        from src.verification.verifier import citas_sin_respaldo, respuesta_vacia, verify

        motivo = evidencia_insuficiente(question, passages, self.cfg)
        if motivo is not None:
            trace.abstention_reason = motivo
            trace.verdicts.append(Verdict.EVIDENCIA_INSUFICIENTE)
            sin_respuesta = Answer(id=question.id, formato=question.formato, pasajes_recuperados=list(passages))
            return sin_respuesta, Verdict.EVIDENCIA_INSUFICIENTE

        vista = passages
        if self.stages.compresor is not None:
            # El LLM ve las sentencias comprimidas; la verificación y la entrega usan el pasaje completo.
            with timed(trace, "compresion"):
                vista = self.stages.compresor.vista(question, passages)
        with timed(trace, "generation"):
            try:
                respuesta = self.stages.generator.generate(question, vista, trace.llm_calls)
            except LLMError as exc:
                respuesta = respuesta_respaldo(question, passages)
                trace.fallback = exc.motivo
        with timed(trace, "verification"):
            vacia = respuesta_vacia(respuesta)
            veredicto = verify(respuesta, passages, self.cfg["verification"]["drop_unsupported"], question, trace)
            if veredicto != Verdict.EVIDENCIA_INSUFICIENTE:
                politica = (self.cfg["verification"].get("referencia_desde_pasajes") or {}).get(question.formato) or {}
                if completar_referencia(respuesta, passages, politica.get("fuentes", 0), politica.get("menciones", 0)):
                    trace.filled_fields.append(f"{CAMPO_REFERENCIA[question.formato]}:pasajes")
                # Extensión mínima del enunciado con texto literal de los pasajes (generation/extension.py).
                if self.stages.extension is not None and self.stages.extension.completar(question, respuesta, passages):
                    trace.filled_fields.append("extension:pasajes")
                assert not citas_sin_respaldo(respuesta, passages), question.id
        if veredicto == Verdict.EVIDENCIA_INSUFICIENTE:
            trace.abstention_reason = "respuesta_vacia" if vacia else "sin_pasajes"
        trace.verdicts.append(veredicto)
        return respuesta, veredicto

    def finalize(self, question: Question, answer: Answer, verdict: Verdict,
                 passages: list[Passage], trace: Trace) -> Answer:
        """Aplica la abstención y fija pasajes_recuperados = passages (≤ 10, los que vio el LLM).

        Con abstención se emiten todas las llaves del formato vacías ("", [], {})
        y se conservan los pasajes (enunciado, anexo A). Cerradas nunca.
        """
        from src.verification.abstention import decide

        answer.pasajes_recuperados = list(passages)
        if decide(question, verdict, passages, self.cfg):
            answer.abstencion = True
            for campo in ("justificacion", "respuesta", "referencia_legal", "marco_normativo",
                          "analisis", "jurisprudencia", "conclusion"):
                setattr(answer, campo, "")
            answer.palabras_clave = []
            answer.descarte_opciones = {}
        elif trace.abstention_reason and question.formato == "multiple_choice":
            trace.abstention_reason = None  # cerradas: se responde igual
        return answer
