"""Corre un pipeline sobre un archivo de preguntas propio (fuera de data/) y lo califica.

Para el benchmark de decoders con preguntas adicionales a sample_50 (p. ej.
data_50.jsonl). Las preguntas pasan por Question.from_dict: la respuesta y el
legal_basis nunca llegan al sistema. Se califica con las funciones del
evaluador oficial (scripts/evaluate.py, sin modificar): cerradas y citas.
Reanudable con el mismo --out.

    python eval/benchmark_decoders/correr_extra.py --config eval/benchmark_decoders/qwen3-8b.yaml \
        --preguntas data_50.jsonl --out eval/runs/extra_qwen3-8b
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.common import io, rutas  # noqa: E402
from src.common.config import load_config  # noqa: E402
from src.common.types import Question  # noqa: E402
from src.submission import writer  # noqa: E402

sys.path.insert(0, str(rutas.SCRIPTS))
import evaluate  # noqa: E402  scripts/evaluate.py, sin modificar


def calificar(filas: list[dict], subs: dict[int, dict]) -> dict:
    key = {r["id"]: {"respuesta_correcta": r.get("respuesta_correcta"), "respuesta_esperada": r.get("respuesta_esperada"),
                     "legal_basis": r.get("legal_basis"), "pregunta": r["pregunta"], "formato": r["formato"]}
           for r in filas}
    cerradas = [i for i, k in key.items() if k["formato"] == "multiple_choice"]
    return {"cerradas": evaluate.score_closed(subs, key, cerradas), "citas": evaluate.score_citations(subs, key)}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--preguntas", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    filas = io.read_jsonl(args.preguntas)
    preguntas = sorted((Question.from_dict(f) for f in filas), key=lambda q: q.id)
    args.out.mkdir(parents=True, exist_ok=True)
    hechos, _ = writer.leer_hechos(args.out)
    pendientes = [q for q in preguntas if q.id not in hechos]
    if pendientes:
        from src.pipelines.registry import build_pipeline

        pipe = build_pipeline(load_config(args.config))
        for n, q in enumerate(pendientes, start=len(hechos) + 1):
            t0 = time.perf_counter()
            answer, trace = pipe.run(q)
            answer.latencia_ms = int(round((time.perf_counter() - t0) * 1000))
            writer.agregar(args.out, answer, trace)
            print(f"[{n:>3}/{len(preguntas)}] id {q.id} {answer.latencia_ms / 1000:.1f} s", flush=True)
    lista, _ = writer.finalizar(args.out)
    subs = {s["id"]: s for s in lista}
    reporte = {"config": args.config, "preguntas": str(args.preguntas), **calificar(filas, subs)}
    io.write_json(reporte, args.out / "report.json")
    print(json.dumps(reporte, ensure_ascii=False))


if __name__ == "__main__":
    main()
