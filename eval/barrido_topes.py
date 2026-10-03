"""Barrido de topes, candidatos y particiones sobre el techo de recuperación, sin LLM.

Responde, con el corpus de 1,54 M fragmentos (relatoría CC completa, ~97 % sentencias):
- ¿garantizar normas primarias entre los candidatos (cuotas.min_primarias, opción A)?
- ¿dejar en el denso solo ficha/síntesis/descriptores(/decisión) de la relatoría (opción B)?
- ¿sacar la relatoría del híbrido general y dejarla solo por número (opción C)? `--sonda N`
  mide además que las sentencias nombradas sigan llegando: N sentencias de la relatoría al
  azar (semilla fija) en plantillas de pregunta, sin LLM ni datos del test.
- ¿traer la relatoría por las normas que cita cuando la pregunta pide jurisprudencia sin
  nombrar sentencia (jurisprudencia.enabled)? `--sonda-juris N` pregunta por la
  jurisprudencia sobre N normas primarias y mide si entran sentencias de la relatoría que
  citan esa norma (con `cuerpos`, sin respuestas esperadas).
- ¿conviene un tope de sentencias más estricto (cuotas.sentencia 3 → 2 → 1)?
- ¿sirve mirar más allá de 10? El evaluador solo cuenta el respaldo en los 10 primeros
  pasajes (enunciado §6.1), así que entregar más no suma; la variante `k20` mide cuánto
  de lo perdido está en las posiciones 11-20, es decir, cuánto se ganaría ordenando mejor.

Carga índice, encoder y reranker una sola vez (eval/retrieval_ceiling.py los cargaría por
variante) y solo reconstruye lo que cambia: el híbrido (máscaras de denso y BM25), las
cuotas y el Pipeline. Solo lee legal_basis de sample_50 para medir, igual que
retrieval_ceiling.py. `actual` es la config por defecto (hoy A20 + B4).

    python eval/barrido_topes.py                       # todas las variantes
    python eval/barrido_topes.py --variantes actual C_A20 C_A0 --sonda 60
"""
from __future__ import annotations

import argparse
import dataclasses
import random
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from retrieval_ceiling import aplicar, ceiling  # noqa: E402
from src.common import io, rutas  # noqa: E402
from src.common.config import load_config  # noqa: E402
from src.common.types import Question, Trace  # noqa: E402
from src.index.cargar import cargar  # noqa: E402
from src.pipelines.registry import PIPELINES, build_stages  # noqa: E402
from src.retrieval.cuotas import Cuotas  # noqa: E402
from src.retrieval.bm25 import BM25Retriever  # noqa: E402
from src.retrieval.dense import DenseRetriever  # noqa: E402
from src.retrieval.hybrid import HybridRetriever  # noqa: E402
from src.retrieval.jurisprudencia import JurisprudenciaPorNormas  # noqa: E402
from src.verification.citations import bodies, extract, respaldadas  # noqa: E402

B4 = "retrieval.denso_relatoria_secciones=[ficha, sintesis, descriptores, decision]"
B3 = "retrieval.denso_relatoria_secciones=[ficha, sintesis, descriptores]"
SIN_B = "retrieval.denso_relatoria_secciones=null"
C = ["retrieval.denso_relatoria_secciones=[]", "retrieval.bm25_relatoria=false"]  # relatoría solo por lookup

# nombre: (overrides, k)
VARIANTES: dict[str, tuple[list[str], int]] = {
    "actual": ([], 10),
    "sin_AB": (["cuotas.min_primarias=0", SIN_B], 10),
    "C_A20": (C, 10),
    "C_A0": ([*C, "cuotas.min_primarias=0"], 10),
    "C_A0_J": ([*C, "cuotas.min_primarias=0", "jurisprudencia.enabled=true"], 10),
    "A10": (["cuotas.min_primarias=10", SIN_B], 10),
    "A15": (["cuotas.min_primarias=15", SIN_B], 10),
    "A20": (["cuotas.min_primarias=20", SIN_B], 10),
    "B4": (["cuotas.min_primarias=0", B4], 10),
    "B3": (["cuotas.min_primarias=0", B3], 10),
    "A15_B4": (["cuotas.min_primarias=15", B4], 10),
    "A15_B3": (["cuotas.min_primarias=15", B3], 10),
    "A20_B4": (["cuotas.min_primarias=20", B4], 10),
    "A20_sinB": (["cuotas.min_primarias=20", SIN_B], 10),
    "sin_cuotas": (["cuotas.enabled=false"], 10),
    "sent2": (["cuotas.sentencia=2"], 10),
    "sent1": (["cuotas.sentencia=1"], 10),
    "sent2_preg4": (["cuotas.sentencia=2", "cuotas.sentencia_si_pregunta=4"], 10),
    "cand60": (["rerank.candidates=60"], 10),
    "cand80": (["rerank.candidates=80"], 10),
    "sent2_cand60": (["cuotas.sentencia=2", "rerank.candidates=60"], 10),
    "k20": (["fusion.max_passages=20", "rerank.top_n=20"], 20),  # diagnóstico: no se puede entregar
}


PLANTILLAS = ("¿Cuál es el problema jurídico de la {s}?",
              "¿Qué decidió la Corte Constitucional en la {s}?",
              "¿Cuáles son los antecedentes fácticos de la {s}?")


def preguntas_sonda(n: int, docs_indice: set[str], semilla: int = 42) -> list[tuple[str, str, Question]]:
    """(doc_id, nombre citable, pregunta) de n sentencias de la relatoría cosechada (ninguna
    estaba en el corpus anterior), en plantillas genéricas. No usa sample ni test."""
    texto = (rutas.SOURCES / "relatoria_cc.yaml").read_text(encoding="utf-8")
    pares = re.findall(r'^  - doc_id: "([^"]+)"\r?\n    nombre_citable: "([^"]+)"', texto, re.M)
    pares = sorted((d, nom) for d, nom in pares if d in docs_indice)
    elegidas = random.Random(semilla).sample(pares, n)
    return [(d, nom, Question(id=900_000 + j, formato="semi_open", pregunta=PLANTILLAS[j % 3].format(s=nom)))
            for j, (d, nom) in enumerate(elegidas)]


def sonda(pipe, preguntas: list[tuple[str, str, Question]]) -> dict:
    """La sentencia nombrada llega a los 10 pasajes, va primera y queda respaldada su cita."""
    hit = primero = respaldo = 0
    perdidas = []
    for doc, nom, q in preguntas:
        pasajes = pipe.recuperar(q, Trace(question_id=q.id))[:10]
        en = doc in {p.doc_id for p in pasajes}
        hit += en
        primero += bool(pasajes) and pasajes[0].doc_id == doc
        respaldo += bodies(extract(nom)) <= bodies(respaldadas(pasajes))
        if not en:
            perdidas.append(nom)
    n = len(preguntas)
    return {"n": n, "hit10": round(hit / n, 3), "primero": round(primero / n, 3),
            "respaldada": round(respaldo / n, 3), "perdidas": perdidas}


def preguntas_juris(n: int, idx, j: JurisprudenciaPorNormas, semilla: int = 42) -> list[tuple[tuple, Question]]:
    """(cuerpo, pregunta) sobre la jurisprudencia de n normas primarias que la relatoría cita a
    menudo (entre 30 y 2.000 sentencias; sin la Constitución, que está en casi todas)."""
    df: dict[tuple, int] = {}
    for cs in j.cuerpos_doc.values():
        for c in cs:
            df[c] = df.get(c, 0) + 1
    nombre: dict[tuple, str] = {}
    for f in idx.metadata:
        if f.get("tipo") not in ("sentencia", "constitucion"):
            for c in bodies(extract(f["norma"])):
                nombre.setdefault(c, f["norma"])
    aptos = sorted(c for c, d in df.items() if 30 <= d <= 2000 and c in nombre and c[0] != "jurisprudencia")
    elegidos = random.Random(semilla).sample(aptos, min(n, len(aptos)))
    return [(c, Question(id=800_000 + k, formato="semi_open",
                         pregunta=f"¿Qué ha dicho la jurisprudencia de la Corte Constitucional sobre la {nombre[c]}?"))
            for k, c in enumerate(elegidos)]


def sonda_juris(pipe, preguntas: list[tuple[tuple, Question]], j: JurisprudenciaPorNormas) -> dict:
    """Sentencias de la relatoría en los 10 pasajes y cuántas citan la norma preguntada."""
    rel = citan = norma = 0
    for c, q in preguntas:
        pasajes = pipe.recuperar(q, Trace(question_id=q.id))[:10]
        docs = {p.doc_id for p in pasajes if p.doc_id in j.cuerpos_doc}
        rel += len(docs)
        citan += sum(c in j.cuerpos_doc[d] for d in docs)
        norma += any(c in bodies(extract(p.norma)) for p in pasajes)
    n = len(preguntas)
    return {"n": n, "relatoria_por_pregunta": round(rel / n, 2),
            "citan_la_norma": round(citan / rel, 3) if rel else None, "norma_en_los_10": round(norma / n, 3)}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="configs/baseline.yaml")
    ap.add_argument("--variantes", nargs="*", default=list(VARIANTES), choices=list(VARIANTES))
    ap.add_argument("--sonda", type=int, default=0, help="n sentencias de la relatoría nombradas en plantillas")
    ap.add_argument("--sonda-juris", type=int, default=0, help="n normas: jurisprudencia sobre ellas, sin nombrar sentencia")
    ap.add_argument("--out", default=str(rutas.EVAL_RUNS / f"{date.today().isoformat()}_barrido_topes.json"))
    args = ap.parse_args()

    stages = build_stages(load_config(args.config), generador=False)
    idx = cargar()
    preguntas = preguntas_sonda(args.sonda, {f["doc_id"] for f in idx.metadata}) if args.sonda else []
    j_sonda = preguntas_j = None
    if args.sonda_juris:
        cfg_j = aplicar(load_config(args.config), ["jurisprudencia.enabled=true"])
        j_sonda = JurisprudenciaPorNormas(idx, cfg_j, stages.lookup, None)
        preguntas_j = preguntas_juris(args.sonda_juris, idx, j_sonda)
    resultados = {}
    for nombre in args.variantes:
        overrides, k = VARIANTES[nombre]
        cfg = aplicar(load_config(args.config), overrides)
        cuotas = Cuotas(idx, cfg, stages.lookup) if cfg.get("cuotas", {}).get("enabled") else None
        r_ = cfg["retrieval"]
        retriever = HybridRetriever(DenseRetriever(idx, cfg), BM25Retriever(idx, cfg), r_["rrf_k"], r_["top_k_per_query"])
        juris = (JurisprudenciaPorNormas(idx, cfg, stages.lookup, cuotas)
                 if cfg.get("jurisprudencia", {}).get("enabled") else None)
        pipe = PIPELINES[cfg["pipeline"]](dataclasses.replace(stages, cuotas=cuotas, retriever=retriever,
                                                              jurisprudencia=juris), cfg)
        r = ceiling(args.config, k=k, overrides=overrides, pipe=pipe)
        resultados[nombre] = {k_: v for k_, v in r.items() if k_ != "items"} | {
            "perdidos": {i["id"]: i["perdidos"] for i in r["items"] if i["perdidos"]}}
        s = r["resumen"]
        print(f"{nombre:14s} body-hit@{k} {s['body_hit']:.3f} · recall {s['recall_cuerpos']:.3f} · "
              f"art {s['article_hit']:.3f} · docs/ítem {s['docs_distintos']:.1f} · "
              f"p95 {r['latencia']['p95']:.2f} s · fallos {r['fallos']}", flush=True)
        if preguntas_j:
            sj = resultados[nombre]["sonda_juris"] = sonda_juris(pipe, preguntas_j, j_sonda)
            print(f"{'':14s} sonda juris ({sj['n']} normas): sentencias de la relatoría por pregunta "
                  f"{sj['relatoria_por_pregunta']} · de ellas citan la norma {sj['citan_la_norma']} · "
                  f"norma en los 10 {sj['norma_en_los_10']}", flush=True)
        if preguntas:
            sd = resultados[nombre]["sonda"] = sonda(pipe, preguntas)
            print(f"{'':14s} sonda ({sd['n']} sentencias nombradas): en los 10 {sd['hit10']:.3f} · primera "
                  f"{sd['primero']:.3f} · cita respaldada {sd['respaldada']:.3f} · perdidas {sd['perdidas'][:5]}", flush=True)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    io.write_json(resultados, Path(args.out))
    print(f"resultado: {args.out}")


if __name__ == "__main__":
    main()
