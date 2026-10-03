"""Normas citadas en una respuesta, para la interfaz.

Extrae las citas con el extractor oficial (src.verification.citations), igual
que evaluate.py: `respaldada` es a grano de cuerpo normativo contra los 10
pasajes entregados. Cada cita lleva además patrones regex (sobre texto en
minúsculas y sin tildes) para que el front resalte la norma dentro de los pasajes.
"""
from __future__ import annotations

import re
from typing import Any, Optional

from src.common.types import Answer
from src.verification import citations

TIPOS = {"ley": "Ley", "decreto": "Decreto", "acto_legislativo": "Acto Legislativo",
         "resolucion": "Resolución", "circular": "Circular", "acuerdo": "Acuerdo"}


def _sin_ordinal(c: tuple) -> tuple:
    """El corpus escribe "ARTÍCULO 3o."; el extractor lo lee como artículo "3o"."""
    return (*c[:3], re.sub(r"(?<=\d)o$", "", c[3]) if c[3] else None)


def _clave(c: tuple) -> tuple:
    return tuple("" if x is None else str(x) for x in c)


def nombre(c: tuple) -> str:
    """("ley", "472", "1998", "3") -> "Ley 472 de 1998, art. 3"."""
    cuerpo, numero, anio, art = c
    if cuerpo == "jurisprudencia":
        base = f"Sentencia {numero} de {anio}"
    elif cuerpo in TIPOS:
        base = f"{TIPOS[cuerpo]} {numero} de {anio}"
    else:
        try:
            from src.common.alias_normas import nombre_citable
            base = nombre_citable(cuerpo) or ""
        except Exception:  # noqa: BLE001 - sin tabla de alias queda el nombre de la clave
            base = ""
        base = base or cuerpo.replace("_", " ").capitalize()
    return f"{base}, art. {art}" if art else base


def _espacios(patron: str) -> str:
    return patron.replace(r"\ ", r"\s+").replace(" ", r"\s+")


def patrones_cuerpo(c: tuple) -> list[str]:
    """Regex (sintaxis común Python/JS) que ubican el cuerpo normativo en texto normalizado."""
    cuerpo, numero, anio, _ = c
    if cuerpo == "jurisprudencia":
        sala, _, n = str(numero).partition("-")
        anios = f"(?:{anio}|{str(anio)[2:]})"
        return [rf"\b{sala.lower()}\s*[-\s]?\s*0*{n}\s*(?:de|del|/|-)\s*{anios}\b"]
    if cuerpo in citations.oficial.NORM_TYPES:
        variantes = sorted(citations.oficial.NORM_TYPES[cuerpo], key=len, reverse=True)
        tipo = "|".join(_espacios(re.escape(v)) for v in variantes)
        return [rf"\b(?:{tipo})\s*(?:n[°ºo]?\.?\s*)?{numero}\s*(?:de|del|/|-)\s*{anio}\b"]
    out = []
    for v in sorted(citations.oficial.CODES.get(cuerpo, ()), key=len, reverse=True):
        if len(v) <= 3 and v.isalpha():
            continue  # "cp", "cc", "et": demasiado ruido para resaltar
        out.append(r"(?<![\w.])" + _espacios(re.escape(v)) + r"(?![\w])")
    return out


def patron_articulo(art: Optional[str]) -> Optional[str]:
    if not art:
        return None
    return rf"\bart(?:iculos?|s?\.)\s*{re.escape(str(art))}(?![\d])"


def normas_citadas(answer: Answer) -> list[dict[str, Any]]:
    """[{"cita", "respaldada", "articulo_en_pasajes", "canonica", "patrones"}] de la respuesta."""
    texto = citations.answer_text(answer.to_submission())
    citas = citations.extract(texto)
    con_articulo = {c[:3] for c in citas if c[3] is not None}
    citas = {c for c in citas if c[3] is not None or c[:3] not in con_articulo}
    en_pasajes = citations.respaldadas(answer.pasajes_recuperados)
    cuerpos = citations.bodies(en_pasajes)
    articulos = {_sin_ordinal(c) for c in en_pasajes}
    return [{"cita": nombre(c),
             "respaldada": c[:3] in cuerpos,
             "articulo_en_pasajes": c[3] is not None and _sin_ordinal(c) in articulos,
             "canonica": list(c),
             "patrones": {"cuerpo": patrones_cuerpo(c), "articulo": patron_articulo(c[3])}}
            for c in sorted(citas, key=_clave)]


def pasajes(answer: Answer, normas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Los pasajes entregados con norma y artículo, y los índices de `normas` que aparecen en cada uno."""
    out = []
    for p in answer.pasajes_recuperados:
        cuerpos = citations.bodies(citations.extract(p.texto or ""))
        d = p.to_json()
        d["normas_citadas"] = [i for i, n in enumerate(normas) if tuple(n["canonica"][:3]) in cuerpos]
        out.append(d)
    return out
