"""Tope de pasajes por tipo de documento en la lista final. Sin LLM.

Las sentencias son casi la mitad del corpus y los DUR y la Circular Básica Jurídica
otra parte grande; sin tope desplazan a la norma primaria (medido en sample_50: el
Consejo de Estado saca la Ley 472 del ítem 51 y la Circular de la SFC el CST del 253).
Sobre la lista ya ordenada (lookup + reranker/RRF), cada pasaje cuenta en su clase:

- `voto`: salvamentos y aclaraciones de voto (sección del fragmento);
- `sentencia`: cualquier otra sección de una sentencia (CC, CSJ, CE);
- `reglamentaria`: decretos únicos reglamentarios y circulares (`cuotas.reglamentarias`).

Un pasaje que excede el tope de su clase cede el lugar al siguiente; si no alcanzan
los candidatos, los cedidos vuelven en su orden (nunca menos pasajes que sin tope).
El tope se aplica dos veces: al elegir los candidatos del reranker entre un híbrido
más largo (si no, en preguntas como la 51 de sample_50 llegan 19 sentencias de 20 y
no hay con qué reemplazarlas) y sobre la lista final de 10.
No cuentan los documentos que la pregunta nombra (lookup.documentos): "la sentencia
T-256 de 2025" o "el Decreto 1072 de 2015" traen lo suyo sin límite. Si la pregunta
pide jurisprudencia o votos, su tope sube (`cuotas.*_si_pregunta`).

El tope solo reemplaza con lo que hay entre los candidatos. Con la relatoría completa
(~97 % de los fragmentos son sentencias) el híbrido puede no traer ninguna norma entre
120 (sample_50, ítems 647 y 748) y la cuota devuelve las sentencias cedidas. Con
`cuotas.min_primarias` > 0, una búsqueda restringida a normas primarias (sin clase:
ni sentencia ni reglamentaria) garantiza ese mínimo entre los candidatos del reranker.
"""
from __future__ import annotations

import re
from typing import Optional

import numpy as np

from src.common.config import Config
from src.common.types import Passage
from src.index.cargar import Indice
from src.verification.citations import norm

VOTOS = {"salvamento_voto", "aclaracion_voto"}
_PIDE = {
    "sentencia": re.compile(r"\b(?:sentencias?|jurisprudencia\w*|precedentes?|providencias?|fallos?|"
                            r"corte constitucional|corte suprema|consejo de estado|ratio decidendi|"
                            r"magistrad[oa] ponente|salvamento|aclaracion de voto)\b"),
    "voto": re.compile(r"\b(?:salvamentos? de voto|aclaracion(?:es)? de voto|salvo (?:el|su) voto)\b"),
    "reglamentaria": re.compile(r"\b(?:decreto unico|dur|circular|superintendencia|superfinanciera|sfc|"
                                r"supersociedades|reglament\w*)\b"),
}


class Cuotas:
    def __init__(self, index: Indice, cfg: Config, lookup: Optional[object] = None) -> None:
        p = cfg.get("cuotas", {})
        self.topes = {"sentencia": p.get("sentencia", 3), "voto": p.get("voto", 0),
                      "reglamentaria": p.get("reglamentaria", 2)}
        self.topes_si_pregunta = {"sentencia": p.get("sentencia_si_pregunta", 6),
                                  "voto": p.get("voto_si_pregunta", 2),
                                  "reglamentaria": p.get("reglamentaria_si_pregunta", 5)}
        reglamentarias = set(p.get("reglamentarias", []))
        self.min_primarias = p.get("min_primarias", 0) or 0
        self.lookup = lookup  # LookupRetriever: documentos nombrados en la pregunta
        self.clase: dict[int, Optional[str]] = {}
        for i, f in enumerate(index.metadata):
            if f.get("tipo") == "sentencia":
                self.clase[i] = "voto" if f.get("seccion") in VOTOS else "sentencia"
            elif f.get("tipo") == "circular" or f["doc_id"] in reglamentarias:
                self.clase[i] = "reglamentaria"
        self.primaria = np.ones(len(index.metadata), dtype=bool)  # sin clase: ley, código, Constitución...
        self.primaria[list(self.clase)] = False

    def topes_para(self, query: str) -> dict[str, int]:
        t = norm(query)
        return {k: (self.topes_si_pregunta[k] if _PIDE[k].search(t) else v) for k, v in self.topes.items()}

    def aplicar(self, passages: list[Passage], query: str, limite: int, factor: float = 1.0) -> list[Passage]:
        """`factor` escala los topes: la preselección de candidatos del reranker (20 de un
        híbrido de 60) usa topes proporcionales a su tamaño (factor 2 para 20 frente a 10)."""
        topes = {k: int(round(v * factor)) for k, v in self.topes_para(query).items()}
        nombrados = set(self.lookup.documentos(query)) if self.lookup is not None else set()
        cuenta = dict.fromkeys(topes, 0)
        elegidos, cedidos = [], []
        for p in passages:
            clase = self.clase.get(p.chunk_id)
            if clase is None or p.doc_id in nombrados:
                elegidos.append(p)
            elif cuenta[clase] < topes[clase]:
                cuenta[clase] += 1
                elegidos.append(p)
            else:
                cedidos.append(p)
            if len(elegidos) >= limite:
                break
        if len(elegidos) < limite:
            claves = {p.clave for p in [*elegidos, *cedidos[: limite - len(elegidos)]]}
            elegidos = [p for p in passages if p.clave in claves]
        return elegidos[:limite]

    def garantizar(self, candidatos: list[Passage], primarias: list[Passage], limite: int) -> list[Passage]:
        """Los candidatos con las `primarias` dadas: las que falten entran al final y, si no
        caben, desplazan a los últimos candidatos que no son norma primaria."""
        ya = {p.clave for p in candidatos}
        faltan = [p for p in primarias if p.clave not in ya]
        sobran = len(candidatos) + len(faltan) - limite
        if sobran > 0:
            quitables = [i for i, p in enumerate(candidatos) if not self.primaria[p.chunk_id]]
            quitar = set(quitables[-sobran:])
            candidatos = [p for i, p in enumerate(candidatos) if i not in quitar]
        return (candidatos + faltan)[:limite]
