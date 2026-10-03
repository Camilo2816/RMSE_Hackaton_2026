"""Techo de recuperación, sin LLM.

% de preguntas de sample_50 cuya norma del legal_basis (citations.extract)
aparece en los 10 pasajes que entrega la etapa de recuperación del pipeline
(Pipeline.retrieve: lookup + híbrido + rerank + fusión, los mismos que vería el
LLM). Solo lee legal_basis para medir; nunca lo pasa al sistema.

Métricas:
- body-hit@k: el ítem tiene al menos un cuerpo de referencia respaldado por los
  k pasajes (igual que evaluate.citas_respaldadas). Es el techo de citación y
  de abstención.
- recall de cuerpos: cuerpos de referencia respaldados / cuerpos de referencia.
- article-hit@k: entre los ítems cuya referencia nombra artículos, alguno de esos
  artículos está en los pasajes. Se mide con los metadatos del pasaje (norma +
  articulo): en el texto, "ARTICULO 241" queda lejos de "Código Penal" (la ruta
  Libro > Título va en medio) y el extractor no los asocia. No afecta al
  evaluador, que compara por cuerpo; sí indica si el LLM tendrá el artículo a la vista.
Cada cuerpo perdido se clasifica: "falta en el corpus" o "no recuperado".

Uso:
    python eval/retrieval_ceiling.py --config configs/baseline.yaml
    python eval/retrieval_ceiling.py --config configs/baseline.yaml --set rerank.enabled=false lookup.enabled=false
"""
from __future__ import annotations

import argparse
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.common import io, rutas  # noqa: E402
from src.common.config import Config, load_config  # noqa: E402
from src.common.types import Question, Trace  # noqa: E402
from src.verification.citations import article_level, bodies, extract, respaldadas  # noqa: E402
from src.verification.abstention import mejor_score_rerank  # noqa: E402


def aplicar(cfg: Config, asignaciones: list[str]) -> Config:
    """Sobrescribe claves con notación de puntos: "rerank.enabled=false"."""
    for a in asignaciones:
        ruta, valor = a.split("=", 1)
        nodo = cfg
        *padres, hoja = ruta.split(".")
        for p in padres:
            nodo = nodo.setdefault(p, {})
        nodo[hoja] = yaml.safe_load(valor)
    return cfg


def _tasa(aciertos: int, total: int) -> float | None:
    return round(aciertos / total, 4) if total else None


def ceiling(config_path: str, split: str = "sample", k: int = 10, overrides: list[str] = (), pipe=None) -> dict:
    """{"global": float, "por_area": {...}, "por_formato": {...}, "fallos": [ids]} + detalle.

    pipe: un pipeline ya construido (p. ej. con otro recuperador denso, eval/benchmark_encoders.py).
    """
    if split != "sample":
        raise ValueError("solo sample_50 trae legal_basis para medir")
    from src.index.cargar import cargar
    from src.pipelines.registry import build_pipeline

    cfg = aplicar(load_config(config_path), list(overrides))
    pipe = pipe or build_pipeline(cfg, generador=False)
    normas = {f["doc_id"]: f["norma"] for f in cargar().metadata}
    cuerpos_corpus = set().union(*(bodies(extract(n)) for n in normas.values()))

    items: list[dict[str, Any]] = []
    for fila in io.read_jsonl(rutas.DATA / "sample_50.jsonl"):
        ref_cites = extract(fila.get("legal_basis") or "")
        ref = bodies(ref_cites)
        if not ref:
            continue  # sin cita extraíble: no mide recuperación
        q = Question.from_dict(fila)
        trace = Trace(question_id=q.id)
        t0 = time.perf_counter()
        pasajes = pipe.recuperar(q, trace)[:k]
        dt = time.perf_counter() - t0
        sop = respaldadas(pasajes)
        arts_vistos = {(*b, p.articulo.lower()) for p in pasajes if p.articulo
                       for b in bodies(extract(p.norma))}
        arts_ref = article_level(ref_cites)
        perdidos = ref - bodies(sop)
        items.append({
            "id": q.id, "area": fila.get("area"), "formato": q.formato,
            "complejidad": fila.get("complejidad"), "body_hit": bool(ref & bodies(sop)),
            "n_ref": len(ref), "n_ref_hit": len(ref & bodies(sop)),
            "article_hit": bool({(*c[:3], str(c[3]).lower()) for c in arts_ref} & arts_vistos) if arts_ref else None,
            "lookup_hits": len(trace.passages_by_query.get("lookup", [])),
            "docs_distintos": len({p.doc_id for p in pasajes}),
            "perdidos": [{"cuerpo": list(c), "motivo": "falta en el corpus" if c not in cuerpos_corpus
                          else "no recuperado"} for c in sorted(perdidos, key=str)],
            "segundos": round(dt, 3), "timings": {e: round(s, 3) for e, s in trace.timings.items()},
            "replaneo": bool(trace.replan_reasons), "subconsultas": list(dict.fromkeys(trace.subqueries)),
            "mejor_rerank": mejor_score_rerank(pasajes),
        })

    def agregado(grupo: list[dict[str, Any]]) -> dict[str, Any]:
        con_art = [i for i in grupo if i["article_hit"] is not None]
        return {"n": len(grupo), "body_hit": _tasa(sum(i["body_hit"] for i in grupo), len(grupo)),
                "recall_cuerpos": _tasa(sum(i["n_ref_hit"] for i in grupo), sum(i["n_ref"] for i in grupo)),
                "article_hit": _tasa(sum(i["article_hit"] for i in con_art), len(con_art)),
                "n_con_articulo": len(con_art), "replaneos": sum(i["replaneo"] for i in grupo),
                "docs_distintos": round(statistics.fmean(i["docs_distintos"] for i in grupo), 2)}

    por = defaultdict(lambda: defaultdict(list))
    for i in items:
        por["area"][i["area"]].append(i)
        por["formato"][i["formato"]].append(i)
    etapas = sorted({e for i in items for e in i["timings"]})
    seg = sorted(i["segundos"] for i in items)
    rerank_s = sorted(i["timings"].get("rerank", 0.0) for i in items)
    return {
        "config": config_path, "overrides": list(overrides), "k": k,
        "global": agregado(items)["body_hit"],
        "resumen": agregado(items),
        "por_area": {a: agregado(g) for a, g in sorted(por["area"].items())},
        "por_formato": {f: agregado(g) for f, g in sorted(por["formato"].items())},
        "latencia": {"p50": statistics.median(seg), "p95": seg[int(0.95 * (len(seg) - 1))], "max": seg[-1],
                     "rerank_p95": rerank_s[int(0.95 * (len(rerank_s) - 1))],
                     "por_etapa_p50": {e: statistics.median(i["timings"].get(e, 0.0) for i in items)
                                       for e in etapas}},
        "fallos": [i["id"] for i in items if not i["body_hit"]],
        "items": items,
    }


def reporte(r: dict[str, Any]) -> str:
    s = r["resumen"]
    lineas = [f"## Techo de recuperación — {r['config']} {' '.join(r['overrides'])}".rstrip(), "",
              f"body-hit@{r['k']}: **{s['body_hit']:.0%}** ({s['n']} ítems) · recall de cuerpos "
              f"{s['recall_cuerpos']:.0%} · article-hit {s['article_hit'] if s['article_hit'] is None else format(s['article_hit'], '.0%')}"
              f" ({s['n_con_articulo']} con artículo) · docs distintos/ítem {s['docs_distintos']:.2f}"
              f" · re-planeos {s['replaneos']}",
              f"latencia p50 {r['latencia']['p50']:.2f} s · p95 {r['latencia']['p95']:.2f} s · "
              f"rerank p95 {r['latencia']['rerank_p95']:.2f} s · por etapa "
              + ", ".join(f"{e} {v:.3f} s" for e, v in r["latencia"]["por_etapa_p50"].items()), "",
              "| Grupo | n | body-hit | recall cuerpos | article-hit |", "|---|---:|---:|---:|---:|"]
    for tipo in ("por_formato", "por_area"):
        for nombre, a in r[tipo].items():
            ah = "—" if a["article_hit"] is None else f"{a['article_hit']:.0%}"
            lineas.append(f"| {nombre} | {a['n']} | {a['body_hit']:.0%} | {a['recall_cuerpos']:.0%} | {ah} |")
    lineas += ["", "Cuerpos de referencia perdidos:"]
    for i in r["items"]:
        for p in i["perdidos"]:
            lineas.append(f"- {i['id']} ({i['area']}, {i['formato']}): {tuple(p['cuerpo'])} — {p['motivo']}"
                          + ("" if i["body_hit"] else "  ← ítem sin ningún cuerpo respaldado"))
    return "\n".join(lineas)


def main() -> None:
    # La consola de Windows (cp1252) no codifica todos los caracteres del reporte.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="configs/baseline.yaml")
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--set", nargs="*", default=[], dest="overrides", help="clave.anidada=valor")
    parser.add_argument("--out", help="guarda el resultado completo en JSON")
    args = parser.parse_args()
    r = ceiling(args.config, k=args.k, overrides=args.overrides)
    print(reporte(r))
    if args.out:
        io.write_json(r, Path(args.out))


if __name__ == "__main__":
    main()
