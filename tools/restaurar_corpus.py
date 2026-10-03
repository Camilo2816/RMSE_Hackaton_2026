"""Restaura el corpus e índice publicados (corpus_RMSE.zip, enlace en el README) en corpus/.

El zip trae la estructura que pide el kit (corpus/, indice/); el sistema los lee de:

    corpus/<doc_id>.txt    -> corpus/processed/<doc_id>.txt
    indice/chunks.jsonl    -> corpus/processed/fragmentos.jsonl y corpus/index/metadata.jsonl
    indice/embeddings.npy  -> corpus/index/embeddings.npy
    indice/bm25/*          -> corpus/index/bm25/*
    indice/config.json     -> corpus/index/config.json

Verifica al final que la huella (sha256) de los fragmentos coincida con la del índice.

    python tools/restaurar_corpus.py corpus_RMSE.zip [--destino <raíz del repositorio>]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for b in iter(lambda: fh.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("zip", type=Path)
    ap.add_argument("--destino", type=Path, default=RAIZ, help="raíz del repositorio (por defecto, esta)")
    args = ap.parse_args()
    proc, idx = args.destino / "corpus" / "processed", args.destino / "corpus" / "index"
    (idx / "bm25").mkdir(parents=True, exist_ok=True)
    proc.mkdir(parents=True, exist_ok=True)

    destinos = {"indice/chunks.jsonl": proc / "fragmentos.jsonl", "indice/embeddings.npy": idx / "embeddings.npy",
                "indice/config.json": idx / "config.json"}
    n_txt = 0
    with zipfile.ZipFile(args.zip) as z:
        for info in z.infolist():
            nombre = info.filename
            if nombre.endswith("/"):
                continue
            if nombre.startswith("corpus/") and nombre.endswith(".txt"):
                salida = proc / Path(nombre).name
                n_txt += 1
            elif nombre.startswith("indice/bm25/"):
                salida = idx / "bm25" / Path(nombre).name
            elif nombre in destinos:
                salida = destinos[nombre]
            else:
                continue  # LICENSE, LEEME.md, corpus_manifest.json (el repo ya trae el suyo)
            with z.open(info) as src, salida.open("wb") as dst:
                shutil.copyfileobj(src, dst, 1 << 22)
    shutil.copyfile(proc / "fragmentos.jsonl", idx / "metadata.jsonl")

    config = json.loads((idx / "config.json").read_text(encoding="utf-8"))
    huella = _sha256(proc / "fragmentos.jsonl")
    if huella != config["sha256_fragmentos"]:
        raise SystemExit(f"la huella de los fragmentos ({huella[:12]}…) no es la del índice ({config['sha256_fragmentos'][:12]}…)")
    print(f"{n_txt} documentos en {proc} · índice en {idx} · {config['n_fragmentos']} fragmentos · huella {huella[:12]}… OK")


if __name__ == "__main__":
    main()
