"""Construye el Pipeline a partir de la config (cfg["pipeline"], cfg["planner"]["type"])."""
from __future__ import annotations

from src.common.config import Config
from src.pipelines.agentic import AgenticPipeline
from src.pipelines.base import Pipeline, Stages
from src.pipelines.baseline import BaselinePipeline
from src.planning.base import QueryPlanner
from src.planning.passthrough import PassthroughPlanner
from src.planning.reformulate import ReformulatePlanner
from src.planning.subqueries import SubqueryPlanner

PIPELINES: dict[str, type[Pipeline]] = {
    "baseline": BaselinePipeline,
    "agentic": AgenticPipeline,
}

PLANNERS: dict[str, type[QueryPlanner]] = {
    "passthrough": PassthroughPlanner,
    "reformulate": ReformulatePlanner,
    "subqueries": SubqueryPlanner,
}


def build_stages(cfg: Config, generador: bool = True) -> Stages:
    """Carga el índice congelado y el cliente LLM, e instancia cada etapa según la config.

    generador=False construye solo planificación y recuperación (sin generador),
    para medir la recuperación; si el planner usa el LLM, el cliente se crea igual.
    """
    from src.index.cargar import cargar
    from src.retrieval.bm25 import BM25Retriever
    from src.retrieval.dense import DenseRetriever
    from src.retrieval.hybrid import HybridRetriever
    from src.retrieval.lookup import LookupRetriever
    from src.retrieval.rerank import Reranker
    from src.retrieval.cuotas import Cuotas
    from src.retrieval.valores import ValoresRetriever

    idx = cargar()
    r = cfg["retrieval"]
    retriever = HybridRetriever(DenseRetriever(idx, cfg), BM25Retriever(idx, cfg), r["rrf_k"], r["top_k_per_query"])
    lookup = LookupRetriever(idx, cfg) if cfg["lookup"]["enabled"] else None
    reranker = Reranker(cfg) if cfg["rerank"]["enabled"] else None
    valores = ValoresRetriever(idx, cfg) if cfg.get("valores", {}).get("enabled") else None
    cuotas = Cuotas(idx, cfg, lookup) if cfg.get("cuotas", {}).get("enabled") else None
    jurisprudencia = None
    if cfg.get("jurisprudencia", {}).get("enabled"):
        from src.retrieval.jurisprudencia import JurisprudenciaPorNormas

        jurisprudencia = JurisprudenciaPorNormas(idx, cfg, lookup, cuotas)
    compresor = None
    if generador and reranker is not None and cfg.get("compresion", {}).get("enabled"):
        from src.generation.compresion import Compresor

        compresor = Compresor(reranker, cfg)
    extension = None
    if generador and reranker is not None and cfg["verification"].get("extension", {}).get("enabled"):
        from src.generation.extension import Extension

        extension = Extension(reranker, cfg)

    tipo = cfg["planner"]["type"]
    llm = generator = None
    if generador or tipo != "passthrough":
        from src.generation.llm import LLMClient

        llm = LLMClient(cfg)
        llm.asegurar_cargado()  # precarga: la primera pregunta no paga la carga en frío
    if generador:
        from src.generation.answer import AnswerGenerator

        generator = AnswerGenerator(llm, cfg["generation"].get("estructura"))
    if tipo == "passthrough":
        planner: QueryPlanner = PassthroughPlanner(cfg)
    elif tipo == "subqueries":
        planner = SubqueryPlanner(llm, cfg["planner"].get("n", 3), cfg)
    else:
        planner = PLANNERS[tipo](llm, cfg)
    return Stages(planner=planner, lookup=lookup, retriever=retriever, reranker=reranker, generator=generator,
                  valores=valores, cuotas=cuotas, jurisprudencia=jurisprudencia, compresor=compresor, extension=extension)


def build_pipeline(cfg: Config, generador: bool = True) -> Pipeline:
    return PIPELINES[cfg["pipeline"]](build_stages(cfg, generador), cfg)
