"""Parser de la Circular Básica Jurídica de la Superintendencia Financiera (C.E. 029 de 2014).

La SFC la publica como un zip con un archivo por capítulo o anexo (DOC, DOCX o PDF),
en carpetas PARTE / Título (src/ingest/importar_sfc.py lo copia a corpus/raw/). Se
modela como una sola norma con articulado, para segmentar.fragmentos_ley:

- ruta: el encabezado del capítulo ("PARTE I. INSTRUCCIONES...", "TÍTULO III. ...",
  "CAPÍTULO II: ...") y el numeral de primer nivel en mayúsculas ("1. SISTEMA DE
  ATENCIÓN AL CONSUMIDOR FINANCIERO (SAC)");
- unidad ("artículo"): cada numeral de segundo nivel ("1.1. Consideraciones generales"),
  identificado como "<archivo> num. 1.1"; los numerales más profundos y las listas
  ("1. Para el cumplimiento...") quedan dentro de su unidad;
- la tabla "CONTENIDO" del inicio de cada capítulo se descarta hasta que el
  encabezado se repite;
- un anexo o formato sin numerales es una sola unidad (el segmentador la parte por tamaño).

Texto: DOC con antiword (Latin-1), DOCX desde su XML, PDF con PyMuPDF.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pymupdf

from src.ingest.importar_samai import lineas_doc

_ENCABEZADO = re.compile(r"^(PARTE\s+[IVX]+|T[ÍI]TULO\s+[IVX]+|CAP[ÍI]TULO\s+[IVXL]+\b.*)$", re.I)
_NUM2 = re.compile(r"^(\d{1,2}\.\d{1,2})\.?\s+\S")
_NUM1_TITULO = re.compile(r"^(\d{1,2})\.\s+([^a-záéíóúñ]{4,200})$")


def _lineas(path: Path) -> list[str]:
    if path.suffix.lower() == ".pdf":
        crudas = [l for p in pymupdf.open(path) for l in p.get_text().splitlines()]
    else:
        crudas = lineas_doc(path)[1]
    return [re.sub(r"\s+", " ", l).strip() for l in crudas if l.strip()]


def _cabecera(lineas: list[str]) -> tuple[list[str], int]:
    """Ruta del capítulo (PARTE, TÍTULO, CAPÍTULO con su nombre) e índice donde empieza el cuerpo."""
    ruta: list[str] = []
    i = 0
    while i < min(len(lineas), 12):
        l = lineas[i]
        if _ENCABEZADO.match(l):
            ruta.append(l)
            if i + 1 < len(lineas) and not _ENCABEZADO.match(lineas[i + 1]) and lineas[i + 1].upper() == lineas[i + 1] \
                    and not l.upper().startswith("CAP") and not _NUM1_TITULO.match(lineas[i + 1]):
                ruta[-1] = f"{l}. {lineas[i + 1]}"
                i += 1
            i += 1
            continue
        break
    if i < len(lineas) and lineas[i].upper() == "CONTENIDO":
        ultimo = ruta[-1].split(". ")[0] if ruta else None
        j = next((k for k in range(i + 1, len(lineas)) if ultimo and lineas[k].startswith(ultimo)), None)
        if j is not None:  # salta la tabla de contenido y el encabezado repetido
            i = j + 1
            while i < len(lineas) and (_ENCABEZADO.match(lineas[i]) or lineas[i].upper() == lineas[i]
                                       and not _NUM1_TITULO.match(lineas[i]) and len(lineas[i]) < 120):
                i += 1
    return ruta, i


def parsear_documento(carpeta: Path, paginas: list[str]) -> dict[str, Any]:
    articulos: list[dict[str, Any]] = []
    errores: list[str] = []
    for rel in paginas:
        path = carpeta / rel
        try:
            lineas = _lineas(path)
        except Exception as e:  # p. ej. un .DOC que antiword no lee
            errores.append(f"{rel}: {type(e).__name__}")
            continue
        partes_ruta = Path(rel).parts[:-1]
        ruta_cap, ini = _cabecera(lineas)
        ruta_base = ruta_cap or [*partes_ruta, path.stem]
        archivo = path.stem
        sub: str | None = None
        actual: dict[str, Any] | None = None

        def abrir(num: str, primera: str) -> dict[str, Any]:
            a = {"articulo": f"{archivo} num. {num}" if num else archivo,
                 "ruta": [*ruta_base, *([sub] if sub else [])], "parrafos": [primera], "notas": {},
                 "pagina": None, "ancla": True}
            articulos.append(a)
            return a

        for l in lineas[ini:]:
            m1 = _NUM1_TITULO.match(l)
            if m1:
                sub = l
                actual = None
                continue
            m2 = _NUM2.match(l)
            if m2:
                actual = abrir(m2.group(1), l)
                continue
            if actual is None:
                actual = abrir(sub.split(".")[0] if sub else "", l)
            else:
                actual["parrafos"].append(l)

    # Tabla de contenido que _cabecera no reconoció: entradas de solo título cuyo numeral
    # reaparece después con texto.
    largo = lambda a: sum(len(p) for p in a["parrafos"])
    con_texto = {a["articulo"] for a in articulos if len(a["parrafos"]) > 1 or largo(a) > 200}
    indice = [a for a in articulos if len(a["parrafos"]) == 1 and largo(a) <= 200 and a["articulo"] in con_texto]
    articulos = [a for a in articulos if not any(a is x for x in indice)]

    nums = [a["articulo"] for a in articulos]
    vistos: dict[str, int] = {}
    for n in nums:
        vistos[n] = vistos.get(n, 0) + 1
    return {
        "preambulo": {"parrafos": [], "notas": {}},
        "epigrafe": None,
        "articulos": articulos,
        "qa": {
            "n_articulos": len(nums),
            "duplicados": sorted(n for n, c in vistos.items() if c > 1)[:50],
            "saltos": [], "n_saltos": 0, "retrocesos": 0, "sin_ancla_aceptados": [],
            "n_parrafos_firma": 0, "ultimo": nums[-1] if nums else None,
            "archivos": len(paginas), "errores": errores, "entradas_de_indice_quitadas": len(indice),
        },
    }
