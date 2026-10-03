"""API de la interfaz (src/api) con un pipeline falso: sin GPU, sin índice, sin Ollama."""
import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.common.types import Answer, Passage, Question, Trace, Verdict

LEY_472 = Passage(doc_id="ley_472_1998", chunk_id=3, norma="Ley 472 de 1998", articulo="3",
                  texto="Ley 472 de 1998. ARTÍCULO 3o. ACCIONES DE GRUPO. Son aquellas acciones interpuestas "
                        "por un número plural de personas.", score=0.91, fuente_query="q")
CODIGO_CIVIL = Passage(doc_id="codigo_civil", chunk_id=7, norma="Código Civil", articulo="1502",
                       texto="Código Civil. ARTÍCULO 1502. Para que una persona se obligue a otra por un acto "
                             "o declaración de voluntad, es necesario que sea legalmente capaz.", score=0.52)


class PipelineFalso:
    """Devuelve una respuesta fija por formato; cita una norma respaldada y otra que no está en los pasajes."""

    def __init__(self):
        self.preguntas: list[Question] = []

    def run(self, q: Question) -> tuple[Answer, Trace]:
        self.preguntas.append(q)
        pasajes = [LEY_472, CODIGO_CIVIL]
        a = Answer(id=q.id, formato=q.formato, pasajes_recuperados=pasajes)
        if q.formato == "multiple_choice":
            a.respuesta_correcta = "C"
            a.justificacion = "Según la Ley 472 de 1998, artículo 3, procede la acción de grupo."
            a.descarte_opciones = {k: "No corresponde." for k in "ABD"}
        elif q.formato == "semi_open":
            a.respuesta = "Sí: la Ley 1010 de 2006 regula el acoso laboral."
            a.palabras_clave = ["acoso laboral"]
            a.referencia_legal = "Ley 472 de 1998, artículo 3"
        else:
            a.marco_normativo = "Código Civil, artículo 1502."
            a.analisis = "Análisis."
            a.jurisprudencia = "Sentencia C-355 de 2006."
            a.conclusion = "Conclusión."
        t = Trace(question_id=q.id, subqueries=[q.pregunta], fused_passages=pasajes,
                  verdicts=[Verdict.OK], iterations=1, timings={"retrieval": 0.12, "generation": 3.4})
        return a, t


class PipelineRoto:
    def run(self, q):
        raise RuntimeError("Ollama caído")


@pytest.fixture
def pipeline():
    return PipelineFalso()


@pytest.fixture
def cliente(pipeline):
    return TestClient(create_app({"pipeline": "baseline"}, pipeline=pipeline, config_path="configs/baseline.yaml"))


OPCIONES = {"A": "uno", "B": "dos", "C": "tres", "D": "cuatro"}


def test_multiple_choice(cliente, pipeline):
    r = cliente.post("/preguntar", json={"pregunta": " ¿Procede la acción de grupo? ", "formato": "multiple_choice",
                                         "opciones": OPCIONES, "config": "configs/baseline.yaml"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == {"answer", "trace", "normas_citadas", "pasajes"}
    a = body["answer"]
    assert a["respuesta_correcta"] == "C" and set(a["descarte_opciones"]) == {"A", "B", "D"}
    assert a["abstencion"] is False and isinstance(a["latencia_ms"], int)
    assert "respuesta" not in a
    assert pipeline.preguntas[0].pregunta == "¿Procede la acción de grupo?"
    assert pipeline.preguntas[0].opciones == OPCIONES
    assert body["normas_citadas"][0]["cita"] == "Ley 472 de 1998, art. 3"
    assert body["normas_citadas"][0]["respaldada"] is True
    assert body["normas_citadas"][0]["articulo_en_pasajes"] is True


def test_semi_open_marca_la_cita_sin_respaldo(cliente, pipeline):
    r = cliente.post("/preguntar", json={"pregunta": "¿Qué norma regula el acoso laboral?", "formato": "semi_open"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body["answer"]) >= {"respuesta", "palabras_clave", "referencia_legal", "pasajes_recuperados"}
    citas = {n["cita"]: n["respaldada"] for n in body["normas_citadas"]}
    assert citas == {"Ley 1010 de 2006": False, "Ley 472 de 1998, art. 3": True}
    assert pipeline.preguntas[0].opciones is None


def test_open_ended(cliente):
    r = cliente.post("/preguntar", json={"pregunta": "Caso", "formato": "open_ended", "opciones": None})
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body["answer"]) >= {"marco_normativo", "analisis", "jurisprudencia", "conclusion"}
    citas = {n["cita"]: n["respaldada"] for n in body["normas_citadas"]}
    assert citas == {"Código Civil, art. 1502": True, "Sentencia C-355 de 2006": False}


def test_forma_de_trace_y_pasajes(cliente):
    body = cliente.post("/preguntar", json={"pregunta": "Caso", "formato": "open_ended"}).json()
    t = body["trace"]
    assert t["subqueries"] == ["Caso"] and t["verdicts"] == ["ok"] and t["iterations"] == 1
    assert t["timings"] == {"retrieval": 0.12, "generation": 3.4}
    assert t["fused_passages"][0]["norma"] == "Ley 472 de 1998" and t["fused_passages"][0]["articulo"] == "3"
    assert [p["doc_id"] for p in body["answer"]["pasajes_recuperados"]] == ["ley_472_1998", "codigo_civil"]
    pasajes = body["pasajes"]
    assert pasajes[1]["norma"] == "Código Civil" and pasajes[1]["score"] == 0.52
    i = next(i for i, n in enumerate(body["normas_citadas"]) if n["cita"].startswith("Código Civil"))
    assert pasajes[1]["normas_citadas"] == [i] and pasajes[0]["normas_citadas"] == []
    patrones = body["normas_citadas"][i]["patrones"]
    assert patrones["cuerpo"] and patrones["articulo"]


def test_patrones_resaltan_en_texto_normalizado():
    import re

    from src.api.normas import patron_articulo, patrones_cuerpo
    from src.verification.citations import norm

    assert re.search(patrones_cuerpo(("ley", "472", "1998", None))[0], norm(LEY_472.texto))
    assert re.search(patron_articulo("3"), norm("Ley 472 de 1998. ARTÍCULO 3o. ACCIONES"))
    assert not re.search(patron_articulo("3"), norm("ARTÍCULO 30."))
    assert any(re.search(p, norm(CODIGO_CIVIL.texto)) for p in patrones_cuerpo(("codigo_civil", None, None, "1502")))
    assert re.search(patrones_cuerpo(("jurisprudencia", "C-355", "2006", None))[0], norm("la Sentencia C-355 de 2006"))


@pytest.mark.parametrize("cuerpo", [
    {"pregunta": "x", "formato": "abierta"},
    {"pregunta": "x", "formato": "multiple_choice"},
    {"pregunta": "x", "formato": "multiple_choice", "opciones": {"A": "a", "B": "b", "C": "c"}},
    {"pregunta": "x", "formato": "multiple_choice", "opciones": {"A": "a", "B": "b", "C": "c", "D": " "}},
    {"pregunta": "   ", "formato": "semi_open"},
    {"formato": "semi_open"},
])
def test_entrada_invalida_422(cliente, pipeline, cuerpo):
    assert cliente.post("/preguntar", json=cuerpo).status_code == 422
    assert pipeline.preguntas == []


def test_config_distinta_409(cliente):
    r = cliente.post("/preguntar", json={"pregunta": "x", "formato": "semi_open", "config": "configs/agentic.yaml"})
    assert r.status_code == 409


def test_error_del_pipeline_500():
    c = TestClient(create_app({"pipeline": "baseline"}, pipeline=PipelineRoto()))
    r = c.post("/preguntar", json={"pregunta": "x", "formato": "semi_open"})
    assert r.status_code == 500 and "Ollama caído" in r.json()["detail"]


def test_salud_e_interfaz(cliente):
    s = cliente.get("/salud").json()
    assert s["estado"] == "ok" and s["pipeline"] == "baseline" and s["ocupado"] is False
    r = cliente.get("/")
    assert r.status_code == 200 and "<html" in r.text.lower()
