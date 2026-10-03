"""Parser del Markdown de legalize-co (github.com/legalize-dev/legalize-co).

legalize-co reproduce el texto consolidado de SUIN-Juriscol (Ministerio de Justicia)
en un archivo por norma; el `source` del front matter es la URL de SUIN. Se usa
para normas que el Senado no publica o publica desactualizadas (art. 99 de la Ley
79 de 1988 sin la reforma de la Ley 454 de 1998 en Función Pública). El repositorio
llega hasta 2014 y no trae jurisprudencia.

Estructura (verificada en las leyes 79/1988, 152/1994, 617/2000, 788/2002, 1066/2006,
1448/2011, 1508/2012 y 1618/2013):
- Front matter YAML entre `---`: `source` (SUIN), `gazette_reference`,
  `modification_summary` (reformas separadas por " · ", con enlaces a SUIN).
- `# título` (el epígrafe), la fórmula de promulgación y luego el articulado.
- Artículos: `##### **Artículo 1º.** texto` (solo los artículos usan `#####`).
- Jerarquía: `##`/`###`/`####` (TÍTULO, CAPÍTULO...) con el nombre en la línea siguiente.
- Listas `- 1. ...`, negrillas/cursivas `**`/`*`, enlaces `[texto](url)`.
- Firmas al final ("El Presidente del honorable Senado...", "Dada en ...").
Las notas de reforma no vienen por artículo: el `modification_summary` va al
preámbulo como "Notas de vigencia (SUIN-Juriscol)", que respalda la cita de las
leyes modificatorias igual que el resumen de notas del Senado.

Trazabilidad: la descarga es el archivo de GitHub fijado a un commit (reconstruible);
los fragmentos y el inventario llevan como URL la de SUIN (`fuente_original`), la
fuente oficial admitida por el enunciado (paso 5).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from src.ingest.parsers.senado import _FIRMAS, _epigrafe

_DADA = re.compile(r"^Dad[ao] en\b")
_ENLACE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_TITULO = re.compile(r"^(#{2,4})\s+(.*)$")
_ARTICULO = re.compile(r"^#{5,6}\s+(.*)$")
_NUMERO = re.compile(r"^art[íi]culo\s+(transitorio\b)?\s*(\d+(?:\s*[A-Z]\b|\s*bis\b)?)?", re.I)


def _limpio(s: str) -> str:
    s = _ENLACE.sub(r"\1", s)
    s = s.replace("**", "").replace("*", "").replace("\\", "")
    s = re.sub(r"^\s*-\s+", "", s)
    return re.sub(r"\s+", " ", s).strip()


def _numero(texto: str) -> str | None:
    m = _NUMERO.match(texto)
    if not m or not (m.group(1) or m.group(2)):
        return None
    num = re.sub(r"\s+", "", (m.group(2) or "")).upper().replace("BIS", " BIS")
    return ("TRANSITORIO " + num).strip() if m.group(1) else num


def front_matter(texto: str) -> tuple[dict[str, Any], str]:
    if not texto.startswith("---"):
        raise ValueError("sin front matter: no es un archivo de legalize-co")
    _, meta, cuerpo = texto.split("---", 2)
    return yaml.safe_load(meta) or {}, cuerpo


def parsear_documento(carpeta: Path, paginas: list[str]) -> dict[str, Any]:
    meta, cuerpo = front_matter((carpeta / paginas[0]).read_bytes().decode("utf-8"))
    preambulo: dict[str, Any] = {"parrafos": [], "notas": {}}
    if meta.get("gazette_reference"):
        preambulo["parrafos"].append(_limpio(str(meta["gazette_reference"])))
    articulos: list[dict[str, Any]] = []
    actual = preambulo
    ruta: list[tuple[int, str]] = []
    pendiente_nombre = en_firmas = False
    firmas = 0
    for linea in cuerpo.splitlines():
        if not linea.strip():
            continue
        art = _ARTICULO.match(linea)
        tit = _TITULO.match(linea)
        texto = _limpio(art.group(1) if art else tit.group(2) if tit else linea.lstrip("# "))
        if art and _numero(texto):
            actual = {"articulo": _numero(texto), "ruta": [r[1] for r in ruta], "parrafos": [texto],
                      "notas": {}, "pagina": None, "ancla": True}  # la URL del fragmento es la de SUIN
            articulos.append(actual)
            pendiente_nombre = en_firmas = False
            continue
        if articulos and (en_firmas or _FIRMAS.match(texto) or _DADA.match(texto)):
            en_firmas = True
            firmas += 1
            continue
        if tit:
            nivel = len(tit.group(1))
            ruta = [r for r in ruta if r[0] < nivel] + [(nivel, texto.rstrip(". "))]
            pendiente_nombre = True
            continue
        if pendiente_nombre and ruta and len(texto) < 200 and not linea.lstrip().startswith("-"):
            nivel, etiqueta = ruta[-1]
            ruta[-1] = (nivel, f"{etiqueta}. {texto.rstrip('. ')}")
            pendiente_nombre = False
            continue
        pendiente_nombre = False
        actual["parrafos"].append(texto)

    if meta.get("modification_summary"):
        reformas = [_limpio(r) for r in str(meta["modification_summary"]).split(" · ") if r.strip()]
        preambulo["parrafos"].append("Notas de vigencia (SUIN-Juriscol): " + "; ".join(reformas) + ".")

    nums = [a["articulo"] for a in articulos]
    vistos: dict[str, int] = {}
    for n in nums:
        vistos[n] = vistos.get(n, 0) + 1
    enteros = [int(m.group()) for n in nums if (m := re.match(r"\d+", n))]
    saltos = [(x, y) for x, y in zip(enteros, enteros[1:]) if y > x + 1]
    return {
        "preambulo": preambulo,
        "epigrafe": _epigrafe(preambulo["parrafos"]),
        "articulos": articulos,
        "fuente_original": meta.get("source"),
        "qa": {
            "n_articulos": len(nums),
            "duplicados": sorted(n for n, c in vistos.items() if c > 1),
            "saltos": saltos[:50],
            "n_saltos": len(saltos),
            "retrocesos": sum(1 for x, y in zip(enteros, enteros[1:]) if y < x),
            "sin_ancla_aceptados": [],
            "n_parrafos_firma": firmas,
            "ultimo": nums[-1] if nums else None,
        },
    }
