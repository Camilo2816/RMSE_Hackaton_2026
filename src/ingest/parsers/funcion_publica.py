"""Parser del Gestor Normativo de Función Pública (norma.php?i=N).

Se usa para normas que el Senado no publica: decretos únicos reglamentarios
(1072/2015, 1625/2016, 2555/2010...) y leyes antiguas (Ley 153 de 1887, Ley 50 de
1990...). La página HTML trae el texto completo, así que no hace falta el PDF.

Estructura (verificada en Ley 54/1990, Ley 50/1990 y Decreto 1072/2015):
- Todo el texto en `<p>` (y algunas `<ol>`/`<table>`) dentro de `div.descripcion-contenido`.
- Artículos: "ARTÍCULO 1." / "Artículo 2o." / "ARTÍCULO 2.2.1.1.1.1." (numeración de
  los decretos únicos). A veces el número va solo en un párrafo y el texto en el
  siguiente. Las anclas (`<a id="sp73">`) existen solo en parte de los artículos.
- Las leyes de reforma reproducen el artículo que modifican ("ARTÍCULO 1º. El
  artículo 23 del Código Sustantivo del Trabajo quedará así: / Artículo 23. ..."):
  ese "Artículo 23." no abre artículo (mismo criterio que parsers/senado.py).
- Jerarquía LIBRO / PARTE / TÍTULO / CAPÍTULO / SECCIÓN en párrafos propios; el orden
  de los niveles varía (en los decretos únicos, LIBRO > PARTE > TÍTULO).
- Notas en línea: "NOTA: ..." (vigencia, exequibilidad) van a las notas del artículo.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import lxml.html

from src.ingest.parsers.senado import _FIRMAS, _epigrafe
from src.ingest.red import decodificar, sin_scripts

_ARTICULO = re.compile(
    r"^(?:ART[ÍI]CULO|Art[íi]culo)\s+"
    r"(?P<trans>(?:TRANSITORIO|Transitorio)\s*)?"
    r"(?P<num>\d+(?:\.\d+)*(?:\s*-\s*\d+)?[A-Z]?(?:\s+(?:BIS|bis|Bis))?)?"
    r"\s*(?:[oº°](?![A-Za-zÁÉÍÓÚÑáéíóúñ]))?\s*[.\-–:]?")
_NIVEL = re.compile(r"^(LIBRO|PARTE|T[ÍI]TULO|CAP[ÍI]TULO|SUBSECCI[ÓO]N|SECCI[ÓO]N)\b", re.I)
_NOTA = re.compile(r"^NOTA\s*\d*\s*:", re.I)
_DADA = re.compile(r"^Dad[ao] en\b")  # "Dada en Bogotá, D.E., a 28 de diciembre de 1990."
# "DECRETA:" antes del artículo 1 es la fórmula de promulgación, no "… quedará así:".
_PROMULGACION = re.compile(r"\b(?:DECRETA|DECRETAN|RESUELVE|ACUERDA|ORDENA)\s*:$", re.I)
MAX_SALTO = 10


def _limpio(s: str) -> str:
    # La fuente trae algunos párrafos doblemente codificados ("Â\xad", "Â§", "Â·"): se
    # quita la "Â" espuria y los guiones suaves, que no aportan texto.
    s = re.sub("Â([\u0080-¿])", r"\1", s).replace("\xad", "")
    s = re.sub("[\u0080-\u009f]", "", s)  # controles C1 (fórmulas mal codificadas en la fuente)
    return re.sub(r"\s+", " ", s.replace("\xa0", " ")).strip()


def _bloques(contenedor) -> list[tuple[str, bool]]:
    """(texto, tiene_ancla) de cada bloque del contenido, en orden."""
    out = []
    for el in contenedor:
        tag = el.tag if isinstance(el.tag, str) else ""
        if tag in ("script", "style"):
            continue
        for s in el.xpath(".//s|.//strike|.//del"):
            s.drop_tree()
        if tag in ("ol", "ul"):
            for li in el.xpath("./li"):
                t = _limpio(li.text_content())
                if t:
                    out.append((t, False))
            continue
        if tag == "table":
            filas = [" | ".join(_limpio(c.text_content()) for c in tr.xpath("./td|./th"))
                     for tr in el.xpath(".//tr")]
            t = "\n".join(f for f in filas if f.strip(" |"))
            if t:
                out.append((t, False))
            continue
        t = _limpio(el.text_content())
        if t:
            out.append((t, bool(el.xpath(".//a[@id]"))))
    return out


def _numero(texto: str) -> str | None:
    m = _ARTICULO.match(texto)
    if not m or not (m.group("num") or m.group("trans")):
        return None
    num = re.sub(r"\s+", " ", (m.group("num") or "").replace(" - ", "-")).strip().upper()
    return ("TRANSITORIO " + num).strip() if m.group("trans") else num


def _clave(num: str) -> tuple[int, ...] | None:
    """'2.2.1.1.1.1' -> (2, 2, 1, 1, 1, 1); '23A' -> (23,); transitorios -> None."""
    if num.startswith("TRANSITORIO"):
        return None
    m = re.match(r"\d+(?:\.\d+)*", num)
    return tuple(int(x) for x in m.group().split(".")) if m else None


def _sigue_secuencia(nuevo: tuple[int, ...] | None, ultimo: tuple[int, ...] | None) -> bool:
    if nuevo is None:
        return True
    if ultimo is None:
        return nuevo[-1] <= 3 or len(nuevo) > 1
    if len(ultimo) == 1 and len(nuevo) > 1:
        return False  # norma numerada en enteros que reproduce artículos de un decreto único
    if len(nuevo) > 1 or len(ultimo) > 1:
        return nuevo > ultimo  # decretos únicos: basta con que avance
    return ultimo[0] <= nuevo[0] <= ultimo[0] + MAX_SALTO


def parsear_documento(carpeta: Path, paginas: list[str]) -> dict[str, Any]:
    html = sin_scripts(decodificar((carpeta / paginas[0]).read_bytes()))
    doc = lxml.html.document_fromstring(html)
    cont = doc.xpath('//div[contains(@class,"descripcion-contenido")]')
    if not cont:
        raise ValueError("sin div.descripcion-contenido: no es una página del Gestor Normativo")
    bloques = _bloques(cont[0])

    preambulo: dict[str, Any] = {"parrafos": [], "notas": {}}
    articulos: list[dict[str, Any]] = []
    actual = preambulo
    ruta: list[tuple[int, str]] = []
    rangos: dict[str, int] = {}
    pendiente_nombre = False
    unir_siguiente = False
    ultimo: tuple[int, ...] | None = None
    en_firmas, firmas, sin_ancla = False, 0, []
    for i, (p, ancla) in enumerate(bloques):
        num = _numero(p)
        previo = actual["parrafos"][-1] if actual["parrafos"] else ""
        if num:
            clave = _clave(num)
            fin_previo = previo.rstrip(" \"'”»)")
            real = ancla or ((not fin_previo.endswith(":") or _PROMULGACION.search(fin_previo))
                             and _sigue_secuencia(clave, ultimo))
            if real:
                if not ancla:
                    sin_ancla.append(num)
                if clave is not None:
                    ultimo = clave
                actual = {"articulo": num, "ruta": [r[1] for r in ruta], "parrafos": [p],
                          "notas": {}, "pagina": paginas[0], "ancla": ancla}
                articulos.append(actual)
                unir_siguiente = len(p) < 25  # "Artículo 6o" solo; el texto viene después
                en_firmas = pendiente_nombre = False
                continue
        if articulos and (en_firmas or _FIRMAS.match(p) or _DADA.match(p)):
            en_firmas = True
            firmas += 1
            continue
        nivel = _NIVEL.match(p)
        if nivel and len(p) < 150 and not num:
            clase = re.sub(r"[ÍI]", "I", re.sub(r"[ÓO]", "O", nivel.group(1).upper()))
            if clase not in rangos:
                rangos[clase] = (ruta[-1][0] + 1) if ruta else 0
            r = rangos[clase]
            ruta = [x for x in ruta if x[0] < r] + [(r, p.rstrip(". "))]
            pendiente_nombre = len(p) < 40  # "CAPÍTULO 2" y el nombre en el párrafo siguiente
            continue
        if pendiente_nombre and ruta and len(p) < 200 and not _NOTA.match(p):
            r, etiqueta = ruta[-1]
            ruta[-1] = (r, f"{etiqueta}. {p.rstrip('. ')}")
            pendiente_nombre = False
            continue
        pendiente_nombre = False
        if _NOTA.match(p):
            actual["notas"].setdefault("notas de vigencia", []).append(p)
            continue
        if unir_siguiente and actual is not preambulo:
            actual["parrafos"][-1] = f"{actual['parrafos'][-1]} {p.lstrip('. ')}"
            unir_siguiente = False
            continue
        actual["parrafos"].append(p)

    nums = [a["articulo"] for a in articulos]
    vistos: dict[str, int] = {}
    for n in nums:
        vistos[n] = vistos.get(n, 0) + 1
    return {
        "preambulo": preambulo,
        "epigrafe": _epigrafe(preambulo["parrafos"]),
        "articulos": articulos,
        "qa": {
            "n_articulos": len(nums),
            "duplicados": sorted(n for n, c in vistos.items() if c > 1),
            "saltos": [],
            "n_saltos": 0,
            "retrocesos": 0,
            "sin_ancla_aceptados": len(sin_ancla),
            "n_parrafos_firma": firmas,
            "ultimo": nums[-1] if nums else None,
        },
    }
