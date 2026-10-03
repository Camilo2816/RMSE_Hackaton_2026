"""Lookup directo: normas, artículos y sentencias nombrados en la consulta. Sin LLM.

Extrae las citas de la consulta con scripts/citations.py (vía
src/verification/citations.py) y devuelve los fragmentos exactos del índice.
Cubre el caso que los embeddings resuelven mal ("artículo 42" vs "artículo 24").

Orden de los hits (determinista):
1. Artículos nombrados de una norma del corpus: sus primeras
   `lookup.partes_por_articulo` partes.
2. Normas nombradas sin artículo: en sentencias la ficha; después, los
   fragmentos del documento con mejor BM25 para la consulta (sin salvamentos
   ni aclaraciones de voto), `lookup.por_norma` por norma.
El total se corta en `lookup.max_hits`: lo demás lo aporta el híbrido.

Complementos al extractor oficial, que no los captura:
- artículos con numeración de decreto único ("artículo 2.2.1.1.1.1") o con guion
  ("artículo 240-1", que el extractor lee como 240);
- sentencias sin año ("sentencia T-256"), si el tipo y número son únicos en el corpus.
Salvaguarda: "constitución de la sociedad" o "constitución en mora" se leen como
Constitución; sin artículo, la Constitución solo cuenta si se nombra completa.
"""
from __future__ import annotations

import re
from collections import defaultdict

import numpy as np

from src.common.config import Config
from src.common.types import Passage
from src.index.cargar import Indice
from src.index.tokenizar import tokenizar
from src.retrieval.base import Retriever
from src.verification.citations import extract, norm

Cuerpo = tuple[str, str | None, str | None]

_ART_COMPUESTO = re.compile(r"\bart(?:[ií]culo|\.)?s?\s+(\d+(?:\.\d+){2,}|\d+-\d+)\b", re.IGNORECASE)
_SENT_SIN_ANIO = re.compile(r"\b(su|c|t)\s*-\s*0*(\d{1,4})\b(?!\s*(?:de|del|/|-)\s*\d{2,4})", re.IGNORECASE)
_CONSTITUCION_EXPLICITA = re.compile(r"constitucion (politica|nacional)|carta politica")
SECCIONES_EXCLUIDAS = {"salvamento_voto", "aclaracion_voto", "anexo"}


def _clave_cita(c: tuple) -> tuple:
    return tuple("" if x is None else str(x) for x in c)


class LookupRetriever(Retriever):
    """`search` devuelve solo coincidencias exactas; puede devolver lista vacía."""

    def __init__(self, index: Indice, cfg: Config) -> None:
        self.index = index
        self.bm25 = index.bm25
        params = cfg.get("lookup", {})
        self.max_hits = params.get("max_hits", 4)
        self.por_norma = params.get("por_norma", 2)
        self.partes_por_articulo = params.get("partes_por_articulo", 2)

        self.docs_de: dict[Cuerpo, list[str]] = defaultdict(list)   # cuerpo → doc_ids
        self.rango: dict[str, tuple[int, int]] = {}                  # doc_id → [inicio, fin) de chunk_id
        self.articulos: dict[tuple[str, str], list[int]] = defaultdict(list)
        self.ficha: dict[str, int] = {}
        self.sentencias: dict[tuple[str, str], list[str]] = defaultdict(list)  # ("t", "256") → doc_ids
        for i, f in enumerate(index.metadata):
            doc = f["doc_id"]
            if doc not in self.rango:
                self.rango[doc] = (i, i + 1)
                for c in extract(f["norma"]):
                    cuerpo = c[:3]
                    if doc not in self.docs_de[cuerpo]:
                        self.docs_de[cuerpo].append(doc)
                    if cuerpo[0] == "jurisprudencia":
                        tipo, num = cuerpo[1].lower().split("-", 1)
                        self.sentencias[(tipo, num.lstrip("0"))].append(doc)
            else:
                self.rango[doc] = (self.rango[doc][0], i + 1)
            if f.get("articulo"):
                self.articulos[(doc, f["articulo"].lower())].append(i)
            if f.get("seccion") == "ficha" and doc not in self.ficha:
                self.ficha[doc] = i

    # -- citas de la consulta -------------------------------------------------
    def citas(self, query: str) -> list[tuple]:
        """Citas (tipo, número, año, artículo) de la consulta, en orden determinista."""
        cites = set(extract(query))
        cuerpos = {c[:3] for c in cites}
        for m in _ART_COMPUESTO.finditer(query):
            art = m.group(1)
            for cuerpo in cuerpos:
                cites.add((*cuerpo, art))
                if "-" in art:  # el extractor leyó "240-1" como "240"
                    cites.discard((*cuerpo, art.split("-")[0]))
        for m in _SENT_SIN_ANIO.finditer(query):
            docs = self.sentencias.get((m.group(1).lower(), m.group(2)), [])
            if len(docs) == 1:
                cites |= {c for c in extract(self.index.metadata[self.rango[docs[0]][0]]["norma"])}
        if not _CONSTITUCION_EXPLICITA.search(norm(query)):
            cites.discard(("constitucion", None, None, None))
        return sorted(cites, key=_clave_cita)

    def documentos(self, query: str) -> list[str]:
        """doc_ids de las normas nombradas en la consulta (sin duplicados, en orden)."""
        out: list[str] = []
        for c in self.citas(query):
            for doc in self.docs_de.get(c[:3], []):
                if doc not in out:
                    out.append(doc)
        return out

    # -- búsqueda -------------------------------------------------------------
    def _mejores_del_doc(self, doc: str, tokens: list[str], n: int, excluir: set[int]) -> list[tuple[int, float]]:
        ini, fin = self.rango[doc]
        if not tokens or self.bm25 is None or n <= 0:
            return []
        scores = np.asarray(self.bm25.get_scores(tokens), dtype=np.float32)[ini:fin]
        orden = sorted(range(fin - ini), key=lambda j: (-round(float(scores[j]), 6), ini + j))
        out = []
        for j in orden:
            i = ini + j
            if scores[j] <= 0 or len(out) >= n:
                break
            if i in excluir or self.index.metadata[i].get("seccion") in SECCIONES_EXCLUIDAS:
                continue
            out.append((i, float(scores[j])))
        return out

    def search(self, query: str, k: int, texto_bm25: str | None = None) -> list[Passage]:
        """`texto_bm25`: con qué se rankea dentro de las normas nombradas (por defecto, `query`).

        En cerradas conviene la pregunta sola: los números de norma de las opciones
        hacen ganar artículos que son listas de leyes (art. 626 del CGP, "DEROGACIONES").
        """
        limite = min(k, self.max_hits)
        cites = self.citas(query)
        elegidos: list[tuple[int, float]] = []
        vistos: set[int] = set()

        def agregar(i: int, score: float) -> None:
            if i not in vistos and len(elegidos) < limite:
                vistos.add(i)
                elegidos.append((i, score))

        # 1. Artículos nombrados.
        for c in cites:
            if c[3] is None:
                continue
            for doc in self.docs_de.get(c[:3], []):
                for i in self.articulos.get((doc, str(c[3]).lower()), [])[: self.partes_por_articulo]:
                    agregar(i, 1.0)
        # 2. Normas nombradas sin artículo (o cuyo artículo no está en el corpus).
        con_articulo = {c[:3] for c in cites if c[3] is not None and any(
            (doc, str(c[3]).lower()) in self.articulos for doc in self.docs_de.get(c[:3], []))}
        tokens = [t for t in tokenizar(texto_bm25 or query) if self.bm25 is not None and t in self.bm25.vocab_dict]
        for cuerpo in dict.fromkeys(c[:3] for c in cites):
            if cuerpo in con_articulo:
                continue
            for doc in self.docs_de.get(cuerpo, []):
                n = self.por_norma
                if doc in self.ficha:
                    agregar(self.ficha[doc], 1.0)
                    n -= 1
                for i, s in self._mejores_del_doc(doc, tokens, n, vistos):
                    agregar(i, s)
        return [self.index.pasaje(i, s, "lookup") for i, s in elegidos]

