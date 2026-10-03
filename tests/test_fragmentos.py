"""corpus/processed/fragmentos.jsonl (solo si el corpus ya se construyó)."""
import json

import pytest

from src.common import rutas
from src.ingest import fuentes

if not rutas.FRAGMENTOS.exists():
    pytest.skip("corpus sin construir (python -m src.ingest.segmentar)", allow_module_level=True)

FRAGS = [json.loads(l) for l in rutas.FRAGMENTOS.read_text(encoding="utf-8").splitlines() if l]
DOCS = fuentes.cargar()


def test_prefijo_citable():
    """Cada fragmento empieza con su nombre citable ("Ley 472 de 1998. ..." o "Sentencia
    C-355 de 2006, Corte Constitucional. ..."), y el extractor oficial lee en ese inicio
    el cuerpo normativo del documento (condición para que respalde citas)."""
    malos = []
    for f in FRAGS:
        d = DOCS[f["doc_id"]]
        norma = fuentes.norma_de(d)
        if not f["texto"].startswith((norma + ". ", norma + ", ")):
            malos.append(f["frag_id"])
        elif d.get("canonico") and tuple(d["canonico"]) not in fuentes.canonico_de(
                f["texto"][:len(norma) + 2]):
            malos.append(f["frag_id"])
    assert not malos, malos[:10]


def test_offsets_validos():
    """inicio/fin válidos sobre <doc_id>.txt: el texto del pasaje es literal."""
    textos: dict[str, str] = {}
    malos = []
    for f in FRAGS:
        t = textos.setdefault(f["doc_id"], (rutas.PROCESSED / f"{f['doc_id']}.txt")
                              .read_text(encoding="utf-8"))
        if t[f["inicio"]:f["fin"]] != f["texto"]:
            malos.append(f["frag_id"])
    assert not malos, malos[:10]


def test_ids_y_orden():
    assert [f["chunk_id"] for f in FRAGS] == list(range(len(FRAGS)))
    assert len({f["frag_id"] for f in FRAGS}) == len(FRAGS)
    assert [f["doc_id"] for f in FRAGS] == sorted(f["doc_id"] for f in FRAGS)


def test_sin_mojibake_ni_vacios():
    malos = [f["frag_id"] for f in FRAGS
             if any(x in f["texto"] for x in ("Ã", "Â", "�")) or len(f["texto"]) < 20]
    assert not malos, malos[:10]


def test_metadatos_minimos():
    """Paso 1 del enunciado: cada fragmento identifica norma y artículo (o sección)."""
    for f in FRAGS:
        assert f["doc_id"] and f["norma"] and f["tipo"], f["frag_id"]
        assert f["articulo"] or f["seccion"], f["frag_id"]
        assert f["vigencia"] in ("vigente", "modificado", "derogado", "inexequible",
                                 "desconocida"), f["frag_id"]
