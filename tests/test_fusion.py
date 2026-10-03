"""fusion.fuse y fusion.rrf: límite de 10 y orden determinista."""
from src.common.types import Passage
from src.retrieval.fusion import fuse, limitar_por_documento, ordenar, penalizar_vigencia, reordenar_con, rrf


def _p(doc: str, chunk: int, score: float = 0.0, q: str = "q") -> Passage:
    return Passage(doc_id=doc, chunk_id=chunk, norma=doc, articulo=None, texto=f"{doc} {chunk}",
                   score=score, fuente_query=q)


def test_nunca_mas_de_10_pasajes():
    """fuse nunca devuelve más de max_passages."""
    listas = {f"q{j}": [_p("d", j * 100 + i, 1.0 - i / 100) for i in range(30)] for j in range(3)}
    lookup = [_p("lookup", i) for i in range(4)]
    assert len(fuse(listas, lookup)) == 10
    assert len(fuse({}, [_p("lookup", i) for i in range(15)])) == 10
    assert len(fuse(listas, lookup, max_passages=5)) == 5


def test_mismo_input_mismo_orden():
    """Mismo input → mismo orden, incluidos empates."""
    empatados = [_p(d, c, 0.5) for d, c in [("b", 2), ("a", 9), ("b", 1), ("a", 3)]]
    esperado = [("a", 3), ("a", 9), ("b", 1), ("b", 2)]
    assert [p.clave for p in ordenar(empatados)] == esperado
    assert [p.clave for p in ordenar(empatados[::-1])] == esperado
    # Dos listas simétricas producen empates exactos en RRF: gana (doc_id, chunk_id).
    x, y = _p("b", 1), _p("a", 2)
    assert [p.clave for p in rrf([[x, y], [y, x]])] == [("a", 2), ("b", 1)]
    assert [p.clave for p in rrf([[y, x], [x, y]])] == [("a", 2), ("b", 1)]
    listas = {"q1": empatados, "q2": empatados[::-1]}
    assert fuse(listas, []) == fuse(dict(listas), [])


def test_lookup_primero():
    """Los hits del lookup encabezan la lista y no se duplican."""
    hit = _p("ley_472_1998", 7, 0.0, "lookup")
    listas = {"q": [_p("x", 1, 0.9), _p("ley_472_1998", 7, 0.8), _p("x", 2, 0.7)]}
    out = fuse(listas, [hit])
    assert out[0] == hit
    assert [p.clave for p in out] == [("ley_472_1998", 7), ("x", 1), ("x", 2)]


def test_rrf_suma_entre_listas():
    """Un pasaje presente en ambas listas supera a uno que encabeza solo una."""
    a, b, c = _p("a", 1), _p("b", 1), _p("c", 1)
    out = rrf([[a, b], [c, b]], k=60)
    assert out[0].clave == ("b", 1)
    assert abs(out[0].score - (1 / 62 + 1 / 62)) < 1e-12


def test_una_lista_conserva_scores():
    """Con una sola subconsulta fuse respeta el orden y los scores del reranker."""
    lista = [_p("a", 1, 0.9), _p("b", 1, 0.4)]
    assert fuse({"q": lista}, []) == lista


def test_tope_por_documento():
    """A lo sumo `tope` fragmentos por documento, en el orden recibido; nunca más de `limite`."""
    lista = [_p("largo", i, 1.0 - i / 100) for i in range(8)] + [_p("b", 1, 0.5), _p("c", 1, 0.4), _p("b", 2, 0.3)]
    out = limitar_por_documento(lista, tope=2, limite=5)
    assert [p.clave for p in out] == [("largo", 0), ("largo", 1), ("b", 1), ("c", 1), ("b", 2)]
    assert [p.clave for p in limitar_por_documento(lista, tope=2, limite=3)] == [("largo", 0), ("largo", 1), ("b", 1)]


def test_tope_rellena_si_no_alcanzan_documentos():
    """Con pocos documentos distintos, se completan los cupos con los descartados, en su orden."""
    lista = [_p("a", i, 1.0 - i / 100) for i in range(6)] + [_p("b", 1, 0.1)]
    out = limitar_por_documento(lista, tope=2, limite=5)
    assert [p.clave for p in out] == [("a", 0), ("a", 1), ("a", 2), ("a", 3), ("b", 1)]


def test_reordenar_con_hibrido_conserva_scores_del_reranker():
    """Lo que el híbrido traía arriba sube aunque el reranker lo hunda; los scores no cambian."""
    hibrido = [_p("ley", 1, 0.1), _p("a", 1, 0.1), _p("b", 1, 0.1), _p("c", 1, 0.1)]
    reranker = [_p("a", 1, 0.9), _p("b", 1, 0.8), _p("c", 1, 0.7), _p("ley", 1, 0.2)]
    out = reordenar_con(reranker, [hibrido])
    assert [p.clave for p in out] == [("a", 1), ("ley", 1), ("b", 1), ("c", 1)]
    assert {p.clave: p.score for p in out} == {p.clave: p.score for p in reranker}
    assert reordenar_con(reranker, []) == reranker


def test_fijos_ocupan_los_ultimos_lugares():
    """Los valores fijos que no entraron reemplazan los últimos; si ya estaban, nada cambia."""
    lista = [_p("d", i, 1.0 - i / 100) for i in range(20)]
    smlmv = _p("decreto_159_2026", 7, q="valores")
    out = fuse({"q": lista}, [], 10, [smlmv])
    assert len(out) == 10
    assert [p.clave for p in out[:9]] == [p.clave for p in lista[:9]]
    assert out[-1].clave == smlmv.clave
    assert fuse({"q": lista}, [], 10, [lista[3]]) == fuse({"q": lista}, [])
    assert fuse({"q": lista[:4]}, [], 10, [smlmv]) == [*lista[:4], smlmv]


def test_penalizar_vigencia_es_suave_y_conserva_scores():
    """Derogado e inexequible bajan frente a un vigente parecido, pero no se descartan ni cambian su score."""
    def v(doc, score, vigencia):
        return Passage(doc_id=doc, chunk_id=1, norma=doc, articulo=None, texto=doc, score=score, vigencia=vigencia)
    lista = [v("ley_1943", 0.92, "inexequible"), v("ley_2010", 0.90, "vigente"),
             v("ley_640", 0.95, "derogado"), v("otra", 0.50, "vigente"), v("sentencia", 0.85, None)]
    out = penalizar_vigencia(lista, {"derogado": 0.85, "inexequible": 0.85})
    assert [p.doc_id for p in out] == ["ley_2010", "sentencia", "ley_640", "ley_1943", "otra"]
    assert {p.doc_id: p.score for p in out} == {p.doc_id: p.score for p in lista}
    assert penalizar_vigencia(lista, {}) == lista
