"""Metadatos por fragmento: norma, tipo, número, año, artículo, órgano, vigencia.

La vigencia sale de las marcas que el Senado escribe en el propio texto
("<Artículo derogado por ...>", "<Artículo modificado por ...>") y de sus notas de
vigencia. Es una bandera para la recuperación (penalizar derogados salvo en la
sub-tarea de vigencia), no un análisis jurídico de vigencia.
"""
from __future__ import annotations

import re

from src.ingest.fuentes import Doc

VIGENCIAS = ("vigente", "modificado", "derogado", "inexequible", "desconocida")

# Marca inicial del artículo: "<Artículo modificado por el artículo 12 de la Ley 1a. de 1976 ...>"
# También marcas sobre la norma completa: "<Decreto derogado por el artículo 33 del Decreto 2844 de 2010>".
_MARCA = re.compile(r"<\s*(Art[ií]culo|ARTÍCULO|ARTICULO|Decreto|Ley|Código|Codigo)[^>]{0,400}>", re.S)
_DEROGADO = re.compile(r"\b(derogad[oa]|subrogad[oa])\b", re.I)
_INEXEQUIBLE = re.compile(r"\bINEXEQUIBLE\b")
_MODIFICADO = re.compile(r"\b(modificad[oa]|adicionad[oa]|sustituid[oa]|corregid[oa])\b", re.I)

MAX_NOTAS = 600  # caracteres de la línea de notas dentro del fragmento


def vigencia(parrafos: list[str], notas: dict[str, list[str]]) -> str:
    """Estado del artículo completo (no de incisos) según marcas y notas del Senado."""
    cabeza = " ".join(parrafos[:2])[:800]
    marcas = " ".join(m.group(0) for m in _MARCA.finditer(cabeza))
    notas_v = " ".join(notas.get("notas de vigencia", []))
    art_notas = " ".join(re.findall(r"-\s*Art[ií]culo [^.;]{0,200}", notas_v))
    if marcas and _INEXEQUIBLE.search(marcas) and not _MODIFICADO.search(marcas):
        return "inexequible"
    if (marcas and _DEROGADO.search(marcas)) or _DEROGADO.search(art_notas):
        return "derogado"
    if (marcas and _MODIFICADO.search(marcas)) or _MODIFICADO.search(art_notas):
        return "modificado"
    return "vigente"


def linea_notas(notas: dict[str, list[str]], claves=("notas de vigencia", "jurisprudencia vigencia")) -> str:
    """Resumen compacto de vigencia para el final del fragmento ("" si no hay).

    Además de informar al lector, sus referencias ("Ley 1395 de 2010", "Sentencia
    C-355-06") cuentan como respaldo para el evaluador, porque están en el pasaje.
    """
    partes: list[str] = []
    for clave in claves:
        for n in notas.get(clave, []):
            n = re.sub(r"\s+", " ", n).strip(" -")
            n = re.sub(r"^(?:resumen de )?notas de vigencia\s*:\s*-?\s*", "", n, flags=re.I)
            if n and n not in partes:
                partes.append(n)
    if not partes:
        return ""
    texto = " ".join(partes)
    if len(texto) > MAX_NOTAS:
        texto = texto[:MAX_NOTAS].rsplit(" ", 1)[0] + " …"
    return f"Notas de vigencia: {texto}"


def base(d: Doc) -> dict:
    """Metadatos del documento que se repiten en cada fragmento."""
    return {
        "doc_id": d["doc_id"],
        "norma": d["nombre_citable"],
        "tipo": d.get("tipo"),
        "numero": d.get("numero"),
        "anio": d.get("anio"),
        "organo_emisor": d.get("organo_emisor"),
    }
