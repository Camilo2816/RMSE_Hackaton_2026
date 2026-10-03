"""src/common: config, tipos serializables, tiempos y respaldo de citas."""
import json
import sys

from src.common import rutas
from src.common.config import deep_merge, load_config
from src.common.timing import timed
from src.common.types import Answer, Passage, Question, Trace, Verdict
from src.verification.citations import respaldadas

if str(rutas.SCRIPTS) not in sys.path:
    sys.path.insert(0, str(rutas.SCRIPTS))
import evaluate  # noqa: E402  scripts/evaluate.py, sin modificar

P = Passage(doc_id="ley_472_1998", chunk_id=3, norma="Ley 472 de 1998", articulo="3",
            texto="Ley 472 de 1998. ARTICULO 3o. ACCIONES DE GRUPO.", inicio=10, fin=58,
            score=0.12345678, fuente_query="q")


def test_deep_merge_no_muta_y_sobrescribe():
    base = {"a": 1, "b": {"x": 1, "y": 2}}
    over = {"b": {"y": 3}, "c": 4}
    assert deep_merge(base, over) == {"a": 1, "b": {"x": 1, "y": 3}, "c": 4}
    assert base == {"a": 1, "b": {"x": 1, "y": 2}}


def test_load_config_baseline_y_agentic():
    base = load_config("configs/baseline.yaml")
    agentic = load_config("configs/agentic.yaml")
    assert base["pipeline"] == "baseline" and agentic["pipeline"] == "agentic"
    assert base["generation"]["temperature"] == 0 == agentic["generation"]["temperature"]
    assert agentic["verification"]["max_iter"] == 1 and agentic["verification"]["drop_unsupported"] is True
    assert agentic["verification"]["referencia_desde_pasajes"] == {
        "semi_open": {"fuentes": 10, "menciones": 4},
        "multiple_choice": {"fuentes": 10, "menciones": 4},
        "open_ended": {"fuentes": 0, "menciones": 0},
    }
    assert base["fusion"]["max_passages"] == 10


def test_question_no_toma_respuestas():
    fila = json.loads((rutas.DATA / "sample_50.jsonl").read_text(encoding="utf-8").splitlines()[0])
    q = Question.from_dict(fila)
    assert q.id == fila["id"] and q.pregunta == fila["pregunta"]
    assert not hasattr(q, "legal_basis") and not hasattr(q, "respuesta_correcta")


def test_to_submission_valida_para_el_evaluador():
    lineas = [
        Answer(id=1, formato="multiple_choice", respuesta_correcta="A", justificacion="Ley 472 de 1998.",
               descarte_opciones={"B": "x", "C": "y", "D": "z"}, pasajes_recuperados=[P]),
        Answer(id=2, formato="semi_open", respuesta="Sí.", palabras_clave=["a"],
               referencia_legal="Ley 472 de 1998", pasajes_recuperados=[P], latencia_ms=1200),
        Answer(id=3, formato="open_ended", abstencion=True),
    ]
    subs = [a.to_submission() for a in lineas]
    assert evaluate.validate(subs, {1, 2, 3}) == []
    assert set(subs[0]) == {"id", "formato", "abstencion", "respuesta_correcta", "justificacion",
                            "descarte_opciones", "pasajes_recuperados"}
    assert subs[1]["pasajes_recuperados"][0] == {"doc_id": "ley_472_1998", "inicio": 10, "fin": 58,
                                                 "texto": P.texto, "score": 0.123457}
    assert subs[2]["marco_normativo"] == "" and subs[2]["pasajes_recuperados"] == []
    json.dumps(subs, allow_nan=False)


def test_trace_serializable_y_timed():
    t = Trace(question_id=1, subqueries=["q"], passages_by_query={"q": [P]}, fused_passages=[P],
              verdicts=[Verdict.OK])
    with timed(t, "retrieval"):
        pass
    with timed(t, "retrieval"):
        pass
    d = json.loads(json.dumps(t.to_json(), allow_nan=False))
    assert d["verdicts"] == ["ok"] and d["fused_passages"][0]["norma"] == "Ley 472 de 1998"
    assert set(d["timings"]) == {"retrieval"}


def test_respaldadas_igual_que_evaluate():
    otros = [P] + [Passage(doc_id="cc", chunk_id=i, norma="Código Civil", articulo=str(i),
                           texto=f"Código Civil. ARTICULO {i}.") for i in range(12)]
    sub = {"pasajes_recuperados": [p.to_submission() for p in otros]}
    assert respaldadas(otros) == evaluate.citas_respaldadas(sub)
