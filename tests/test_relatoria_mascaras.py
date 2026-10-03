"""src/retrieval/relatoria.py: máscaras del híbrido (opción C y solo_lookup) sobre un índice de juguete."""
from types import SimpleNamespace

from src.retrieval import relatoria

META = [{"doc_id": "ley_1", "seccion": None}, {"doc_id": "sentencia_cosechada", "seccion": "ficha"},
        {"doc_id": "sentencia_cosechada", "seccion": "consideraciones"}, {"doc_id": "resolucion_x", "seccion": None}]


def _cfg(tmp_path, **retrieval):
    inv = tmp_path / "relatoria.yaml"
    inv.write_text('documentos:\n  - doc_id: "sentencia_cosechada"\n', encoding="utf-8")
    return {"retrieval": {"relatoria_inventario": str(inv), **retrieval}}


def test_sin_opciones_no_hay_mascara(tmp_path):
    idx = SimpleNamespace(metadata=META)
    cfg = _cfg(tmp_path)
    assert relatoria.mascara_denso(idx, cfg) is None
    assert relatoria.mascara_bm25(idx, cfg) is None


def test_opcion_c_y_solo_lookup(tmp_path):
    idx = SimpleNamespace(metadata=META)
    cfg = _cfg(tmp_path, denso_relatoria_secciones=[], bm25_relatoria=False, solo_lookup=["resolucion_x"])
    assert relatoria.mascara_denso(idx, cfg).tolist() == [True, False, False, False]
    assert relatoria.mascara_bm25(idx, cfg).tolist() == [True, False, False, False]


def test_solo_lookup_sin_opcion_c(tmp_path):
    idx = SimpleNamespace(metadata=META)
    cfg = _cfg(tmp_path, solo_lookup=["resolucion_x"])
    assert relatoria.mascara_denso(idx, cfg).tolist() == [True, True, True, False]
    assert relatoria.mascara_bm25(idx, cfg).tolist() == [True, True, True, False]
