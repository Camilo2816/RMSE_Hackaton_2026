"""Sentencias de la relatoría para preguntas que piden jurisprudencia sin nombrar una. Sin LLM.

Con la relatoría fuera del híbrido general (src/retrieval/relatoria.py, "opción C") solo
entra por número. Cuando la pregunta pide jurisprudencia o precedente y no nombra una
sentencia, se buscan sentencias de la relatoría por BM25 y se prefieren las que citan las
normas núcleo de la consulta: acoplamiento bibliográfico con la jerarquía de normas
(Hier-SPCNet, SIGIR 2020) y reordenamiento guiado por el conocimiento núcleo (HCLeK,
CIKM 2025). Normas núcleo: las que la pregunta nombra y las primarias entre los primeros
candidatos del híbrido. Cada norma pesa por su rareza en la relatoría (idf): la
Constitución, citada en casi todas, aporta poco (Hier-SPCNet atribuye a eso sus falsos
positivos). Las elegidas entran como candidatos del reranker; las cuotas
(`sentencia_si_pregunta`) deciden cuántas quedan en los 10.
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from typing import Optional

import numpy as np

from src.common.config import Config, deep_merge
from src.common.types import Passage
from src.index.cargar import Indice
from src.retrieval import relatoria
from src.retrieval.bm25 import BM25Retriever
from src.retrieval.cuotas import _PIDE, Cuotas
from src.verification.citations import bodies, extract, norm

Cuerpo = tuple[str, Optional[str], Optional[str]]


class JurisprudenciaPorNormas:
    def __init__(self, index: Indice, cfg: Config, lookup=None, cuotas: Optional[Cuotas] = None) -> None:
        p = cfg.get("jurisprudencia", {})
        self.n = p.get("candidatos", 10)
        self.k_bm25 = p.get("bm25_k", 300)
        self.nucleo = p.get("nucleo", 10)
        self.index, self.lookup = index, lookup
        self.primaria = cuotas.primaria if cuotas is not None else None
        self.es_relatoria = relatoria.filas(index, cfg)
        # BM25 sin la máscara del híbrido: aquí se busca justamente dentro de la relatoría.
        self.bm25 = BM25Retriever(index, deep_merge(cfg, {"retrieval": {"bm25_relatoria": True}}))
        self.cuerpos_doc: dict[str, set[Cuerpo]] = defaultdict(set)
        for i in np.flatnonzero(self.es_relatoria):
            f = index.metadata[i]
            for c in f.get("cuerpos") or []:
                if not (c[0] == "jurisprudencia" and c[1] == f.get("numero")):  # su propia cita no cuenta
                    self.cuerpos_doc[f["doc_id"]].add(tuple(c))
        df = Counter(c for cs in self.cuerpos_doc.values() for c in cs)
        n_docs = max(1, len(self.cuerpos_doc))
        self.idf = {c: math.log(n_docs / d) for c, d in df.items()}

    def aplica(self, query: str) -> bool:
        """La pregunta pide jurisprudencia y no nombra una sentencia (esa la trae lookup)."""
        if not _PIDE["sentencia"].search(norm(query)):
            return False
        nombradas = self.lookup.documentos(query) if self.lookup is not None else []
        return not any(d.startswith("sentencia_") for d in nombradas)

    def nucleo_de(self, query: str, hibrido: list[Passage]) -> set[Cuerpo]:
        """Normas que la pregunta nombra y normas primarias entre los primeros candidatos."""
        nucleo = {c for c in bodies(extract(query)) if c[0] != "jurisprudencia"}
        primarias = [p for p in hibrido if (self.primaria[p.chunk_id] if self.primaria is not None
                                            else not p.doc_id.startswith("sentencia_"))]
        for p in primarias[: self.nucleo]:
            nucleo |= {c for c in bodies(extract(p.norma)) if c[0] != "jurisprudencia"}
        return nucleo

    def candidatos(self, query: str, hibrido: list[Passage]) -> list[Passage]:
        """Hasta `candidatos` fragmentos de la relatoría (uno por sentencia), por acoplamiento
        con las normas núcleo y, a igualdad, por BM25."""
        nucleo = self.nucleo_de(query, hibrido)
        if not nucleo:
            return []
        mejor: dict[str, tuple[int, Passage]] = {}
        for rango, p in enumerate(self.bm25.search(query, self.k_bm25, mascara=self.es_relatoria)):
            mejor.setdefault(p.doc_id, (rango, p))
        puntaje = {d: sum(self.idf.get(c, 0.0) for c in nucleo & self.cuerpos_doc.get(d, set())) for d in mejor}
        elegidos = sorted((d for d in mejor if puntaje[d] > 0), key=lambda d: (-puntaje[d], mejor[d][0], d))
        return [mejor[d][1] for d in elegidos[: self.n]]
