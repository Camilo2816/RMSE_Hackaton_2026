"""Corre un pipeline sobre un split y escribe la corrida.

Salida en --out (por defecto eval/runs/<AAAA-MM-DD_HHMM>_<pipeline>/):
submission.jsonl (ordenado por id, con latencia_ms), traces.jsonl, config.yaml
(la config fusionada), validacion.json y, en corridas completas de sample,
report.json (scripts/evaluate.py sin --ragas, como subproceso).

Reanudable: cada ítem se guarda al terminarlo. Si la corrida se cae, se relanza
con el mismo --out (o con --reanudar, que toma la última corrida sin terminar
del mismo pipeline y split) y sigue donde quedó. Un ítem que lanza una
excepción inesperada se anota en errores.jsonl y no se escribe: al reanudar se
vuelve a intentar.

Uso:
    python -m src.main --config configs/agentic.yaml --split sample          # el de la entrega (configs/baseline.yaml: comparación)
    python -m src.main --config configs/agentic.yaml --split sample --reanudar
    python -m src.main --config configs/agentic.yaml --split sample --ids 24 58   # verificación en vivo
"""
from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

from src.common import io, rutas
from src.common.config import Config, load_config
from src.common.types import Question
from src.submission import writer
from src.submission.validate import SPLITS, validate

# Composición del test (enunciado, anexo: 1042 del banco − 50 de la muestra).
TEST_POR_FORMATO = {"multiple_choice": 290, "semi_open": 652, "open_ended": 50}
PRESUPUESTO_S = 22.0


def cargar_preguntas(split: str, ids: Optional[list[int]]) -> list[Question]:
    """Solo los campos de entrada (Question.from_dict descarta respuestas y legal_basis)."""
    preguntas = [Question.from_dict(f) for f in io.read_jsonl(rutas.DATA / SPLITS[split])]
    if ids:
        por_id = {q.id: q for q in preguntas}
        faltan = [i for i in ids if i not in por_id]
        if faltan:
            sys.exit(f"ids que no están en el split {split}: {faltan}")
        preguntas = [por_id[i] for i in ids]
    return sorted(preguntas, key=lambda q: q.id)


def _normalizar_cfg(cfg: Config) -> Config:
    return json.loads(json.dumps(cfg))


def _corrida_sin_terminar(pipeline: str, split: str) -> Optional[Path]:
    candidatas = sorted(rutas.EVAL_RUNS.glob(f"*_{pipeline}"), reverse=True)
    for c in candidatas:
        meta = c / "corrida.json"
        if meta.exists():
            m = io.read_json(meta)
            if not m.get("terminada") and m.get("split") == split and not m.get("ids"):
                return c
    return None


def preparar_directorio(args, cfg: Config) -> Path:
    if args.out:
        out = Path(args.out)
    elif args.reanudar:
        out = _corrida_sin_terminar(cfg["pipeline"], args.split)
        if out is None:
            sys.exit(f"no hay corrida sin terminar de '{cfg['pipeline']}' en {args.split}")
    else:
        out = rutas.EVAL_RUNS / f"{datetime.now():%Y-%m-%d_%H%M}_{cfg['pipeline']}"
    out.mkdir(parents=True, exist_ok=True)

    config_yaml = out / "config.yaml"
    meta = {"config": args.config, "split": args.split, "ids": args.ids or None}
    if config_yaml.exists():
        previa = yaml.safe_load(config_yaml.read_text(encoding="utf-8"))
        if previa != _normalizar_cfg(cfg):
            sys.exit(f"{out} ya tiene otra config: no se reanuda con una distinta (determinismo)")
        previa_meta = io.read_json(out / "corrida.json") if (out / "corrida.json").exists() else meta
        if (previa_meta.get("split"), previa_meta.get("ids")) != (meta["split"], meta["ids"]):
            sys.exit(f"{out} es de otro split o de otros ids: {previa_meta}")
    else:
        config_yaml.write_text(yaml.safe_dump(_normalizar_cfg(cfg), allow_unicode=True, sort_keys=False),
                               encoding="utf-8", newline="\n")
        meta["inicio"] = datetime.now().isoformat(timespec="seconds")
        meta["commit"] = _commit()
        io.write_json(meta, out / "corrida.json")
    return out


def _commit() -> Optional[str]:
    try:
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=rutas.RAIZ, capture_output=True, text=True)
        return r.stdout.strip() or None
    except OSError:
        return None


def _hms(seg: float) -> str:
    seg = int(round(seg))
    h, r = divmod(seg, 3600)
    m, s = divmod(r, 60)
    return f"{h} h {m:02d} min" if h else f"{m} min {s:02d} s"


def proyeccion_992(latencias: dict[str, list[float]]) -> Optional[float]:
    """Segundos para el test: media por formato × ítems del test de ese formato."""
    todas = [x for v in latencias.values() for x in v]
    if not todas:
        return None
    media = statistics.fmean(todas)
    return sum(n * (statistics.fmean(latencias[f]) if latencias.get(f) else media)
               for f, n in TEST_POR_FORMATO.items())


def evaluar(out: Path, split: str) -> Optional[dict]:
    """scripts/evaluate.py sin --ragas (no usa la llave de OpenRouter) → report.json."""
    report = out / "report.json"
    r = subprocess.run([sys.executable, str(rutas.SCRIPTS / "evaluate.py"), "--submission", str(out / writer.SUBMISSION),
                        "--split", split, "--out", str(report)],
                       cwd=rutas.RAIZ, capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0 or not report.exists():
        print(f"evaluate.py falló ({r.returncode}):\n{r.stderr[-2000:]}")
        return None
    return io.read_json(report)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="configs/agentic.yaml")
    parser.add_argument("--split", choices=list(SPLITS), default="sample")
    parser.add_argument("--out", default=None, help="directorio de la corrida (si existe, se reanuda)")
    parser.add_argument("--reanudar", action="store_true", help="sigue la última corrida sin terminar")
    parser.add_argument("--ids", type=int, nargs="*", help="solo estos ids (verificación en vivo)")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # consola de Windows (cp1252)

    cfg = load_config(args.config)
    preguntas = cargar_preguntas(args.split, args.ids)
    out = preparar_directorio(args, cfg)
    hechos, _ = writer.leer_hechos(out)
    pendientes = [q for q in preguntas if q.id not in hechos]
    print(f"corrida: {out}")
    print(f"{cfg['pipeline']} · {args.split} · {len(preguntas)} preguntas · {len(hechos)} ya hechas · "
          f"{len(pendientes)} pendientes", flush=True)

    formato_de = {q.id: q.formato for q in preguntas}
    latencias: dict[str, list[float]] = {}
    for qid, s in hechos.items():
        if s.get("latencia_ms") is not None and qid in formato_de:
            latencias.setdefault(formato_de[qid], []).append(s["latencia_ms"] / 1000)

    if pendientes:
        from src.pipelines.registry import build_pipeline

        t0 = time.perf_counter()
        pipeline = build_pipeline(cfg)
        print(f"pipeline cargado en {time.perf_counter() - t0:.1f} s", flush=True)

    for n, q in enumerate(pendientes, start=len(hechos) + 1):
        t0 = time.perf_counter()
        try:
            answer, trace = pipeline.run(q)
        except Exception as exc:  # noqa: BLE001 - un ítem no tumba la corrida; se reintenta al reanudar
            with (out / "errores.jsonl").open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"id": q.id, "error": repr(exc), "traceback": traceback.format_exc()},
                                    ensure_ascii=False) + "\n")
            print(f"[{n:>4}/{len(preguntas)}] id {q.id}: ERROR {exc!r} (queda pendiente)", flush=True)
            continue
        dt = time.perf_counter() - t0
        answer.latencia_ms = int(round(dt * 1000))
        writer.agregar(out, answer, trace)
        latencias.setdefault(q.formato, []).append(dt)

        todas = [x for v in latencias.values() for x in v]
        restantes = len(preguntas) - n
        marcas = " ".join(m for m, c in (("[respaldo]", trace.fallback), ("[abstención]", answer.abstencion),
                                          ("[citas quitadas]", trace.dropped_citations)) if c)
        print(f"[{n:>4}/{len(preguntas)}] id {q.id:>5} {q.formato:<16} {dt:5.1f} s · media {statistics.fmean(todas):4.1f} s"
              f" · faltan ~{_hms(restantes * statistics.fmean(todas))} · 992 → {_hms(proyeccion_992(latencias))} {marcas}",
              flush=True)

    subs, _ = writer.finalizar(out)
    esperados = {q.id for q in preguntas}
    # La validación no puede tumbar el cierre: tras horas de generación, una excepción
    # aquí dejaba la corrida sin validacion.json, sin `terminada` y sin report.json.
    try:
        problemas = validate(out / writer.SUBMISSION, expected_ids=esperados)
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        problemas = [f"validación no ejecutada: {type(e).__name__}: {e}"]
    io.write_json({"errores": len(problemas), "detalle": problemas}, out / "validacion.json")
    if len(subs) == len(preguntas):
        meta = io.read_json(out / "corrida.json")
        meta.update(terminada=True, fin=datetime.now().isoformat(timespec="seconds"))
        io.write_json(meta, out / "corrida.json")
    print(f"\n{len(subs)}/{len(preguntas)} ítems escritos · validación: {len(problemas)} problemas")
    for p in problemas[:20]:
        print("  ", p)
    if (out / "errores.jsonl").exists() and len(subs) < len(preguntas):
        print(f"hay ítems con error: relance con --out {out} para reintentarlos")

    proy = proyeccion_992(latencias)
    if proy is not None:
        print(f"proyección a 992 preguntas: {_hms(proy)} ({proy / 992:.1f} s/pregunta; presupuesto {PRESUPUESTO_S:.0f} s)")

    if args.split == "sample" and not args.ids and len(subs) == len(preguntas):
        rep = evaluar(out, args.split)
        if rep:
            print(f"report.json: total {rep['total_automatico']['obtenidos']} / {rep['total_automatico']['posibles']} "
                  f"(cerradas {rep['cerradas']['puntos']}, citas {rep['citas']['puntos']}, "
                  f"abstención {rep['abstencion']['puntos']})")
    elif args.ids:
        print("corrida con --ids: sin report.json (el evaluador espera el split completo)")


if __name__ == "__main__":
    main()
