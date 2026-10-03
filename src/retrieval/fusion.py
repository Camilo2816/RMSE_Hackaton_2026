"""Fusión de listas de pasajes. Determinista y con orden estable.

- rrf: fusión Reciprocal Rank Fusion genérica (la usa también hybrid.py).
- limitar_por_documento: tope de fragmentos por documento en una lista ordenada.
- penalizar_vigencia: baja (sin descartar) los fragmentos derogados o inexequibles.
- fuse: combina los hits del lookup y las listas por subconsulta en ≤ max_passages.
  Los hits del lookup van primero; duplicados por (doc_id, chunk_id) se eliminan;
  desempate por (doc_id, chunk_id).
"""
from __future__ import annotations

from dataclasses import replace

from src.common.types import Passage


def ordenar(passages: list[Passage]) -> list[Passage]:
    """Score descendente; empates por (doc_id, chunk_id). El score se redondea a 1e-6
    para que diferencias de último bit (GPU, BLAS) no reordenen empates prácticos."""
    return sorted(passages, key=lambda p: (-round(p.score, 6), p.clave))


def penalizar_vigencia(passages: list[Passage], factores: dict[str, float] | None) -> list[Passage]:
    """Reordena con score × factores[vigencia] (p. ej. derogado 0,85); los scores no cambian.

    Desempate suave, no filtro: a veces la clave espera la norma derogada (Ley 640
    de 2001, CPT de 1948) y un pasaje derogado muy pertinente sigue arriba. Donde
    el texto es casi el mismo (Ley 1943, inexequible, frente a la Ley 2010) gana el
    vigente. Los scores se conservan porque la abstención y el re-planeo los leen.
    """
    if not factores:
        return passages

    def ajustado(p: Passage) -> float:
        f = factores.get(p.vigencia or "", 1.0)
        return p.score * f if p.score >= 0 else p.score / f

    return sorted(passages, key=lambda p: (-round(ajustado(p), 6), p.clave))


def rrf(lists: list[list[Passage]], k: int = 60) -> list[Passage]:
    """Suma 1 / (k + rango) por pasaje a través de las listas (rango desde 1).

    Cada pasaje conserva los campos de su primera aparición (incluido
    fuente_query) y toma como score su puntaje RRF.
    """
    puntaje: dict[tuple[str, int], float] = {}
    primero: dict[tuple[str, int], Passage] = {}
    for lista in lists:
        for rango, p in enumerate(lista, start=1):
            puntaje[p.clave] = puntaje.get(p.clave, 0.0) + 1.0 / (k + rango)
            primero.setdefault(p.clave, p)
    return ordenar([replace(p, score=puntaje[c]) for c, p in primero.items()])


def reordenar_con(base: list[Passage], otras: list[list[Passage]], k: int = 60) -> list[Passage]:
    """Los pasajes de `base` ordenados por RRF entre `base` y `otras`, con sus campos y scores intactos.

    Uso: base = orden del reranker, otras = [orden del híbrido]. El reranker no
    tiene la última palabra (en 128 y 247 hunde la norma que el híbrido traía en
    3.º y 17.º lugar), pero su score se conserva para la señal de evidencia débil.
    """
    puntaje: dict[tuple[str, int], float] = {}
    for lista in [base, *otras]:
        for rango, p in enumerate(lista, start=1):
            puntaje[p.clave] = puntaje.get(p.clave, 0.0) + 1.0 / (k + rango)
    return sorted(base, key=lambda p: (-round(puntaje[p.clave], 9), p.clave))


def limitar_por_documento(passages: list[Passage], tope: int, limite: int) -> list[Passage]:
    """Los `limite` primeros con a lo sumo `tope` fragmentos por doc_id, conservando el orden.

    Un documento largo (Decreto 2555, T-760) deja de copar los 10 cupos. Si no
    alcanzan documentos distintos, se rellena con los descartados en su orden.
    """
    elegidos: list[Passage] = []
    descartados: list[Passage] = []
    por_doc: dict[str, int] = {}
    for p in passages:
        if por_doc.get(p.doc_id, 0) < tope:
            por_doc[p.doc_id] = por_doc.get(p.doc_id, 0) + 1
            elegidos.append(p)
        else:
            descartados.append(p)
    if len(elegidos) < limite:
        claves = {p.clave for p in [*elegidos, *descartados[: limite - len(elegidos)]]}
        elegidos = [p for p in passages if p.clave in claves]
    return elegidos[:limite]


def fuse(
    lists_by_query: dict[str, list[Passage]],
    lookup_hits: list[Passage],
    max_passages: int = 10,
    fijos: list[Passage] = (),
) -> list[Passage]:
    """Lista final que ve el LLM y que se entrega como pasajes_recuperados. Nunca > max_passages.

    Con una sola lista se respeta su orden y sus scores (los del reranker); con
    varias, se fusionan con RRF en el orden de inserción del dict. Los `fijos`
    (valores vigentes) que no hayan entrado ocupan los últimos lugares.
    """
    listas = [l for l in lists_by_query.values() if l]
    resto = rrf(listas) if len(listas) > 1 else (listas[0] if listas else [])
    out: list[Passage] = []
    vistos: set[tuple[str, int]] = set()
    for p in [*lookup_hits, *resto]:
        if len(out) >= max_passages:
            break
        if p.clave not in vistos:
            vistos.add(p.clave)
            out.append(p)
    faltan = list({p.clave: p for p in fijos if p.clave not in vistos}.values())[:max_passages]
    if faltan:
        out = out[: max_passages - len(faltan)] + faltan
    return out
