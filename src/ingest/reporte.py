"""Tablero del corpus: avance por ola y cobertura frente al banco.

Métricas (todas sin LLM, en segundos):
- Avance por ola: documentos pendientes, con URL, descargados, procesados.
- Cobertura ponderada del seed: Σ items_del_banco de los cuerpos procesados / Σ total.
  Aproxima qué fracción de las citas del banco completo puede respaldar el corpus.
- Techo de la muestra: cuerpos del legal_basis de data/sample_50.jsonl presentes en
  el corpus. Solo se lee el legal_basis (nunca entra al índice).
- Faltantes de mayor peso, para decidir la siguiente hora de trabajo.

    python -m src.ingest.reporte
"""
from __future__ import annotations

import json
from collections import Counter

from src.common import rutas
from src.ingest import fuentes
from src.ingest.resolver import cargar_lock


def _procesados() -> set[str]:
    return {p.stem for p in rutas.FRAGMENTOS_DIR.glob("*.jsonl")} if rutas.FRAGMENTOS_DIR.exists() else set()


def construir() -> dict:
    docs = fuentes.cargar()
    lock = cargar_lock()
    procesados = _procesados()
    descargados = {p.parent.name for p in rutas.RAW.glob("*/_descarga.json")}

    por_ola: dict[int, Counter] = {}
    for d in docs.values():
        c = por_ola.setdefault(d["ola"], Counter())
        c[d["estado"]] += 1
        if d["estado"] == "excluido":
            continue
        c["con_url"] += lock.get(d["doc_id"], {}).get("estado") == "ok"
        c["descargados"] += d["doc_id"] in descargados
        c["procesados"] += d["doc_id"] in procesados

    cuerpos_corpus = {tuple(docs[k]["canonico"]) for k in procesados if docs.get(k, {}).get("canonico")}
    for k in procesados:  # los alias también respaldan
        for alias in docs.get(k, {}).get("alias_citables") or []:
            cuerpos_corpus |= fuentes.canonico_de_encabezado(alias)
    total = sum(d.get("items_del_banco") or 0 for d in docs.values())
    cubierto = sum(d.get("items_del_banco") or 0 for d in docs.values()
                   if d.get("canonico") and tuple(d["canonico"]) in cuerpos_corpus)

    muestra: Counter = Counter()
    faltan_muestra = set()
    for linea in (rutas.DATA / "sample_50.jsonl").read_text(encoding="utf-8").splitlines():
        if not linea.strip():
            continue
        for c in fuentes.canonico_de(json.loads(linea).get("legal_basis") or ""):
            muestra["total"] += 1
            if c in cuerpos_corpus:
                muestra["en_corpus"] += 1
            else:
                faltan_muestra.add(c)

    faltantes = sorted((d for d in docs.values()
                        if d["doc_id"] not in procesados and d["estado"] != "excluido"),
                       key=lambda d: (-(d.get("items_del_banco") or 0), d["ola"], d["doc_id"]))
    return {
        "por_ola": {k: dict(v) for k, v in sorted(por_ola.items())},
        "cobertura_seed": (cubierto, total),
        "muestra": (muestra["en_corpus"], muestra["total"]),
        "faltan_muestra": sorted(faltan_muestra, key=lambda c: tuple(x or "" for x in c)),
        "faltantes_top": [(d["doc_id"], d.get("items_del_banco"), d["ola"],
                           lock.get(d["doc_id"], {}).get("estado", "sin_resolver"))
                          for d in faltantes[:15]],
    }


def main() -> None:
    r = construir()
    print("Avance por ola")
    print(f"  {'ola':>3} {'pend.':>6} {'verif.':>6} {'excl.':>6} {'URL':>5} {'desc.':>6} {'proc.':>6}")
    for ola, c in r["por_ola"].items():
        print(f"  {ola:>3} {c.get('pendiente', 0):>6} {c.get('por_verificar', 0):>6} "
              f"{c.get('excluido', 0):>6} {c.get('con_url', 0):>5} {c.get('descargados', 0):>6} "
              f"{c.get('procesados', 0):>6}")
    a, b = r["cobertura_seed"]
    print(f"\nCobertura ponderada del seed: {a}/{b} citas del banco ({a / b:.0%})")
    a, b = r["muestra"]
    print(f"Techo de la muestra: {a}/{b} citas (por cuerpo normativo) del legal_basis "
          f"respaldables con el corpus ({a / max(b, 1):.0%})")
    print("\nFaltantes de mayor peso (doc_id, ítems del banco, ola, URL):")
    for fila in r["faltantes_top"]:
        print("  ", *fila)


if __name__ == "__main__":
    main()
