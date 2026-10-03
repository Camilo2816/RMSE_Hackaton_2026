"""Benchmark de encoders sobre el corpus congelado, sin tocar corpus/index/.

Para cada encoder: embebe los 66 mil fragmentos de corpus/index/metadata.jsonl
(caché en --cache, fuera del repo), sustituye SOLO el recuperador denso del
pipeline baseline en memoria (BM25, lookup y reranker quedan los de la entrega)
y mide sobre los 41 ítems calificables de sample_50:

- denso solo: body-hit@10, recall de cuerpos@10 y presencia del fragmento
  propio de la norma de referencia en el top-50 (calidad del encoder aislada);
- pipeline: eval/retrieval_ceiling.ceiling con ese denso (lo que vería el LLM).

    python eval/benchmark_encoders.py --cache C:/Temp/enc --out eval/runs/benchmark_encoders.json
    python eval/benchmark_encoders.py --solo e5-large jina-v3
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.common import io, rutas  # noqa: E402
from src.common.config import load_config  # noqa: E402
from src.common.types import Passage, Question  # noqa: E402
from src.retrieval.fusion import ordenar  # noqa: E402
from src.verification.citations import bodies, extract, respaldadas  # noqa: E402

# consulta/pasaje: prefijo de texto (E5) o prompt_name / task de sentence-transformers.
ENCODERS: dict[str, dict] = {
    "bge-m3": {"modelo": "BAAI/bge-m3", "max_len": 1024},
    "e5-large": {"modelo": "intfloat/multilingual-e5-large", "max_len": 512,
                 "prefijo_q": "query: ", "prefijo_p": "passage: "},
    "jina-v3": {"modelo": "jinaai/jina-embeddings-v3", "max_len": 1024, "remoto": True,
                "kw_q": {"task": "retrieval.query", "prompt_name": "retrieval.query"},
                "kw_p": {"task": "retrieval.passage"}},
    "qwen3-emb-4b": {"modelo": "Qwen/Qwen3-Embedding-4B", "max_len": 1024, "lote": 8,
                     "kw_q": {"prompt_name": "query"}},
    "arctic-l-v2": {"modelo": "Snowflake/snowflake-arctic-embed-l-v2.0", "max_len": 1024,
                    "kw_q": {"prompt_name": "query"}},
}


def cargar_modelo(spec: dict):
    import torch
    from sentence_transformers import SentenceTransformer

    if spec.get("remoto"):
        # El código remoto de jina-v3 es anterior a transformers 5, que espera este
        # atributo en todo PreTrainedModel; sin él la carga falla (AttributeError).
        from transformers import PreTrainedModel

        if not hasattr(PreTrainedModel, "all_tied_weights_keys"):
            PreTrainedModel.all_tied_weights_keys = {}
    modelo = SentenceTransformer(spec["modelo"], device="cuda", trust_remote_code=spec.get("remoto", False),
                                 model_kwargs={"torch_dtype": torch.float16})
    modelo.max_seq_length = spec["max_len"]
    return modelo


def embeber_corpus(nombre: str, spec: dict, textos: list[str], cache: Path) -> tuple[np.ndarray, float]:
    """Embeddings normalizados en float16 (caché por encoder); bge-m3 reutiliza los del índice."""
    if nombre == "bge-m3":
        return np.load(rutas.INDEX / "embeddings.npy").astype(np.float32), 0.0
    destino = cache / f"{nombre}.npy"
    if destino.exists():
        meta = json.loads((cache / f"{nombre}.json").read_text(encoding="utf-8"))
        return np.load(destino).astype(np.float32), meta["segundos"]
    modelo = cargar_modelo(spec)
    t0 = time.perf_counter()
    emb = modelo.encode([spec.get("prefijo_p", "") + t for t in textos], batch_size=spec.get("lote", 16),
                        normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=True,
                        **spec.get("kw_p", {}))
    segundos = time.perf_counter() - t0
    np.save(destino, emb.astype(np.float16))
    (cache / f"{nombre}.json").write_text(json.dumps({"modelo": spec["modelo"], "segundos": segundos,
                                                       "dim": int(emb.shape[1])}), encoding="utf-8")
    del modelo
    return emb.astype(np.float32), segundos


class DensoBench:
    """Misma interfaz y búsqueda exacta que DenseRetriever, con otro encoder y otra matriz."""

    def __init__(self, indice, emb: np.ndarray, spec: dict) -> None:
        self.indice, self.emb, self.spec = indice, emb, spec
        self.modelo = cargar_modelo(spec)

    def search(self, query: str, k: int) -> list[Passage]:
        vec = self.modelo.encode([self.spec.get("prefijo_q", "") + query], batch_size=1, normalize_embeddings=True,
                                 convert_to_numpy=True, show_progress_bar=False, **self.spec.get("kw_q", {}))
        scores = self.emb @ vec[0].astype(np.float32)
        k = min(k, len(scores))
        cand = np.argpartition(-scores, min(k + 20, len(scores) - 1))[: k + 20]
        return ordenar([self.indice.pasaje(int(i), float(scores[i]), query) for i in cand])[:k]


def denso_solo(denso: DensoBench) -> dict:
    n = hit10 = ref = ref10 = propio50 = 0
    t = []
    for f in io.read_jsonl(rutas.DATA / "sample_50.jsonl"):
        cuerpos = bodies(extract(f.get("legal_basis") or ""))
        if not cuerpos:
            continue
        q = Question.from_dict(f)
        t0 = time.perf_counter()
        top = denso.search(q.texto_busqueda(), 50)
        t.append(time.perf_counter() - t0)
        sop = bodies(respaldadas(top[:10]))
        n += 1
        hit10 += bool(cuerpos & sop)
        ref += len(cuerpos)
        ref10 += len(cuerpos & sop)
        propio50 += bool(cuerpos & bodies(extract(" ; ".join(p.norma for p in top))))
    return {"n": n, "body_hit@10": round(hit10 / n, 4), "recall@10": round(ref10 / ref, 4),
            "propio@50": round(propio50 / n, 4), "consulta_p50_s": round(float(np.median(t)), 3)}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cache", required=True, type=Path, help="carpeta para los embeddings (fuera del repo)")
    ap.add_argument("--solo", nargs="*", default=list(ENCODERS))
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    args.cache.mkdir(parents=True, exist_ok=True)

    from eval.retrieval_ceiling import ceiling
    from src.index.cargar import cargar
    from src.pipelines.registry import build_pipeline

    cfg = load_config("configs/baseline.yaml")
    pipe = build_pipeline(cfg, generador=False)
    indice = cargar()
    textos = [f["texto"] for f in indice.metadata]
    resultados = json.loads(args.out.read_text(encoding="utf-8")) if args.out and args.out.exists() else {}
    for nombre in args.solo:
        spec = ENCODERS[nombre]
        emb, seg = embeber_corpus(nombre, spec, textos, args.cache)
        denso = DensoBench(indice, emb, spec)
        pipe.stages.retriever.dense = denso
        r = ceiling("configs/baseline.yaml", pipe=pipe)
        resultados[nombre] = {"modelo": spec["modelo"], "dim": int(emb.shape[1]), "indexado_s": round(seg),
                              "denso_solo": denso_solo(denso), "pipeline": r["resumen"],
                              "pipeline_fallos": r["fallos"], "pipeline_p95_s": r["latencia"]["p95"]}
        print(nombre, json.dumps(resultados[nombre], ensure_ascii=False), flush=True)
        if args.out:
            io.write_json(resultados, args.out)
        del denso
        import torch
        torch.cuda.empty_cache()


if __name__ == "__main__":
    main()
