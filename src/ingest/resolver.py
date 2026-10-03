"""Resuelve la URL directa de cada documento de sources/ y la fija en sources/urls.lock.json.

Las URL del seed son búsquedas (`?q=`), no documentos. Para cada documento se
prueban patrones conocidos por fuente y se valida el CONTENIDO, no el código
HTTP: la relatoría de la Corte Constitucional responde 200 con una página de
error de ~8 KB cuando el archivo no existe.

Patrones verificados (2026-09-28):
- Senado: basedoc/ley_0472_1998.html (número con 4 dígitos); códigos con nombre
  propio (codigo_civil.html, codigo_procedimental_laboral.html, ...).
- Corte Constitucional: relatoria/2006/C-355-06.htm; las SU van sin guion:
  relatoria/2025/SU277-25.htm.
- Comunidad Andina: StaticFiles/DocOf/DEC486.pdf.
- Corte Suprema: sin patrón (carpeta por boletín mensual); la URL va en el YAML.

Un `url` no vacío en el YAML manda sobre los patrones (se valida igual). Lo que no
se resuelve queda `no_encontrado` o `manual` en el lock para resolverlo a mano.

    python -m src.ingest.resolver [--ola 0 1] [--ids ley_472_1998 ...] [--forzar]
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import date
from typing import Any

from src.common import rutas
from src.ingest import fuentes
from src.ingest.fuentes import Doc
from src.ingest.red import Cliente, decodificar, sin_scripts

SENADO = "http://www.secretariasenado.gov.co/senado/basedoc/"
CORTE_CONST = "https://www.corteconstitucional.gov.co/relatoria/"
CAN = "https://www.comunidadandina.org/StaticFiles/DocOf/"

# Documentos del Senado cuyo archivo no sigue el patrón tipo_NNNN_AAAA
# (tomados del índice de códigos del Senado, basedoc/arbol/).
SENADO_NOMBRES = {
    "constitucion": "constitucion_politica_1991.html",
    "codigo_civil": "codigo_civil.html",
    "codigo_comercio": "codigo_comercio.html",
    "codigo_sustantivo_trabajo": "codigo_sustantivo_trabajo.html",
    "codigo_procesal_trabajo": "codigo_procedimental_laboral.html",
    "estatuto_tributario": "estatuto_tributario.html",
    "codigo_general_proceso": "ley_1564_2012.html",
    "cpaca": "ley_1437_2011.html",
    "codigo_penal": "ley_0599_2000.html",
    "codigo_procedimiento_penal": "ley_0906_2004.html",
    "codigo_infancia": "ley_1098_2006.html",
    "codigo_nacional_policia": "ley_1801_2016.html",
    "codigo_disciplinario": "ley_1952_2019.html",
    "estatuto_consumidor": "ley_1480_2011.html",
    "decreto_663_1993": "estatuto_organico_sistema_financiero.html",
}

MIN_BYTES = 12_000  # la página de error de la Corte pesa ~8,6 KB
MIN_BYTES_LEGALIZE = 2_000  # Markdown sin plantilla HTML: un decreto corto pesa 6-10 KB


def candidatos(d: Doc) -> list[tuple[str, str]]:
    """[(url, parser)] en orden de preferencia."""
    doc_id, tipo = d["doc_id"], d.get("tipo")
    can = d.get("canonico") or [None, None, None]
    out: list[tuple[str, str]] = []
    if doc_id in SENADO_NOMBRES:
        out.append((SENADO + SENADO_NOMBRES[doc_id], "senado"))
    if can[0] in ("ley", "decreto") and can[1] and can[1].isdigit():
        out.append((f"{SENADO}{can[0]}_{int(can[1]):04d}_{can[2]}.html", "senado"))
    if tipo == "sentencia" and can[0] == "jurisprudencia":
        sala, num = can[1].split("-")
        if sala in ("C", "T", "SU"):
            anio = can[2]
            sep = "" if sala == "SU" else "-"
            out.append((f"{CORTE_CONST}{anio}/{sala}{sep}{int(num):03d}-{anio[2:]}.htm",
                        "corte_constitucional"))
    if tipo == "decision_andina":
        m = re.search(r"\b(\d{3})\b", f"{d.get('numero') or ''} {d['nombre_citable']}")
        if m:
            out.append((f"{CAN}DEC{int(m.group(1))}.pdf", "pdf"))
    return out


def parser_de_url(url: str) -> str:
    if ("secretariasenado.gov.co" in url or "cancilleria.gov.co/normograma" in url
            or "normograma.dian.gov.co" in url):
        return "senado"  # los normogramas de Cancillería y DIAN usan el mismo formato (Avance Jurídico)
    if "corteconstitucional.gov.co" in url:
        return "corte_constitucional"
    if "funcionpublica.gov.co/eva/gestornormativo" in url:
        return "funcion_publica"
    if "raw.githubusercontent.com/legalize-dev/" in url:
        return "legalize"  # Markdown de legalize-co fijado a un commit (texto de SUIN-Juriscol)
    if "cortesuprema.gov.co" in url:
        return "pdf_sentencia"  # relatoría de la CSJ: PDF, también tras enlaces sin extensión
    if url.lower().endswith(".pdf"):
        return "pdf"
    return "manual"


def _numero_en(texto: str, d: Doc) -> bool:
    """El documento descargado es el que se pidió (número y año visibles al inicio)."""
    can = d.get("canonico") or [None, None, None]
    t = texto[:60_000]
    if can[0] == "jurisprudencia":
        sala, num = can[1].split("-")
        yy = can[2][2:]
        return bool(re.search(rf"{sala}\s*-?\s*0*{int(num)}\s*(?:/|-|de)\s*(?:{can[2]}|{yy})\b",
                              t, re.I))
    if can[1] and can[1].isdigit():
        n = int(can[1])
        return bool(re.search(rf"\b0*{n}\b", t)) and (can[2] or "") in t
    return True  # códigos con nombre propio: basta la estructura


def validar(resp, d: Doc, parser: str) -> str | None:
    """None si la respuesta es el documento; si no, el motivo del rechazo."""
    if resp.status != 200:
        return f"HTTP {resp.status}"
    if len(resp.contenido) < (MIN_BYTES_LEGALIZE if parser == "legalize" else MIN_BYTES):
        return f"muy pequeño ({len(resp.contenido)} bytes)"
    if parser in ("pdf", "pdf_sentencia", "relatoria_csj"):
        return None if resp.contenido[:5] == b"%PDF-" else "no es PDF"
    html = sin_scripts(decodificar(resp.contenido, resp.content_type))
    if parser == "senado" and "<!--Inicio documento-->" not in html and "panel-documento" not in html:
        return "sin marcador de documento del Senado"
    if not _numero_en(html, d):
        return "número o año ausentes del contenido"
    return None


def resolver_doc(cli: Cliente, d: Doc) -> dict[str, Any]:
    manual = (d.get("url") or "").strip()
    # `parser` en el YAML manda cuando el dominio no basta (compilaciones de la Relatoría de la CSJ).
    probar = [(manual, d.get("parser") or parser_de_url(manual))] if manual else candidatos(d)
    probadas = []
    for url, parser in probar:
        if parser == "manual":
            probadas.append({"url": url, "motivo": "fuente sin parser"})
            continue
        resp = cli.get(url)
        motivo = validar(resp, d, parser)
        probadas.append({"url": url, "motivo": motivo or "ok"})
        if motivo is None:
            return {"estado": "ok", "url": url, "parser": parser,
                    "origen_url": "yaml" if manual else "patron",
                    "fecha": date.today().isoformat(), "probadas": probadas}
    return {"estado": "no_encontrado" if probar else "manual", "url": None, "parser": None,
            "fecha": date.today().isoformat(), "probadas": probadas}


def cargar_lock() -> dict[str, Any]:
    if rutas.URLS_LOCK.exists():
        return json.loads(rutas.URLS_LOCK.read_text(encoding="utf-8"))
    return {}


def guardar_lock(lock: dict[str, Any]) -> None:
    rutas.URLS_LOCK.write_text(
        json.dumps(dict(sorted(lock.items())), ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8", newline="\n")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ola", type=int, nargs="*")
    ap.add_argument("--ids", nargs="*")
    ap.add_argument("--forzar", action="store_true", help="re-resolver también los ok")
    ap.add_argument("--pausa", type=float, default=1.0)
    args = ap.parse_args()

    docs = fuentes.cargar()
    lock = cargar_lock()
    cli = Cliente(pausa=args.pausa)
    for d in fuentes.seleccionar(docs, args.ola, args.ids):
        previo = lock.get(d["doc_id"], {})
        url_yaml = (d.get("url") or "").strip()
        if previo.get("estado") == "ok" and not args.forzar                 and (not url_yaml or previo.get("url") == url_yaml):
            continue
        res = resolver_doc(cli, d)
        lock[d["doc_id"]] = res
        guardar_lock(lock)  # tras cada documento: una interrupción no pierde lo resuelto
        print(f"{res['estado']:14s} {d['doc_id']:40s} {res['url'] or ''}", flush=True)


if __name__ == "__main__":
    main()
