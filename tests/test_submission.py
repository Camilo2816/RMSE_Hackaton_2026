"""Salida de la corrida: writer reanudable y validate (esquema oficial + reglas propias)."""
import json
import math

import pytest

from src.common import io, rutas
from src.common.types import Answer, Passage, Question
from src.submission import writer
from src.submission.validate import validate

if not rutas.FRAGMENTOS.exists():
    pytest.skip("corpus/processed sin extraer (corpus_snapshot.zip)", allow_module_level=True)


def _fragmentos(n: int) -> list[dict]:
    out = []
    for f in io.iter_jsonl(rutas.FRAGMENTOS):
        if f["articulo"]:
            out.append(f)
        if len(out) >= n:
            return out
    return out


def _pasaje(f: dict, score: float = 0.5) -> Passage:
    return Passage(doc_id=f["doc_id"], chunk_id=f["chunk_id"], norma=f["norma"], articulo=f["articulo"],
                   texto=f["texto"], inicio=f["inicio"], fin=f["fin"], score=score)


@pytest.fixture(scope="module")
def frags():
    return _fragmentos(11)


def _semi(qid: int, f: dict, pasajes: list[Passage]) -> Answer:
    return Answer(id=qid, formato="semi_open", pasajes_recuperados=pasajes,
                  respuesta=f"{f['norma']}, artículo {f['articulo']}, regula el punto. Dos. Tres.",
                  palabras_clave=["uno"], referencia_legal=f"{f['norma']}, artículo {f['articulo']}", latencia_ms=10)


def _escribir(tmp_path, filas: list[dict]):
    path = tmp_path / "submission.jsonl"
    path.write_text("".join(json.dumps(d, ensure_ascii=False) + "\n" for d in filas), encoding="utf-8")
    return path


def test_valida_contra_schema(tmp_path, frags):
    """submission.jsonl valida contra schema/submission.schema.json y las reglas propias."""
    f = frags[0]
    mc = Answer(id=2, formato="multiple_choice", pasajes_recuperados=[_pasaje(f)], respuesta_correcta="B",
                justificacion=f"Lo dispone {f['norma']}.", descarte_opciones={"A": "a", "C": "c", "D": "d"})
    abst = Answer(id=3, formato="open_ended", abstencion=True, pasajes_recuperados=[_pasaje(f)])
    path = tmp_path / "submission.jsonl"
    writer.write_submissions([mc, _semi(1, f, [_pasaje(f)]), abst], path)
    assert [json.loads(l)["id"] for l in path.read_text(encoding="utf-8").splitlines()] == [1, 2, 3]
    assert validate(path, expected_ids={1, 2, 3}) == []


def test_detecta_problemas(tmp_path, frags):
    f, g = frags[0], frags[1]
    base = _semi(1, f, [_pasaje(f)]).to_submission()

    def problemas(**cambios):
        d = json.loads(json.dumps(base))
        d.update(cambios)
        return validate(_escribir(tmp_path, [d]), expected_ids={1})

    assert any("sin respaldo" in p for p in problemas(respuesta="La Ley 9999 de 1999 lo dice. Dos. Tres."))
    assert any("campos vacíos" in p for p in problemas(referencia_legal=""))
    otro = dict(base["pasajes_recuperados"][0], texto=g["texto"])
    assert any("texto distinto" in p for p in problemas(pasajes_recuperados=[otro]))
    assert any("corpus_manifest" in p for p in problemas(pasajes_recuperados=[dict(otro, doc_id="no_existe")]))
    assert any("máximo 10" in p for p in problemas(pasajes_recuperados=[base["pasajes_recuperados"][0]] * 11))
    assert any("no pertenece" in p for p in problemas(id=7))
    mc = {"id": 1, "formato": "multiple_choice", "abstencion": False, "respuesta_correcta": "E",
          "justificacion": "x", "descarte_opciones": {"A": "a"}, "pasajes_recuperados": base["pasajes_recuperados"]}
    assert any("fuera de A–D" in p for p in validate(_escribir(tmp_path, [mc]), expected_ids={1}))
    nan = json.dumps(base).replace('"score": 0.5', '"score": NaN')
    (tmp_path / "nan.jsonl").write_text(nan + "\n", encoding="utf-8")
    assert any("NaN" in p for p in validate(tmp_path / "nan.jsonl", expected_ids={1}))
    assert any("duplicado" in p for p in validate(_escribir(tmp_path, [base, base]), expected_ids={1}))
    assert not math.isnan(base["pasajes_recuperados"][0]["score"])


def test_reanudable_descarta_linea_cortada(tmp_path, frags):
    from src.common.types import Trace

    f = frags[0]
    for qid in (5, 3):
        writer.agregar(tmp_path, _semi(qid, f, [_pasaje(f)]), Trace(question_id=qid))
    with (tmp_path / writer.SUBMISSION).open("a", encoding="utf-8") as fh:
        fh.write('{"id": 9, "formato": "semi_o')  # caída a mitad de escritura
    subs, traces = writer.leer_hechos(tmp_path)
    assert list(subs) == [3, 5] and list(traces) == [3, 5]
    assert len((tmp_path / writer.SUBMISSION).read_text(encoding="utf-8").splitlines()) == 2


def test_pasajes_igual_a_los_del_llm(frags):
    """pasajes_recuperados = los pasajes que vio el LLM (≤ 10)."""
    if not (rutas.INDEX / "config.json").exists():
        pytest.skip("índice sin construir")
    from src.common.config import load_config
    from src.generation.answer import a_answer
    from src.pipelines.registry import build_pipeline

    class GeneradorEspia:
        visto: list[Passage] = []

        def generate(self, question, passages, calls=None):
            GeneradorEspia.visto = list(passages)
            return a_answer(question, passages, {"respuesta": "Respuesta.", "palabras_clave": ["x"],
                                                 "referencia_legal": passages[0].norma})

    pipe = build_pipeline(load_config("configs/baseline.yaml"), generador=False)
    pipe.stages.generator = GeneradorEspia()
    q = Question(id=1, formato="semi_open", pregunta="¿Qué establece el artículo 1502 del Código Civil?")
    answer, trace = pipe.run(q)
    assert 0 < len(GeneradorEspia.visto) <= 10
    assert answer.pasajes_recuperados == GeneradorEspia.visto == trace.fused_passages
    assert answer.to_submission()["pasajes_recuperados"] == [p.to_submission() for p in GeneradorEspia.visto]


def test_estructura_partes_une_las_partes_en_los_campos_oficiales():
    """generation.estructura: el esquema pide partes y el Answer lleva las claves oficiales."""
    from src.generation.answer import a_answer, output_schema

    assert output_schema("semi_open") != output_schema("semi_open", "partes")
    assert list(output_schema("semi_open", "partes_razonadas")["properties"])[0] == "razonamiento"
    assert output_schema("multiple_choice", "partes") == output_schema("multiple_choice")
    semi = a_answer(Question(id=1, formato="semi_open", pregunta="p"), [], {
        "razonamiento": "no se entrega", "respuesta_directa": "Sí procede.", "fundamento": "La regla dice X.",
        "alcance": "Salvo Y.", "palabras_clave": ["x"], "referencia_legal": "Ley 1 de 2000"})
    assert semi.respuesta == "Sí procede. La regla dice X. Salvo Y."
    assert "no se entrega" not in str(semi.to_submission())
    abierta = a_answer(Question(id=2, formato="open_ended", pregunta="p"), [], {
        "marco_normativo": "Ley 1 de 2000", "analisis": ["Uno.", "Dos.", "Tres.", "Cuatro.", "Cinco."],
        "jurisprudencia": "", "conclusion": "Fin."})
    assert abierta.analisis == "Uno. Dos. Tres. Cuatro. Cinco."
