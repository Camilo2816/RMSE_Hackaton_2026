"""Rutas canónicas del repo (corpus/, data/, eval/...).

Todas absolutas y derivadas de la raíz del repo, para que los módulos funcionen
igual desde `python -m`, pytest o la API.
"""
from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]

DATA = RAIZ / "data"
SCRIPTS = RAIZ / "scripts"
SOURCES = RAIZ / "sources"
URLS_LOCK = SOURCES / "urls.lock.json"
INVENTARIO_XLSX = RAIZ / "docs" / "inventario_fuentes_corpus.xlsx"

CORPUS = RAIZ / "corpus"
RAW = CORPUS / "raw"                  # originales descargados, uno por carpeta <doc_id>/
INTERIM = CORPUS / "interim"          # estructura extraída <doc_id>.json (artículos/secciones)
PROCESSED = CORPUS / "processed"      # <doc_id>.txt + fragmentos/<doc_id>.jsonl + fragmentos.jsonl
FRAGMENTOS_DIR = PROCESSED / "fragmentos"
FRAGMENTOS = PROCESSED / "fragmentos.jsonl"
INDEX = CORPUS / "index"
DIST = CORPUS / "dist"

MANIFEST = RAIZ / "corpus_manifest.json"
EVAL_RUNS = RAIZ / "eval" / "runs"
