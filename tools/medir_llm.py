"""Mide el decoder en Ollama con prompts reales (10 pasajes del pipeline de recuperación).

Por pregunta llama dos veces con el contexto por defecto de Ollama y dos veces con
--num-ctx. Si con el defecto prompt_tokens sale menor, Ollama estaba recortando
el prompt (y con él la pregunta). Las dos llamadas iguales miden el determinismo.

    python tools/medir_llm.py                      # ids 253 58 589 674, qwen3:8b, num_ctx 16384
    python tools/medir_llm.py --solo-prompt        # sin Ollama: solo tamaño de los prompts
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.common import io, rutas  # noqa: E402
from src.common.config import load_config  # noqa: E402
from src.common.types import Question, Trace  # noqa: E402
from src.pipelines.registry import build_pipeline  # noqa: E402


def prompt_de(q: Question, pasajes) -> str:
    evidencia = "\n\n".join(f"[{i}] {p.texto}" for i, p in enumerate(pasajes, 1))
    opciones = "\n".join(f"{k}. {v}" for k, v in sorted((q.opciones or {}).items()))
    return ('Responde con un JSON {"respuesta": "..."} de 3 a 5 oraciones usando solo la evidencia.\n\n'
            f"# Pregunta\n{q.pregunta}\n{opciones}\n\n# Evidencia\n{evidencia}")


def llamar(url: str, modelo: str, prompt: str, num_ctx: int | None) -> dict:
    opciones = {"temperature": 0, "seed": 42, "num_predict": 400}
    if num_ctx:
        opciones["num_ctx"] = num_ctx
    r = requests.post(f"{url}/api/chat", timeout=300, json={
        "model": modelo, "stream": False, "think": False, "format": "json",
        "messages": [{"role": "user", "content": prompt}], "options": opciones})
    r.raise_for_status()
    return r.json()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ids", type=int, nargs="+", default=[253, 58, 589, 674])
    ap.add_argument("--modelo", default="qwen3:8b")
    ap.add_argument("--num-ctx", type=int, default=16384)
    ap.add_argument("--url", default="http://localhost:11434")
    ap.add_argument("--solo-prompt", action="store_true")
    args = ap.parse_args()

    pipe = build_pipeline(load_config("configs/baseline.yaml"), generador=False)
    filas = {f["id"]: f for f in io.read_jsonl(rutas.DATA / "sample_50.jsonl")}
    print("id    ctx      prompt_tok  gen_tok  seg   prompt_tok/s  gen_tok/s  idéntico")
    for qid in args.ids:
        q = Question.from_dict(filas[qid])
        pasajes = pipe.retrieve(q, pipe.stages.planner.plan(q), Trace(question_id=qid))
        prompt = prompt_de(q, pasajes)
        if args.solo_prompt:
            print(f"{qid:<5} {len(pasajes)} pasajes, {len(prompt)} caracteres (~{len(prompt) // 3} tokens)")
            continue
        for ctx in (None, args.num_ctx):
            a, b = (llamar(args.url, args.modelo, prompt, ctx) for _ in range(2))
            seg = a["total_duration"] / 1e9
            ptps = a["prompt_eval_count"] / max(a.get("prompt_eval_duration", 1) / 1e9, 1e-9)
            gtps = a["eval_count"] / max(a["eval_duration"] / 1e9, 1e-9)
            igual = a["message"]["content"] == b["message"]["content"]
            print(f"{qid:<5} {str(ctx or 'defecto'):<8} {a['prompt_eval_count']:>10}  {a['eval_count']:>7}  "
                  f"{seg:4.1f}  {ptps:12.0f}  {gtps:9.1f}  {'sí' if igual else 'NO'}")


if __name__ == "__main__":
    main()