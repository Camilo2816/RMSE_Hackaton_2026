"""Regenera el inventario del corpus desde corpus_manifest.json.

El enunciado (paso 5) pide un registro por documento que coincida con el manifiesto. Con la
relatoría completa son ~29.000 filas (6 MB), que GitHub no muestra dentro de CORPUS.md, así que:

- CORPUS.md, sección "## Anexo — Inventario de la selección manual": los documentos elegidos uno a
  uno (todo salvo la relatoría cosechada por número, sources/relatoria_cc.yaml);
- docs/INVENTARIO_COMPLETO.md: los 29.000+ documentos del manifiesto, una fila por documento.

    python tools/inventario_corpus.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
TITULO = "## Anexo — Inventario de la selección manual"
TITULOS_PREVIOS = ("## Anexo — Inventario completo",)
COMPLETO = RAIZ / "docs" / "INVENTARIO_COMPLETO.md"
COLUMNAS = """Columnas: identificador, título (nombre citable), fuente, URL de la que se tomó el texto, fecha
de consulta, número de artículos (en sentencias, que se segmentan por sección, el número de
fragmentos) y áreas del banco a las que responde.

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
    relatoria = set(re.findall(r'^  - doc_id: "([^"]+)"',
                               (RAIZ / "sources" / "relatoria_cc.yaml").read_text(encoding="utf-8"), re.M))
    docs = sorted(manifiesto["documentos"], key=lambda d: d["doc_id"])
    manuales = [d for d in docs if d["doc_id"] not in relatoria]

    corpus = RAIZ / "CORPUS.md"
    texto = corpus.read_text(encoding="utf-8")
    titulo = next((t for t in (TITULO, *TITULOS_PREVIOS) if t in texto), None)
    if titulo is None:
        raise SystemExit(f"CORPUS.md no tiene la sección '{TITULO}'")
    anexo = (f"{TITULO}\n\nGenerado por `tools/inventario_corpus.py` desde `corpus_manifest.json` (mismo `doc_id`, URL\n"
             f"y fecha de consulta). Lista los {len(manuales)} documentos seleccionados uno a uno. El inventario\n"
             f"completo, con las {len(docs) - len(manuales)} sentencias de la relatoría de la Corte Constitucional "
             f"cosechadas por número\n(área constitucional por defecto: no se clasificaron una a una), está en\n"
             f"[`docs/INVENTARIO_COMPLETO.md`](docs/INVENTARIO_COMPLETO.md): {len(docs)} filas, una por documento del manifiesto.\n\n"
             + COLUMNAS + "\n".join(fila(d) for d in manuales) + "\n")
    corpus.write_text(texto.split(titulo)[0] + anexo, encoding="utf-8", newline="\n")

    COMPLETO.parent.mkdir(parents=True, exist_ok=True)
    COMPLETO.write_text(
        f"# Inventario completo del corpus — {manifiesto.get('equipo') or 'equipo'}\n\n"
        f"Un registro por documento de `corpus_manifest.json` ({len(docs)} documentos; generado por\n"
        f"`tools/inventario_corpus.py`). Criterio, método y evolución: [`CORPUS.md`](../CORPUS.md).\n\n"
        + COLUMNAS + "\n".join(fila(d) for d in docs) + "\n", encoding="utf-8", newline="\n")
    print(f"CORPUS.md: {len(manuales)} documentos, {corpus.stat().st_size / 1e3:.0f} KB · "
          f"{COMPLETO.relative_to(RAIZ)}: {len(docs)} documentos, {COMPLETO.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
