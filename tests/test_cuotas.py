"""retrieval/cuotas.py: tope por tipo de documento, con reemplazos en orden y sin perder pasajes."""
from types import SimpleNamespace

from src.common.types import Passage
from src.retrieval.cuotas import Cuotas

META = ([{"doc_id": "sentencia_ce_1", "tipo": "sentencia", "seccion": "consideraciones"}] * 6
        + [{"doc_id": "sentencia_ce_1", "tipo": "sentencia", "seccion": "salvamento_voto"}] * 2
        + [{"doc_id": "decreto_1072_2015", "tipo": "decreto", "seccion": None}] * 3
        + [{"doc_id": "ley_472_1998", "tipo": "ley", "seccion": None}] * 4)
CFG = {"cuotas": {"sentencia": 3, "voto": 0, "reglamentaria": 2, "reglamentarias": ["decreto_1072_2015"]}}


class LookupFalso:
    def __init__(self, docs=()):
        self.docs = list(docs)

    def documentos(self, query):
        return self.docs


def _p(i: int) -> Passage:
    return Passage(doc_id=META[i]["doc_id"], chunk_id=i, norma="x", articulo=None, texto="x")


def test_tope_por_clase_y_reemplazo_en_orden():
    c = Cuotas(SimpleNamespace(metadata=META), CFG, LookupFalso())
    out = c.aplicar([_p(i) for i in range(len(META))], "¿procede la acción de grupo?", 10)
    # 3 sentencias, 0 votos, 2 DUR, 4 leyes; falta 1 y vuelve el primer cedido (3) en su lugar original
    assert [p.chunk_id for p in out] == [0, 1, 2, 3, 8, 9, 11, 12, 13, 14]


def test_documento_nombrado_no_cuenta_y_pregunta_por_jurisprudencia_sube_el_tope():
    c = Cuotas(SimpleNamespace(metadata=META), CFG, LookupFalso(["sentencia_ce_1"]))
    assert [p.chunk_id for p in c.aplicar([_p(i) for i in range(8)], "q", 8)] == list(range(8))
    c = Cuotas(SimpleNamespace(metadata=META), CFG, LookupFalso())
    out = c.aplicar([_p(i) for i in range(6)] + [_p(11)], "¿cuál es el precedente jurisprudencial?", 7)
    assert sum(p.doc_id == "sentencia_ce_1" for p in out) == 6


def test_nunca_menos_pasajes_que_sin_tope():
    c = Cuotas(SimpleNamespace(metadata=META), CFG, LookupFalso())
    out = c.aplicar([_p(i) for i in range(8)], "q", 8)
    assert len(out) == 8 and [p.chunk_id for p in out] == list(range(8))


def test_primarias_son_las_filas_sin_clase():
    c = Cuotas(SimpleNamespace(metadata=META), CFG, LookupFalso())
    assert [i for i in range(len(META)) if c.primaria[i]] == [11, 12, 13, 14]  # la Ley 472, no el DUR


def test_garantizar_primarias_desplaza_los_ultimos_no_primarios():
    c = Cuotas(SimpleNamespace(metadata=META), {**CFG, "cuotas": {**CFG["cuotas"], "min_primarias": 2}},
               LookupFalso())
    assert c.min_primarias == 2
    cands = [_p(i) for i in [0, 1, 11, 2, 3]]
    out = c.garantizar(cands, [_p(11), _p(12), _p(13)], 5)
    # la 11 ya estaba; 12 y 13 entran y salen las dos últimas sentencias (2 y 3)
    assert [p.chunk_id for p in out] == [0, 1, 11, 12, 13]
    assert [p.chunk_id for p in c.garantizar(cands[:2], [_p(12)], 5)] == [0, 1, 12]  # con espacio, solo se agrega
