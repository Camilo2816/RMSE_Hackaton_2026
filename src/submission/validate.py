"""Validación de submission.jsonl: esquema oficial y reglas propias antes de entregar.

Además del JSON Schema (schema/submission.schema.json) revisa:
- ids enteros, únicos y exactamente los del split (o los pedidos con --ids);
- campos del formato no vacíos si no hay abstención, y pasajes no vacíos;
- respuesta_correcta y las llaves de descarte_opciones dentro de A–D;
- ≤ 10 pasajes, doc_id en corpus_manifest.json y texto literal igual a
  corpus/processed/<doc_id>.txt[inicio:fin];
- cero citas sin respaldo (answer_text oficial contra los 10 pasajes);
- sin NaN ni Infinity.

    python -m src.submission.validate eval/runs/<corrida>/submission.jsonl --split sample
"""
from __future__ import annotations

import argparse
import json
import sys
from functools import lru_cache
from pathlib import Path
from typing import Optional

from src.common import io, rutas
from src.common.types import CLAVES_FORMATO
from src.verification.citations import answer_text, bodies, extract

SCHEMA = rutas.RAIZ / "schema" / "submission.schema.json"
SPLITS = {"sample": "sample_50.jsonl", "test": "test_992.jsonl"}
LETRAS = {"A", "B", "C", "D"}
MAX_PASAJES = 10


def ids_del_split(split: str) -> set[int]:
    return {int(f["id"]) for f in io.read_jsonl(rutas.DATA / SPLITS[split])}


@lru_cache(maxsize=1)
def _doc_ids_manifest() -> frozenset[str]:
    return frozenset(d["doc_id"] for d in io.read_json(rutas.MANIFEST)["documentos"])


@lru_cache(maxsize=512)
def _texto_doc(doc_id: str) -> Optional[str]:
    ruta = rutas.PROCESSED / f"{doc_id}.txt"
    return ruta.read_text(encoding="utf-8") if ruta.exists() else None


def _rechazar_constante(nombre: str):
    raise ValueError(f"valor no JSON estándar: {nombre}")


def _leer(path: Path) -> tuple[list[dict], list[str]]:
    filas, problemas = [], []
    with Path(path).open(encoding="utf-8") as fh:
        for n, linea in enumerate(fh, start=1):
            if not linea.strip():
                continue
            try:
                filas.append(json.loads(linea, parse_constant=_rechazar_constante))
            except ValueError as exc:
                problemas.append(f"línea {n}: {exc}")
    return filas, problemas


def validar_item(s: dict, validador) -> list[str]:
    """Problemas de un ítem (sin contar ids del split)."""
    qid = s.get("id")
    p = [f"item {qid}: esquema: {e.message}" for e in validador.iter_errors(s)]
    formato = s.get("formato")
    if formato not in CLAVES_FORMATO:
        return p
    abst = bool(s.get("abstencion"))
    pasajes = s.get("pasajes_recuperados") or []
    if not abst:
        faltan = [k for k in CLAVES_FORMATO[formato] if s.get(k) in (None, "", [], {})]
        if faltan:
            p.append(f"item {qid}: campos vacíos sin abstención {faltan}")
        if not pasajes:
            p.append(f"item {qid}: sin pasajes_recuperados")
    if formato == "multiple_choice":
        if abst:
            p.append(f"item {qid}: abstención en multiple_choice")
        if s.get("respuesta_correcta") not in LETRAS:
            p.append(f"item {qid}: respuesta_correcta fuera de A–D: {s.get('respuesta_correcta')!r}")
        descarte = s.get("descarte_opciones") or {}
        fuera = set(descarte) - LETRAS
        if fuera:
            p.append(f"item {qid}: descarte_opciones con letras fuera de A–D {sorted(fuera)}")
        if s.get("respuesta_correcta") in descarte:
            p.append(f"item {qid}: descarte_opciones incluye la letra elegida")
    if len(pasajes) > MAX_PASAJES:
        p.append(f"item {qid}: {len(pasajes)} pasajes (máximo {MAX_PASAJES})")
    for j, ps in enumerate(pasajes[:MAX_PASAJES], start=1):
        doc = ps.get("doc_id")
        if doc not in _doc_ids_manifest():
            p.append(f"item {qid}: pasaje {j}: doc_id {doc!r} no está en corpus_manifest.json")
            continue
        texto_doc = _texto_doc(doc)
        ini, fin = ps.get("inicio"), ps.get("fin")
        if texto_doc is None:
            p.append(f"item {qid}: pasaje {j}: falta corpus/processed/{doc}.txt")
        elif ini is None or fin is None or texto_doc[ini:fin] != ps.get("texto"):
            p.append(f"item {qid}: pasaje {j}: texto distinto de {doc}.txt[{ini}:{fin}]")
    respaldo = set()
    for ps in pasajes[:MAX_PASAJES]:
        respaldo |= extract(str(ps.get("texto") or ""))
    sin_respaldo = bodies(extract(answer_text(s))) - bodies(respaldo)
    if sin_respaldo:
        p.append(f"item {qid}: citas sin respaldo {sorted(sin_respaldo)}")
    return p


def validate(path: Path, schema: Path = SCHEMA, expected_ids: Optional[set[int]] = None) -> list[str]:
    """Lista de problemas (vacía si la entrega es válida)."""
    from jsonschema import Draft202012Validator

    validador = Draft202012Validator(io.read_json(schema))
    filas, problemas = _leer(path)
    vistos: set[int] = set()
    for s in filas:
        qid = s.get("id")
        if not isinstance(qid, int):
            problemas.append(f"'id' ausente o no entero: {qid!r}")
            continue
        if qid in vistos:
            problemas.append(f"item {qid}: duplicado")
        vistos.add(qid)
        if expected_ids is not None and qid not in expected_ids:
            problemas.append(f"item {qid}: no pertenece al split")
        problemas.extend(validar_item(s, validador))
    if expected_ids is not None and expected_ids - vistos:
        faltan = sorted(expected_ids - vistos)
        problemas.append(f"{len(faltan)} ids del split sin respuesta: {faltan[:20]}")
    return problemas


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("submission", type=Path)
    ap.add_argument("--split", choices=list(SPLITS), default=None, help="exige exactamente los ids del split")
    ap.add_argument("--ids", type=int, nargs="*", help="exige exactamente estos ids")
    args = ap.parse_args()
    esperados = set(args.ids) if args.ids else (ids_del_split(args.split) if args.split else None)
    problemas = validate(args.submission, expected_ids=esperados)
    for p in problemas:
        print(p)
    print(f"{len(problemas)} problemas")
    return 1 if problemas else 0


if __name__ == "__main__":
    sys.exit(main())
