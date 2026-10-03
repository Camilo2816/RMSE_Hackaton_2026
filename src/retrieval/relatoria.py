"""La relatoría de la Corte Constitucional cosechada por número, dentro del índice.

Son ~1,45 M de los 1,54 M fragmentos (sources/relatoria_cc.yaml, 28.663 sentencias):
sin acotarla domina el híbrido general y desplaza la norma primaria. Dos opciones de
config, que no tocan lookup (las sentencias que la pregunta nombra siguen llegando por
número, con la relatoría completa):

- retrieval.denso_relatoria_secciones: secciones de la relatoría que entran al denso
  (null = todas; [] = ninguna).
- retrieval.bm25_relatoria: false la saca del BM25 del híbrido.

Con [] y false la relatoría solo entra por número ("opción C"). Las sentencias del
inventario original (seed, muestra) no son de la relatoría cosechada y no se tocan.

- retrieval.solo_lookup: doc_id que tampoco entran al híbrido (ni denso ni BM25) y solo
  llegan cuando la pregunta los nombra. Para documentos que, nombrados, ocupan los 10
  pasajes y desplazan la norma de referencia (Resolución 368 de 2014 frente al CPACA).
"""
from __future__ import annotations

import re
from typing import Optional

import numpy as np

from src.common import rutas
from src.common.config import Config
from src.index.cargar import Indice


def filas(index: Indice, cfg: Config) -> np.ndarray:
    """bool por chunk_id: True si el fragmento es de la relatoría cosechada."""
    inventario = rutas.RAIZ / cfg["retrieval"].get("relatoria_inventario", "sources/relatoria_cc.yaml")
    # Solo los doc_id: leer el YAML completo (~480 mil líneas) tarda y no hace falta.
    relatoria = set(re.findall(r'^  - doc_id: "([^"]+)"', inventario.read_text(encoding="utf-8"), re.M))
    return np.fromiter((f["doc_id"] in relatoria for f in index.metadata), dtype=bool, count=len(index.metadata))


def _sin_solo_lookup(index: Indice, cfg: Config, mascara: Optional[np.ndarray]) -> Optional[np.ndarray]:
    """Quita de `mascara` (None = todas las filas) los documentos de `retrieval.solo_lookup`."""
    solo = set(cfg["retrieval"].get("solo_lookup") or [])
    if not solo:
        return mascara
    fuera = np.fromiter((f["doc_id"] in solo for f in index.metadata), dtype=bool, count=len(index.metadata))
    return ~fuera if mascara is None else mascara & ~fuera


def mascara_denso(index: Indice, cfg: Config) -> Optional[np.ndarray]:
    """Filas del denso: todo salvo las secciones de la relatoría fuera de `denso_relatoria_secciones`
    y los documentos de `solo_lookup`."""
    secciones = cfg["retrieval"].get("denso_relatoria_secciones")
    if secciones is None:
        return _sin_solo_lookup(index, cfg, None)
    permitidas = set(secciones)
    seccion_ok = np.fromiter((f.get("seccion") in permitidas for f in index.metadata), dtype=bool,
                             count=len(index.metadata))
    return _sin_solo_lookup(index, cfg, ~filas(index, cfg) | seccion_ok)


def mascara_bm25(index: Indice, cfg: Config) -> Optional[np.ndarray]:
    """Filas del BM25 del híbrido: sin la relatoría si `bm25_relatoria` es false y sin `solo_lookup`."""
    if cfg["retrieval"].get("bm25_relatoria", True):
        return _sin_solo_lookup(index, cfg, None)
    return _sin_solo_lookup(index, cfg, ~filas(index, cfg))
