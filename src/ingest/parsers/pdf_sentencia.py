"""Parser de sentencias de la Corte Suprema de Justicia publicadas en PDF con capa de texto.

Produce la misma estructura que parsers/corte_constitucional.py (ficha + secciones con
párrafos y subtítulo vigente), así que se segmenta con segmentar.fragmentos_sentencia.

Reglas (verificadas en SL3385-2022, SP1680-2022, SC425-2024):
- Fuera: números de página y encabezados corridos (una línea idéntica en ≥ 3 páginas,
  p. ej. el nombre del procesado en cada página de una SP).
- Títulos en mayúsculas, solos en su línea, abren sección según `_SECCIONES`
  (ANTECEDENTES, LA DEMANDA DE CASACIÓN, CONSIDERACIONES, DECISIÓN, SALVAMENTO...).
  Los demás títulos cortos en mayúsculas (CARGO PRIMERO, RÉPLICA) son el subtítulo.
- Ficha: ponente (línea antes de "Magistrado/a ponente"), referencia (SL3385-2022 +
  radicación), fecha ("Bogotá, ... (2022)") y las primeras líneas de la decisión.
- Un párrafo termina en una línea que cierra con . : ; » ” o antes de un título.

Un PDF sin capa de texto (escaneado) se reporta en `qa.sin_texto`; aquí no se hace OCR:
si existe corpus/raw/<doc_id>/ocr.json (src/ingest/ocr.py), se leen sus líneas en lugar
de la capa de texto del PDF.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import pymupdf

from src.ingest.parsers.corte_constitucional import ORDEN, _TERMINALES

_PAGINA = re.compile(r"^\s*(?:-\s*)?\d{1,3}(?:\s*-)?\s*$")
_NUMERAL = r"(?:[IVXL]{1,5}\.|\d{1,2}\.)?\s*"
_SECCIONES = [
    ("salvamento_voto", re.compile(rf"^{_NUMERAL}SALVAMENTO\s+(?:PARCIAL\s+)?DE\s+VOTO\b")),
    ("aclaracion_voto", re.compile(rf"^{_NUMERAL}ACLARACI[ÓO]N\s+DE\s+VOTO\b")),
    # FALLA (también "F A L L A"): Consejo de Estado
    ("decision", re.compile(rf"^{_NUMERAL}(?:DECISI[ÓO]N|RESUELVE|F\s*A\s*L\s*L\s*A)\s*:?$")),
    ("consideraciones", re.compile(rf"^{_NUMERAL}(?:CONSIDERACIONES|CONSIDERACIONES DE LA (?:CORTE|SALA))\b")),
    ("demanda", re.compile(rf"^{_NUMERAL}(?:LA DEMANDA|DEMANDA DE CASACI[ÓO]N|RECURSO DE CASACI[ÓO]N|"
                           rf"EL RECURSO|LA IMPUGNACI[ÓO]N|ALCANCE DE LA IMPUGNACI[ÓO]N)\b")),
    ("antecedentes", re.compile(rf"^{_NUMERAL}(?:ANTECEDENTES|HECHOS|ACTUACI[ÓO]N PROCESAL|"
                                rf"SENTENCIA DE (?:PRIMERA|SEGUNDA) INSTANCIA|LA SENTENCIA|"
                                rf"LOS ARGUMENTOS DEL TRIBUNAL|EL FALLO)\b")),
]
_TITULO = re.compile(r"^[^a-záéíóúñ]{4,70}$")
_FIN_PARRAFO = re.compile(r"[.:;»”\"]\s*$")
_PONENTE = re.compile(r"^Magistrad[oa]s?\s+[Pp]onentes?$")
_PONENTE_EN_LINEA = re.compile(r"^(?:Consejer|Magistrad)[oa]\s+ponente\s*:\s*(.+)$", re.I)  # Consejo de Estado
_REFERENCIA = re.compile(r"\b(?:(?:SL|SP|SC|STC|STL|STP|AC|AL|AP)\s*-?\s*\d{1,5}\s*-\s*\d{4}|\d{4}CE-SUJ-\d-\d{3})\b")
_FECHA = re.compile(r"^(Bogot[áa],?\s.*?\(\s*\d\.?\d{3}\s*\))")


def _lineas(paginas: list[list[str]]) -> list[str]:
    """Líneas del documento sin números de página ni encabezados corridos."""
    paginas = [[l.strip() for l in ls] for ls in paginas]
    por_pagina = Counter(l for ls in paginas for l in set(ls) if l)
    corridos = {l for l, n in por_pagina.items() if n >= 3 and len(l) < 120
                and not any(rx.match(l) for _, rx in _SECCIONES)}  # tres "ACLARACIÓN DE VOTO" no son un encabezado
    return [l for ls in paginas for l in ls if l and not _PAGINA.match(l) and l not in corridos]


def _seccion_de(linea: str) -> str | None:
    if not _TITULO.match(linea):
        return None
    return next((s for s, rx in _SECCIONES if rx.match(linea)), None)


def parsear_documento(carpeta: Path, paginas: list[str]) -> dict[str, Any]:
    # ocr.json (src/ingest/ocr.py): PDF escaneado o ilegible · texto.json (importar_samai.py): DOC/DOCX
    lateral = next((carpeta / n for n in ("ocr.json", "texto.json") if (carpeta / n).exists()), None)
    if lateral:
        lineas = _lineas(json.loads(lateral.read_text(encoding="utf-8"))["paginas"])
    else:
        lineas = _lineas([p.get_text().splitlines() for p in pymupdf.open(carpeta / paginas[0])])
    ficha: dict[str, Any] = {"ponentes": [], "fecha": None, "referencia": None, "otros": [], "resuelve": []}
    secciones: list[dict[str, Any]] = []
    actual = {"seccion": "cuerpo", "titulo": None, "parrafos": []}
    sub: str | None = None
    buffer: list[str] = []

    def cerrar_parrafo() -> None:
        if buffer:
            actual["parrafos"].append({"texto": re.sub(r"\s+", " ", " ".join(buffer)).strip(), "sub": sub})
            buffer.clear()

    i_ponente = -99  # el encabezado (fecha, radicación) va justo después del ponente
    for i, l in enumerate(lineas):
        if _PONENTE.match(l) and i and not ficha["ponentes"]:
            ficha["ponentes"].append(lineas[i - 1].title())
            i_ponente = i
            continue
        if (m := _PONENTE_EN_LINEA.match(l)) and not ficha["ponentes"]:
            ficha["ponentes"].append(m.group(1).strip().title())
            i_ponente = i
            continue
        cerca = i - i_ponente <= 4  # en el PDF de la DIAN el encabezado viene tras la ficha de relatoría
        if ficha["referencia"] is None and _REFERENCIA.search(l) and (i < 40 or cerca):
            ficha["referencia"] = re.sub(r"\s+", " ", l)
        if ficha["fecha"] is None and (i < 60 or cerca) and l.startswith("Bogot"):
            m = _FECHA.match(" ".join(lineas[i:i + 3]))  # la fecha suele partirse en dos líneas
            ficha["fecha"] = m.group(1) if m else None
        seccion = _seccion_de(l)
        if seccion and (ORDEN.get(seccion, 99) >= ORDEN.get(actual["seccion"], 0)
                        or seccion in _TERMINALES) and not (actual["seccion"] in _TERMINALES
                                                            and seccion not in _TERMINALES):
            cerrar_parrafo()
            if actual["parrafos"]:
                secciones.append(actual)
            actual = {"seccion": seccion, "titulo": l, "parrafos": []}
            sub = None
            continue
        if _TITULO.match(l) and len(l) <= 60 and not buffer:
            cerrar_parrafo()
            sub = l
            continue
        buffer.append(l)
        if _FIN_PARRAFO.search(l):
            cerrar_parrafo()
    cerrar_parrafo()
    if actual["parrafos"]:
        secciones.append(actual)

    decision = next((s for s in secciones if s["seccion"] == "decision"), None)
    if decision:
        ficha["resuelve"] = [p["texto"] for p in decision["parrafos"][:4]]
    caracteres = sum(len(l) for l in lineas)
    return {
        "ficha": ficha,
        "descriptores": [],
        "secciones": secciones,
        "qa": {
            "ponentes": ficha["ponentes"],
            "caracteres_por_seccion": {s["seccion"]: sum(len(p["texto"]) for p in s["parrafos"])
                                       for s in secciones},
            "sin_decision": decision is None,
            "sin_texto": caracteres < 500,
        },
    }
