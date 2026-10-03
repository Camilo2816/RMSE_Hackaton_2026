"""Parser de compilaciones de la Relatoría de la Sala de Casación Civil (Corte Suprema), en PDF.

Gacetas de jurisprudencia y compilaciones temáticas ("Contratos civiles y comerciales").
No son una sentencia sino reseñas de muchas providencias escritas por la Relatoría; cada
reseña lleva el número de la providencia (SC3666-2021), que es lo que el evaluador
reconoce como cita. Se modela como una sentencia (misma estructura que
parsers/corte_constitucional.py) en la que cada reseña es una sección propia con el
número de la providencia como subtítulo, así que segmentar.fragmentos_sentencia la parte
sin mezclar dos providencias en un fragmento.

Estructura (verificada en la Gaceta 08-2021 y en "Contratos civiles y comerciales", 2025):
- Créditos y contenido, luego el índice temático: arranca en la primera línea que es
  una sola letra ("A", "C"). Cada extracto termina en "(SC3712-2021; 25/08/2021)".
- Reseñas: empiezan en una línea que es solo el número ("SC4425-2020"): descriptores,
  fuente formal y jurisprudencial, asunto y la ficha (M. PONENTE, NÚMERO DE PROCESO,
  PROCEDENCIA, TIPO DE PROVIDENCIA, NÚMERO DE LA PROVIDENCIA, CLASE DE ACTUACIÓN,
  FECHA, DECISIÓN), con la etiqueta y ": valor" en líneas distintas.
- El "Índice alfabético" final queda fuera.
- Fuera: números de página y encabezados corridos (línea idéntica en ≥ 60 % de las
  páginas; las etiquetas de la ficha se repiten menos y se conservan).
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any

import pymupdf

_PAGINA = re.compile(r"^\s*\d{1,3}\s*$")
_REF = r"(?:SC|STC|AC|ATC|SL|SP|STL|STP|AL|AP)\s?\d{1,5}-\d{4}"
_REF_SOLA = re.compile(rf"^({_REF})$")
_CIERRE = re.compile(rf"\(({_REF})(?:\s*,\s*{_REF})*\s*;\s*\d{{1,2}}/\d{{1,2}}/\d{{4}}\)\S{{0,3}}\s*$")
_CIERRE_ABIERTO = re.compile(rf"\({_REF}(?:\s*,\s*{_REF})*\s*;?\s*$")
_LETRA = re.compile(r"^[A-ZÁÉÍÓÚÑ]$")
_TITULO = re.compile(r"^[^a-záéíóúñ]{4,70}$")
_FIN_PARRAFO = re.compile(r"[.:;»”\")]\s*$")
_INDICE_FINAL = re.compile(r"^Índice alfabético$", re.I)


def _lineas(doc: pymupdf.Document) -> list[str]:
    paginas = [[l.strip() for l in p.get_text().splitlines()] for p in doc]
    por_pagina = Counter(l for ls in paginas for l in set(ls) if l)
    corridos = {l for l, n in por_pagina.items() if n >= 0.6 * len(paginas)}
    out: list[str] = []
    for l in (l for ls in paginas for l in ls):
        if not l or _PAGINA.match(l) or l in corridos:
            continue
        if l.startswith(":") and out:  # ficha: "M. PONENTE" / ": NOMBRE"
            out[-1] = f"{out[-1]}{l}"
            continue
        out.append(re.sub(r"\s+", " ", l))
    return out


def _parrafos(lineas: list[str]) -> list[str]:
    out, buffer = [], []
    for l in lineas:
        etiqueta = re.match(r"^[A-ZÁÉÍÓÚÑ. ]{4,40}:", l)  # línea de ficha completa
        titulo = (_TITULO.match(l) and not _CIERRE_ABIERTO.search(l)
                  and not re.fullmatch(r"[\d/ ().;,]+", l))  # "(SC1121-2018;" + "18/04/2018)" no son títulos
        if titulo or etiqueta or _LETRA.match(l):
            if buffer:
                out.append(" ".join(buffer))
                buffer = []
            out.append(l)
            continue
        buffer.append(l)
        if _FIN_PARRAFO.search(l) and not _CIERRE_ABIERTO.search(l):  # "(SC1121-2018;" / "18/04/2018)"
            out.append(" ".join(buffer))
            buffer = []
    if buffer:
        out.append(" ".join(buffer))
    return out


def parsear_documento(carpeta: Path, paginas: list[str]) -> dict[str, Any]:
    lineas = _lineas(pymupdf.open(carpeta / paginas[0]))
    fin = next((i for i, l in enumerate(lineas) if _INDICE_FINAL.match(l) and i > len(lineas) // 2), len(lineas))
    ini_a = next((i for i, l in enumerate(lineas) if _LETRA.match(l)), 0)
    ini_b = next((i for i, l in enumerate(lineas) if _REF_SOLA.match(l)), fin)

    secciones: list[dict[str, Any]] = []
    actual: list[str] = []
    for p in _parrafos(lineas[ini_a:ini_b]):
        if _LETRA.match(p):
            continue
        actual.append(p)
        m = _CIERRE.search(p)
        if m:
            ref = re.sub(r"\s+", "", m.group(1))
            secciones.append({"seccion": "extracto", "titulo": ref,
                              "parrafos": [{"texto": t, "sub": ref} for t in actual]})
            actual = []
    if actual and secciones:  # cola sin cierre: va con el último extracto
        secciones[-1]["parrafos"] += [{"texto": t, "sub": secciones[-1]["titulo"]} for t in actual]

    resenas: list[dict[str, Any]] = []
    for l in lineas[ini_b:fin]:
        m = _REF_SOLA.match(l)
        if m:
            resenas.append({"seccion": "providencia", "titulo": re.sub(r"\s+", "", m.group(1)), "lineas": []})
        elif resenas:
            resenas[-1]["lineas"].append(l)
    for r in resenas:
        secciones.append({"seccion": "providencia", "titulo": r["titulo"],
                          "parrafos": [{"texto": t, "sub": r["titulo"]} for t in _parrafos(r["lineas"])]})

    refs = Counter(s["titulo"] for s in secciones)
    return {
        "ficha": {"ponentes": [], "fecha": None, "referencia": None, "otros": [], "resuelve": []},
        "descriptores": [],
        "secciones": secciones,
        "qa": {
            "ponentes": [],
            "caracteres_por_seccion": {k: sum(len(p["texto"]) for s in secciones if s["seccion"] == k
                                              for p in s["parrafos"]) for k in ("extracto", "providencia")},
            "n_extractos": sum(s["seccion"] == "extracto" for s in secciones),
            "n_providencias": len(resenas),
            "providencias_distintas": len(refs),
            "sin_decision": False,
            "sin_texto": not secciones,
        },
    }
