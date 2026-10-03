"""Construye el índice denso y BM25 con filas alineadas con fragmentos.jsonl.

Solo lee corpus/processed/fragmentos.jsonl (nunca data/ ni docs/kit/). Escribe en
corpus/index/ (docs/CONTRATOS.md §4):

- embeddings.npy: vectores normalizados en float16, fila i = chunk_id i;
- bm25/: índice serializado de bm25s sobre src/index/tokenizar.py;
- metadata.jsonl: copia de fragmentos.jsonl (fila i ↔ vector i);
- config.json: encoder, dimensión, prefijos, versiones y el sha256 de
  fragmentos.jsonl con que se construyó cada parte (cargar.py lo verifica).

    python -m src.index.construir                    # denso + BM25
    python -m src.index.construir --partes bm25      # solo BM25 (segundos)
    python -m src.index.construir --reusar           # denso: solo codifica los fragmentos nuevos

--reusar toma de embeddings.npy el vector de cada fragmento cuyo texto ya estaba en
metadata.jsonl (mismo encoder, mismos prefijos y mismo max_seq_length) y codifica el
resto; con 1,5 M de fragmentos evita ~65 min de GPU al agregar unos pocos documentos.
Los vectores reutilizados son idénticos; los nuevos pueden diferir de una
reconstrucción completa en el redondeo de float16 (otro lote).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from src.common import io, rutas
from src.common.config import Config, load_config
from src.index import tokenizar

CONFIG_INDEX = rutas.INDEX / "config.json"
EMBEDDINGS = rutas.INDEX / "embeddings.npy"
BM25_DIR = rutas.INDEX / "bm25"
METADATA = rutas.INDEX / "metadata.jsonl"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for bloque in iter(lambda: fh.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def prefijos(encoder: str) -> dict[str, str]:
    """Los E5 exigen "query: " / "passage: " (enunciado, anexo B.2); bge-m3 no usa prefijos."""
    if "e5" in encoder.lower():
        return {"query": "query: ", "passage": "passage: "}
    return {"query": "", "passage": ""}


def cargar_fragmentos() -> list[dict[str, Any]]:
    frags = io.read_jsonl(rutas.FRAGMENTOS)
    for i, f in enumerate(frags):
        if f["chunk_id"] != i:
            raise ValueError(f"fragmentos.jsonl desalineado: fila {i} tiene chunk_id {f['chunk_id']}")
    return frags


def construir_bm25(textos: list[str], cfg: Config) -> dict[str, Any]:
    import bm25s

    params = cfg["retrieval"]["bm25"]
    t0 = time.perf_counter()
    tokens = [tokenizar.tokenizar(t) for t in textos]
    modelo = bm25s.BM25(method=params.get("method", "lucene"),
                        k1=params.get("k1", 1.5), b=params.get("b", 0.75))
    modelo.index(tokens, show_progress=False)
    if BM25_DIR.exists():
        shutil.rmtree(BM25_DIR)
    modelo.save(str(BM25_DIR))
    print(f"bm25: {len(tokens)} documentos, {len(modelo.vocab_dict)} términos, "
          f"{time.perf_counter() - t0:.0f} s")
    return {"method": modelo.method, "k1": modelo.k1, "b": modelo.b,
            "tokenizador_version": tokenizar.VERSION, "bm25s": bm25s.__version__}


def _vectores_previos(cfg: Config, textos: list[str]) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    """(filas nuevas, filas viejas, embeddings viejos) de los textos ya codificados con el
    mismo encoder; None si no hay un índice denso previo compatible."""
    if not (EMBEDDINGS.exists() and METADATA.exists() and CONFIG_INDEX.exists()):
        return None
    denso = io.read_json(CONFIG_INDEX).get("denso") or {}
    encoder = cfg["retrieval"]["encoder"]
    if (denso.get("encoder"), denso.get("max_seq_length"), denso.get("prefijos")) != (
            encoder, cfg["retrieval"].get("max_seq_length", 1024), prefijos(encoder)):
        print("--reusar: el índice previo usa otro encoder o configuración; se codifica todo")
        return None
    viejos = np.load(EMBEDDINGS)
    fila_de: dict[bytes, int] = {}
    with METADATA.open(encoding="utf-8") as fh:
        for i, linea in enumerate(fh):
            texto = json.loads(linea)["texto"]
            fila_de.setdefault(hashlib.blake2b(texto.encode("utf-8"), digest_size=16).digest(), i)
    if len(fila_de) and max(fila_de.values()) >= viejos.shape[0]:
        print("--reusar: metadata.jsonl y embeddings.npy no están alineados; se codifica todo")
        return None
    pares = [(i, fila_de.get(hashlib.blake2b(t.encode("utf-8"), digest_size=16).digest()))
             for i, t in enumerate(textos)]
    nuevas = np.array([i for i, j in pares if j is not None], dtype=np.int64)
    previas = np.array([j for _, j in pares if j is not None], dtype=np.int64)
    return nuevas, previas, viejos


def construir_denso(textos: list[str], cfg: Config, batch_size: int, reusar: bool = False) -> dict[str, Any]:
    import sentence_transformers
    import torch
    from sentence_transformers import SentenceTransformer

    encoder = cfg["retrieval"]["encoder"]
    max_len = cfg["retrieval"].get("max_seq_length", 1024)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if device == "cuda" else torch.float32
    torch.manual_seed(cfg["seed"])
    modelo = SentenceTransformer(encoder, device=device, model_kwargs={"torch_dtype": dtype})
    modelo.max_seq_length = max_len
    pre = prefijos(encoder)["passage"]

    t0 = time.perf_counter()
    previo = _vectores_previos(cfg, textos) if reusar else None
    if previo is None:
        emb = modelo.encode([pre + t for t in textos], batch_size=batch_size,
                            normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=True)
        reuso = {}
    else:
        nuevas, previas, viejos = previo
        emb = np.zeros((len(textos), viejos.shape[1]), dtype=np.float16)
        emb[nuevas] = viejos[previas]
        faltan = np.setdiff1d(np.arange(len(textos)), nuevas)
        if len(faltan):
            emb[faltan] = modelo.encode([pre + textos[i] for i in faltan], batch_size=batch_size,
                                        normalize_embeddings=True, convert_to_numpy=True,
                                        show_progress_bar=True).astype(np.float16)
        reuso = {"reutilizados": int(len(nuevas)), "codificados": int(len(faltan))}
        print(f"--reusar: {len(nuevas)} vectores reutilizados, {len(faltan)} codificados")
    np.save(EMBEDDINGS, emb.astype(np.float16))
    print(f"denso: {emb.shape[0]} × {emb.shape[1]} en {device}, {time.perf_counter() - t0:.0f} s")
    return {**reuso, "encoder": encoder, "dim": int(emb.shape[1]), "max_seq_length": max_len,
            "prefijos": prefijos(encoder), "device": device, "dtype_modelo": str(dtype).split(".")[-1],
            "dtype_embeddings": "float16", "normalizado": True,
            "torch": torch.__version__, "sentence_transformers": sentence_transformers.__version__}


def construir(cfg: Config, partes: list[str], batch_size: int = 16, reusar: bool = False) -> dict[str, Any]:
    rutas.INDEX.mkdir(parents=True, exist_ok=True)
    frags = cargar_fragmentos()
    huella = sha256(rutas.FRAGMENTOS)
    textos = [f["texto"] for f in frags]

    previo = io.read_json(CONFIG_INDEX) if CONFIG_INDEX.exists() else {}
    config = {k: v for k, v in previo.items() if k in ("denso", "bm25")}
    if "bm25" in partes:
        config["bm25"] = {**construir_bm25(textos, cfg), "sha256_fragmentos": huella}
    if "denso" in partes:
        config["denso"] = {**construir_denso(textos, cfg, batch_size, reusar), "sha256_fragmentos": huella}

    shutil.copyfile(rutas.FRAGMENTOS, METADATA)
    config.update({"n_fragmentos": len(frags), "sha256_fragmentos": huella,
                   "fecha": datetime.now().isoformat(timespec="seconds")})
    io.write_json(config, CONFIG_INDEX)
    for parte in ("denso", "bm25"):
        if parte in config and config[parte]["sha256_fragmentos"] != huella:
            print(f"AVISO: la parte '{parte}' se construyó con otro fragmentos.jsonl; reconstruirla")
    return config


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="configs/base.yaml")
    parser.add_argument("--partes", nargs="+", choices=["denso", "bm25"], default=["denso", "bm25"])
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--reusar", action="store_true",
                        help="reutiliza los vectores de los fragmentos cuyo texto ya está en el índice")
    args = parser.parse_args()
    construir(load_config(args.config), args.partes, args.batch_size, args.reusar)


if __name__ == "__main__":
    main()
