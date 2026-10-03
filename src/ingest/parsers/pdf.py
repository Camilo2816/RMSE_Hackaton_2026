"""Parser de normas con articulado publicadas en PDF con capa de texto.

Primer uso: Decisiones de la Comunidad Andina (DEC486.pdf, DEC351.pdf, ...), que
no están en el Senado. Produce la misma estructura que parsers/senado.py
(preámbulo, epígrafe, artículos con ruta), así que se segmenta igual.

Reglas (verificadas en la Decisión 486):
- Párrafos separados por líneas en blanco; las líneas de un párrafo se unen.
- Números de página "- 32 -" fuera.
- "Artículo 134.-" abre artículo; TÍTULO/CAPÍTULO/SECCIÓN arman la ruta, y un
  subtítulo corto sin punto final justo antes de un artículo ("De los Requisitos
  para el Registro de Marcas") se agrega como último nivel.
- En "DISPOSICIONES TRANSITORIAS/FINALES/COMPLEMENTARIAS", "PRIMERA.-" abre la
  disposición "TRANSITORIA PRIMERA".
- "Dada en la ciudad de ..." cierra el articulado (firmas fuera).

Un PDF sin capa de texto (escaneado) se reporta en `qa.sin_texto` para pasarlo
por OCR; aquí no se hace OCR.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pymupdf

_PAGINA = re.compile(r"^\s*-?\s*\d{1,3}\s*-?\s*$")
# Con mayúscula inicial: "...las disposiciones del / artículo 78." (salto de línea) es una remisión.
_ARTICULO = re.compile(r"^(?:Art[íi]culo|ART[ÍI]CULO)\s+(\d+[A-Za-z]?(?:\s*[Bb][Ii][Ss])?)\s*[.º°]?\s*[-–.:]")
_NIVEL = re.compile(r"^(T[ÍI]TULO|CAP[ÍI]TULO|SECCI[ÓO]N)\b", re.I)
_RANGO = {"T": 2, "C": 3, "S": 4}
_DISPOSICIONES = re.compile(r"^DISPOSICI[ÓO]N(?:ES)?\s+(TRANSITORIAS?|FINAL(?:ES)?|COMPLEMENTARIAS?)", re.I)
_ORDINAL = re.compile(
    r"^((?:DÉCIMO|DECIMO|VIGÉSIMO|VIGESIMO)?\s*(?:PRIMERA|SEGUNDA|TERCERA|CUARTA|QUINTA|SEXTA|"
    r"S[ÉE]PTIMA|OCTAVA|NOVENA|D[ÉE]CIMA|UND[ÉE]CIMA|DUOD[ÉE]CIMA))\s*[.\-–]+", re.I)
_CIERRE = re.compile(r"^(?:Dada en|Dado en|Firmad[oa] en)\b")
_MARCADOR = re.compile(r"[a-zñ]{1,2}\)|\d{1,2}\)|[ivx]{1,4}\)|[-•]")  # literal o viñeta sola


def _sin_simbolos(texto: str) -> str:
    """Fuentes de símbolos de Word exportan ASCII en el área privada (U+F020-U+F07E =
    ' '..'~'): se devuelven a ASCII."""
    return re.sub(r"[-]", lambda m: chr(ord(m.group()) - 0xF000), texto)


def _parrafos(texto: str) -> list[str]:
    lineas = [l for l in _sin_simbolos(texto).splitlines() if not _PAGINA.match(l)]
    bloques, actual = [], []
    for l in lineas:
        l = l.strip()
        # Además de las líneas en blanco, un artículo, un título o un literal suelto
        # siempre abren párrafo (hay PDFs que no dejan líneas en blanco).
        if l and actual and (_ARTICULO.match(l) or _NIVEL.match(l) or _DISPOSICIONES.match(l)
                             or _MARCADOR.fullmatch(l) or _MARCADOR.fullmatch(actual[-1])):
            bloques.append(actual)
            actual = []
        if l:
            actual.append(l)
        elif actual:
            bloques.append(actual)
            actual = []
    if actual:
        bloques.append(actual)
    out: list[str] = []
    for b in bloques:
        p = " ".join(b)
        p = re.sub(r"([a-záéíóúñ])- ([a-záéíóúñ])", r"\1\2", p)  # guion de corte de línea
        p = re.sub(r"\s+", " ", p).strip()
        if out and _MARCADOR.fullmatch(out[-1]):
            out[-1] = f"{out[-1]} {p}"  # "a)" o "-" suelto + su texto
        else:
            out.append(p)
    return out


def parsear_documento(carpeta: Path, paginas: list[str]) -> dict[str, Any]:
    doc = pymupdf.open(carpeta / paginas[0])
    texto = "\n".join(p.get_text() for p in doc)
    ps = _parrafos(texto)

    preambulo: dict[str, Any] = {"parrafos": [], "notas": {}}
    articulos: list[dict[str, Any]] = []
    actual: dict[str, Any] = preambulo
    ruta: list[tuple[float, str]] = []
    prefijo_disp: str | None = None
    firmas = 0
    en_firmas = False
    for i, p in enumerate(ps):
        siguiente = ps[i + 1] if i + 1 < len(ps) else ""
        m = _ARTICULO.match(p)
        disp = _ORDINAL.match(p) if prefijo_disp else None
        if m or disp:
            num = m.group(1).upper() if m else f"{prefijo_disp} {re.sub(r'\s+', ' ', disp.group(1).upper())}"
            actual = {"articulo": num, "ruta": [r[1] for r in ruta], "parrafos": [p],
                      "notas": {}, "pagina": paginas[0], "ancla": True}
            articulos.append(actual)
            en_firmas = False
            continue
        if articulos and (en_firmas or _CIERRE.match(p)):
            en_firmas = True
            firmas += 1
            continue
        nivel = _NIVEL.match(p)
        if nivel and len(p) < 120:
            rango = _RANGO[nivel.group(1)[0].upper()]
            # El nombre del título suele venir en el párrafo siguiente, en mayúsculas.
            nombre = siguiente if siguiente.isupper() and not _NIVEL.match(siguiente) \
                and not _ARTICULO.match(siguiente) and len(siguiente) < 150 else ""
            ruta = [r for r in ruta if r[0] < rango] + [(rango, f"{p}. {nombre}".strip(". "))]
            prefijo_disp = None
            continue
        d = _DISPOSICIONES.match(p)
        if d and len(p) < 80:
            clase = d.group(1).upper()
            prefijo_disp = "TRANSITORIA" if clase.startswith("TRANS") else \
                "FINAL" if clase.startswith("FINAL") else "COMPLEMENTARIA"
            ruta = [r for r in ruta if r[0] < 2] + [(2, p)]
            continue
        if ruta and p == ruta[-1][1].split(". ", 1)[-1]:
            continue  # nombre de título ya usado en la ruta
        es_subtitulo = (len(p) < 110 and not p.endswith((".", ":", ";", ",")) and
                        bool(_ARTICULO.match(siguiente)) and not p.isupper())
        if es_subtitulo:
            ruta = [r for r in ruta if r[0] < 5] + [(5, p)]
            continue
        actual["parrafos"].append(p)

    nums = [a["articulo"] for a in articulos]
    vistos: dict[str, int] = {}
    for n in nums:
        vistos[n] = vistos.get(n, 0) + 1
    enteros = [int(m.group()) for n in nums if (m := re.match(r"\d+", n))]
    epigrafe = next((p for p in preambulo["parrafos"][:15]
                     if re.match(r"^(?:R[ée]gimen|Por (?:la|el) cual|Sobre)\b", p, re.I)), None)
    return {
        "preambulo": preambulo,
        "epigrafe": epigrafe,
        "articulos": articulos,
        "qa": {
            "n_articulos": len(nums),
            "duplicados": sorted(n for n, c in vistos.items() if c > 1),
            "saltos": [(x, y) for x, y in zip(enteros, enteros[1:]) if y > x + 1][:50],
            "n_saltos": sum(1 for x, y in zip(enteros, enteros[1:]) if y > x + 1),
            "retrocesos": sum(1 for x, y in zip(enteros, enteros[1:]) if y < x),
            "ultimo": nums[-1] if nums else None,
            "n_parrafos_firma": firmas,
            "sin_texto": len(texto.strip()) < 200 * max(doc.page_count, 1),
            "paginas_pdf": doc.page_count,
        },
    }
