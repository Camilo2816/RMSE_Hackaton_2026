"""Valores vigentes (SMLMV, UVT, auxilio de transporte): pasajes fijos por regla. Sin LLM.

Una pregunta sobre "una cuantía de 30.000.000" no comparte vocabulario con
"salario mínimo", así que la recuperación no trae el decreto que fija la cifra
(ítem 528 de la muestra). Cada regla de `valores.reglas` es un patrón sobre la
consulta normalizada (minúsculas, sin tildes) y los artículos que aporta.

Los pasajes son fragmentos del corpus (la primera parte del artículo), con su
offset y su nombre citable: el evaluador los ve como cualquier otro. Van con
fuente_query "valores", así que no cuentan como hit del lookup para el re-planeo
ni como score del reranker para la abstención.
"""
from __future__ import annotations

import re

from src.common.config import Config
from src.common.types import Passage
from src.index.cargar import Indice
from src.verification.citations import norm

FUENTE = "valores"


class ValoresRetriever:
    def __init__(self, index: Indice, cfg: Config) -> None:
        params = cfg.get("valores", {})
        self.index = index
        self.max = params.get("max", 2)
        primera: dict[tuple[str, str], int] = {}
        for i, f in enumerate(index.metadata):
            if f.get("articulo"):
                primera.setdefault((f["doc_id"], f["articulo"].lower()), i)
        self.reglas: list[tuple[str, re.Pattern, list[int]]] = []
        for r in params.get("reglas", []):
            ids = []
            for p in r["pasajes"]:
                clave = (p["doc_id"], str(p["articulo"]).lower())
                if clave not in primera:
                    raise ValueError(f"valores.{r['nombre']}: {clave} no está en el índice")
                ids.append(primera[clave])
            self.reglas.append((r["nombre"], re.compile(r["patron"]), ids))

    def disparadas(self, query: str) -> list[str]:
        t = norm(query)
        return [nombre for nombre, patron, _ in self.reglas if patron.search(t)]

    def search(self, query: str) -> list[Passage]:
        """Pasajes de las reglas que se activan, en el orden de la config, sin repetir; ≤ max."""
        t = norm(query)
        elegidos: list[int] = []
        for _, patron, ids in self.reglas:
            if patron.search(t):
                elegidos += [i for i in ids if i not in elegidos]
        return [self.index.pasaje(i, 0.0, FUENTE) for i in elegidos[: self.max]]
