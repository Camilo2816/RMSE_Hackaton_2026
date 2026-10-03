"""Extrae la estructura (artículos o secciones) de los originales de corpus/raw/.

Lee corpus/raw/<doc_id>/_descarga.json, aplica el parser de la fuente y escribe
corpus/interim/<doc_id>.json con preámbulo, artículos (ruta, párrafos, notas) y un
bloque `qa` (conteo, duplicados, saltos de numeración) para revisar la extracción.

Parsers:
- senado: src/ingest/parsers/senado.py (HTML de basedoc, varias páginas + JS de notas).
- corte_constitucional: src/ingest/parsers/corte_constitucional.py (relatoría, HTML de Word).
- pdf: src/ingest/parsers/pdf.py (normas con articulado en PDF: Decisiones Andinas).
- pdf_sentencia: src/ingest/parsers/pdf_sentencia.py (sentencias de la Corte Suprema en PDF).
- funcion_publica: src/ingest/parsers/funcion_publica.py (Gestor Normativo: decretos únicos, leyes antiguas).
- legalize: src/ingest/parsers/legalize.py (Markdown de legalize-co: texto consolidado de SUIN-Juriscol).
- relatoria_csj: src/ingest/parsers/relatoria_csj.py (gacetas y compilaciones de la Relatoría de la CSJ).
- sfc_cbj: src/ingest/parsers/sfc_cbj.py (Circular Básica Jurídica de la SFC, un archivo por capítulo).

    python -m src.ingest.extraer [--ola 0] [--ids ley_472_1998 ...]
"""
from __future__ import annotations

import argparse
import json
from typing import Any

from src.common import rutas
from src.ingest import fuentes
from src.ingest.fuentes import Doc
from src.ingest.parsers import (corte_constitucional, funcion_publica, legalize, pdf, pdf_sentencia,
                                relatoria_csj, senado, sfc_cbj)


def extraer_doc(d: Doc) -> dict[str, Any] | None:
    carpeta = rutas.RAW / d["doc_id"]
    registro = carpeta / "_descarga.json"
    if not registro.exists():
        return None
    info = json.loads(registro.read_text(encoding="utf-8"))
    if info["parser"] == "senado":
        est = senado.parsear_documento(carpeta, info["paginas"])
    elif info["parser"] == "corte_constitucional":
        est = corte_constitucional.parsear_documento(carpeta, info["paginas"])
    elif info["parser"] == "pdf":
        est = pdf.parsear_documento(carpeta, info["paginas"])
    elif info["parser"] == "pdf_sentencia":
        est = pdf_sentencia.parsear_documento(carpeta, info["paginas"])
    elif info["parser"] == "funcion_publica":
        est = funcion_publica.parsear_documento(carpeta, info["paginas"])
    elif info["parser"] == "legalize":
        est = legalize.parsear_documento(carpeta, info["paginas"])
    elif info["parser"] == "relatoria_csj":
        est = relatoria_csj.parsear_documento(carpeta, info["paginas"])
    elif info["parser"] == "sfc_cbj":
        est = sfc_cbj.parsear_documento(carpeta, info["paginas"])
    else:
        raise NotImplementedError(f"parser {info['parser']!r} pendiente")
    salida = {"doc_id": d["doc_id"], "parser": info["parser"], "url": info["url"],
              "fecha_consulta": info["fecha_consulta"], "paginas": info["paginas"], **est}
    rutas.INTERIM.mkdir(parents=True, exist_ok=True)
    (rutas.INTERIM / f"{d['doc_id']}.json").write_text(
        json.dumps(salida, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    return salida


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ola", type=int, nargs="*")
    ap.add_argument("--ids", nargs="*")
    args = ap.parse_args()
    for d in fuentes.seleccionar(fuentes.cargar(), args.ola, args.ids):
        try:
            est = extraer_doc(d)
        except NotImplementedError as e:
            print(f"pendiente      {d['doc_id']:40s} {e}")
            continue
        except Exception as e:
            print(f"error          {d['doc_id']:40s} {type(e).__name__}: {e}")
            continue
        if est is None:
            print(f"sin_descarga   {d['doc_id']}")
            continue
        qa = est["qa"]
        if est["parser"] == "relatoria_csj":
            print(f"ok             {d['doc_id']:40s} {qa['n_extractos']} extractos · {qa['n_providencias']} reseñas"
                  f" · {qa['providencias_distintas']} providencias distintas", flush=True)
        elif est["parser"] in ("corte_constitucional", "pdf_sentencia"):
            secciones = ",".join(qa["caracteres_por_seccion"])
            alerta = " · SIN DECISIÓN" if qa["sin_decision"] else ""
            print(f"ok             {d['doc_id']:40s} ponente {'/'.join(qa['ponentes']) or '?'}"
                  f" · {secciones}{alerta}", flush=True)
        else:
            print(f"ok             {d['doc_id']:40s} {qa['n_articulos']} art. · último {qa['ultimo']}"
                  f" · saltos {qa['n_saltos']} · duplicados {len(qa['duplicados'])}", flush=True)


if __name__ == "__main__":
    main()
