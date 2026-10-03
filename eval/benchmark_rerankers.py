"""Benchmark de rerankers sobre el índice congelado (sin LLM generador).

Reemplaza solo el reranker del pipeline baseline en memoria (lookup, híbrido y
bge-m3 quedan los de la entrega) y mide con eval/retrieval_ceiling.ceiling sobre
los 41 ítems calificables de sample_50. Guarda por ítem el mejor score del
reranker, para recalibrar verification.replan_min_rerank_score si se adopta
otro (cada reranker tiene su escala).

Cross-encoders: sentence-transformers CrossEncoder. Rerankers LLM (Qwen3-Reranker,
bge-reranker-v2-gemma): probabilidad del token "yes" con el formato oficial de cada modelo.

    python eval/benchmark_rerankers.py --out eval/runs/benchmark_rerankers.json
    python eval/benchmark_rerankers.py --solo qwen3-rr-0.6b --out ...
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.common import io  # noqa: E402
from src.common.config import load_config  # noqa: E402
from src.common.types import Passage  # noqa: E402
from src.retrieval.fusion import ordenar  # noqa: E402

INSTRUCCION = ("Given a legal question about Colombian law, judge whether the document is a legal provision "
               "or ruling that answers it")

RERANKERS: dict[str, dict] = {
    "bge-v2-m3": {"tipo": "cross", "modelo": "BAAI/bge-reranker-v2-m3", "max_len": 512},
    "qwen3-rr-4b": {"tipo": "qwen3", "modelo": "Qwen/Qwen3-Reranker-4B", "max_len": 1024, "lote": 4},
    "qwen3-rr-0.6b": {"tipo": "qwen3", "modelo": "Qwen/Qwen3-Reranker-0.6B", "max_len": 1024, "lote": 8},
    "bge-v2-gemma": {"tipo": "gemma", "modelo": "BAAI/bge-reranker-v2-gemma", "max_len": 1024, "lote": 4},
    "jina-v2-multi": {"tipo": "cross", "modelo": "jinaai/jina-reranker-v2-base-multilingual", "max_len": 1024,
                      "remoto": True},
    "gte-multi": {"tipo": "cross", "modelo": "Alibaba-NLP/gte-multilingual-reranker-base", "max_len": 1024,
                  "remoto": True},
}


class Base:
    """Misma interfaz que src.retrieval.rerank.Reranker: entrada en orden canónico, salida ordenada."""

    def rerank(self, query: str, passages: list[Passage], top_n: int) -> list[Passage]:
        if not passages:
            return []
        canonico = sorted(passages, key=lambda p: p.clave)
        scores = self.puntuar(query, [p.texto for p in canonico])
        return ordenar([replace(p, score=float(s)) for p, s in zip(canonico, scores)])[:top_n]


class Cross(Base):
    def __init__(self, spec: dict) -> None:
        import torch
        from sentence_transformers import CrossEncoder

        self.modelo = CrossEncoder(spec["modelo"], device="cuda", max_length=spec["max_len"],
                                   trust_remote_code=spec.get("remoto", False),
                                   model_kwargs={"torch_dtype": torch.float16})

    def puntuar(self, query: str, textos: list[str]) -> list[float]:
        import torch

        return list(self.modelo.predict([(query, t) for t in textos], batch_size=8, show_progress_bar=False,
                                        activation_fn=torch.nn.Sigmoid(), convert_to_numpy=True))


class LLMSiNo(Base):
    """P("yes") en el último token; el formato lo arma cada subclase."""

    def __init__(self, spec: dict) -> None:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.tok = AutoTokenizer.from_pretrained(spec["modelo"], padding_side="left")
        self.modelo = AutoModelForCausalLM.from_pretrained(spec["modelo"], torch_dtype=torch.float16).cuda().eval()
        self.max_len, self.lote = spec["max_len"], spec.get("lote", 4)
        self.si = self.tok.convert_tokens_to_ids(self.token_si)
        self.no = self.tok.convert_tokens_to_ids(self.token_no) if self.token_no else None

    def puntuar(self, query: str, textos: list[str]) -> list[float]:
        import torch

        out: list[float] = []
        for i in range(0, len(textos), self.lote):
            ids = [self.armar(query, t) for t in textos[i:i + self.lote]]
            largo = max(map(len, ids))
            pad = self.tok.pad_token_id if self.tok.pad_token_id is not None else self.tok.eos_token_id
            entrada = torch.tensor([[pad] * (largo - len(x)) + x for x in ids], device="cuda")
            mascara = torch.tensor([[0] * (largo - len(x)) + [1] * len(x) for x in ids], device="cuda")
            with torch.no_grad():
                logits = self.modelo(input_ids=entrada, attention_mask=mascara).logits[:, -1, :].float()
            if self.no is not None:
                out += torch.softmax(logits[:, [self.no, self.si]], dim=-1)[:, 1].tolist()
            else:
                out += torch.sigmoid(logits[:, self.si]).tolist()
        return out

    def _recortar(self, prefijo: list[int], doc: list[int], sufijo: list[int]) -> list[int]:
        return prefijo + doc[: max(0, self.max_len - len(prefijo) - len(sufijo))] + sufijo


class Qwen3(LLMSiNo):
    """Formato oficial de Qwen3-Reranker (model card)."""

    token_si, token_no = "yes", "no"
    PRE = ("<|im_start|>system\nJudge whether the Document meets the requirements based on the Query and the "
           "Instruct provided. Note that the answer can only be \"yes\" or \"no\".<|im_end|>\n<|im_start|>user\n")
    SUF = "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"

    def armar(self, query: str, texto: str) -> list[int]:
        enc = lambda s: self.tok.encode(s, add_special_tokens=False)  # noqa: E731
        return self._recortar(enc(f"{self.PRE}<Instruct>: {INSTRUCCION}\n<Query>: {query}\n<Document>: "),
                              enc(texto), enc(self.SUF))


class Gemma(LLMSiNo):
    """Formato de FlagEmbedding FlagLLMReranker para bge-reranker-v2-gemma (logit de "Yes")."""

    token_si, token_no = "Yes", None
    PROMPT = ("Given a query A and a passage B, determine whether the passage contains an answer to the query "
              "by providing a prediction of either 'Yes' or 'No'.")

    def armar(self, query: str, texto: str) -> list[int]:
        enc = lambda s: self.tok.encode(s, add_special_tokens=False)  # noqa: E731
        return self._recortar([self.tok.bos_token_id] + enc(f"A: {query}\n") + enc("B: "),
                              enc(texto), enc(f"\n{self.PROMPT}"))


CLASES = {"cross": Cross, "qwen3": Qwen3, "gemma": Gemma}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--solo", nargs="*", default=["sin-reranker", *RERANKERS])
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    import torch

    from eval.retrieval_ceiling import ceiling
    from src.pipelines.registry import build_pipeline

    pipe = build_pipeline(load_config("configs/baseline.yaml"), generador=False)
    original = pipe.stages.reranker
    resultados = json.loads(args.out.read_text(encoding="utf-8")) if args.out and args.out.exists() else {}
    for nombre in args.solo:
        t0 = time.perf_counter()
        if nombre == "sin-reranker":
            pipe.stages.reranker = None
        elif nombre == "bge-v2-m3":
            pipe.stages.reranker = original
        else:
            try:
                pipe.stages.reranker = CLASES[RERANKERS[nombre]["tipo"]](RERANKERS[nombre])
            except Exception as exc:  # noqa: BLE001 - un modelo que no carga se reporta y se sigue
                resultados[nombre] = {"error": repr(exc)[:400]}
                print(nombre, "ERROR", repr(exc)[:400], flush=True)
                continue
        carga = time.perf_counter() - t0
        r = ceiling("configs/baseline.yaml", pipe=pipe)
        resultados[nombre] = {
            "modelo": RERANKERS.get(nombre, {}).get("modelo"), "carga_s": round(carga, 1),
            "pipeline": r["resumen"], "fallos": r["fallos"], "latencia": r["latencia"],
            "por_item": {i["id"]: {"n_ref_hit": i["n_ref_hit"], "body_hit": i["body_hit"],
                                   "article_hit": i["article_hit"], "formato": i["formato"],
                                   "mejor_rerank": i["mejor_rerank"]} for i in r["items"]},
        }
        print(nombre, json.dumps({k: resultados[nombre][k] for k in ("pipeline", "fallos")}, ensure_ascii=False),
              "rerank_p95", r["latencia"]["rerank_p95"], flush=True)
        if args.out:
            io.write_json(resultados, args.out)
        if nombre not in ("sin-reranker", "bge-v2-m3"):
            pipe.stages.reranker = None
            import gc

            gc.collect()
            torch.cuda.empty_cache()


if __name__ == "__main__":
    main()
