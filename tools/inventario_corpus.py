"""Regenera el anexo "Inventario completo" de CORPUS.md desde corpus_manifest.json.

El enunciado (paso 5) pide un registro por documento que coincida con el manifiesto: con la
relatoría completa son ~29.000 filas, así que la tabla se genera, no se edita a mano. Reemplaza
todo lo que sigue al título "## Anexo — Inventario completo".

    python tools/inventario_corpus.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
TITULO = "## Anexo — Inventario completo"
ENCABEZADO = """Generado por `tools/inventario_corpus.py` desde `corpus_manifest.json` (mismo `doc_id`, URL
y fecha de consulta). Columnas: identificador, título (nombre citable), fuente, URL de la que se
tomó el texto, fecha de consulta, número de artículos (en sentencias, que se segmentan por
sección, el número de fragmentos) y áreas del banco a las que responde. Las sentencias de la
relatoría de la Corte Constitucional cosechadas por número llevan el área constitucional por
defecto: no se clasificaron una a una.

| doc_id | Título | Fuente | URL | Fecha de consulta | Artículos | Áreas |
|---|---|---|---|---|---:|---|
"""


def area_corta(a: str) -> str:
    return re.sub(r"\s*\[.*\]$", "", a).removeprefix("Derecho ").removeprefix("de los ").capitalize()


def fila(d: dict) -> str:
    articulos = str(d["n_articulos"]) if d.get("n_articulos") else f"— ({d.get('n_fragmentos', 0)} fragm.)"
    celdas = [f"`{d['doc_id']}`", d["titulo"], d["fuente"], d["url"], d["fecha_consulta"], articulos,
              ", ".join(area_corta(a) for a in d["areas"])]
    return "| " + " | ".join(str(c).replace("|", "/") for c in celdas) + " |"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    manifiesto = json.loads((RAIZ / "corpus_manifest.json").read_text(encoding="utf-8"))
    corpus = RAIZ / "CORPUS.md"
    texto = corpus.read_text(encoding="utf-8")
    if TITULO not in texto:
        raise SystemExit(f"CORPUS.md no tiene la sección '{TITULO}'")
    filas = [fila(d) for d in sorted(manifiesto["documentos"], key=lambda d: d["doc_id"])]
    nuevo = texto.split(TITULO)[0] + TITULO + "\n\n" + ENCABEZADO + "\n".join(filas) + "\n"
    corpus.write_text(nuevo, encoding="utf-8", newline="\n")
    print(f"{len(filas)} documentos en el anexo · CORPUS.md {len(nuevo.encode('utf-8')) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
