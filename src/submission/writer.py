"""Escritura de la corrida: submission.jsonl (esquema oficial) y traces.jsonl.

La corrida es reanudable: cada ítem se agrega a ambos archivos al terminarlo
(con flush + fsync). Al reanudar, `leer_hechos` descarta una línea cortada por
una caída y deja solo los ids presentes en los dos archivos. Al final,
`finalizar` reescribe ambos ordenados por id.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable

from src.common.types import Answer, Trace

SUBMISSION = "submission.jsonl"
TRACES = "traces.jsonl"


def _linea(obj: dict) -> str:
    return json.dumps(obj, ensure_ascii=False, allow_nan=False) + "\n"


def write_submissions(answers: Iterable[Answer], path: Path) -> None:
    """Una línea por Answer.to_submission(), ordenadas por id."""
    filas = sorted((a.to_submission() for a in answers), key=lambda d: d["id"])
    _escribir(filas, path)


def write_traces(traces: Iterable[Trace], path: Path) -> None:
    _escribir(sorted((t.to_json() for t in traces), key=lambda d: d["question_id"]), path)


def _escribir(filas: list[dict], path: Path) -> None:
    tmp = Path(path).with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as fh:
        for f in filas:
            fh.write(_linea(f))
    os.replace(tmp, path)


def _leer_tolerante(path: Path) -> list[dict]:
    """Líneas JSON válidas; una línea final cortada (caída a mitad de escritura) se ignora."""
    if not path.exists():
        return []
    filas = []
    with path.open(encoding="utf-8") as fh:
        for linea in fh:
            if not linea.strip():
                continue
            try:
                filas.append(json.loads(linea))
            except json.JSONDecodeError:
                break
    return filas


def leer_hechos(out: Path) -> tuple[dict[int, dict], dict[int, dict]]:
    """(submission por id, trace por id) de lo ya terminado; reescribe ambos archivos consistentes."""
    subs = {d["id"]: d for d in _leer_tolerante(out / SUBMISSION)}
    traces = {d["question_id"]: d for d in _leer_tolerante(out / TRACES)}
    hechos = subs.keys() & traces.keys()
    subs = {i: subs[i] for i in sorted(hechos)}
    traces = {i: traces[i] for i in sorted(hechos)}
    _escribir(list(subs.values()), out / SUBMISSION)
    _escribir(list(traces.values()), out / TRACES)
    return subs, traces


def agregar(out: Path, answer: Answer, trace: Trace) -> None:
    """Agrega un ítem terminado a submission.jsonl y traces.jsonl (primero el trace)."""
    for nombre, obj in ((TRACES, trace.to_json()), (SUBMISSION, answer.to_submission())):
        with (out / nombre).open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(_linea(obj))
            fh.flush()
            os.fsync(fh.fileno())


def finalizar(out: Path) -> tuple[list[dict], list[dict]]:
    """Reescribe submission.jsonl y traces.jsonl ordenados por id; devuelve las filas."""
    subs, traces = leer_hechos(out)
    return list(subs.values()), list(traces.values())
