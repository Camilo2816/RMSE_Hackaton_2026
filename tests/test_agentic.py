"""Agéntico: planner de subconsultas, señal de evidencia débil y bucle acotado (sin índice ni LLM)."""
from src.common.config import load_config
from src.common.types import Answer, Passage, Question, Verdict
from src.generation.llm import LLMError
from src.pipelines.agentic import AgenticPipeline
from src.pipelines.base import Stages
from src.planning.subqueries import MAX_PALABRAS, SubqueryPlanner, normalizar
from src.verification.abstention import MOTIVO_DEBIL, evidencia_debil

CFG = load_config("configs/agentic.yaml")
ABIERTA = Question(id=1, formato="open_ended", pregunta="Una persona sufrió un daño. ¿Qué puede hacer?")
CERRADA = Question(id=2, formato="multiple_choice", pregunta="¿Cuál?",
                   opciones={"A": "a", "B": "b", "C": "c", "D": "d"})


def _pasaje(i: int, score: float, fuente: str = "q", doc: str = "ley_1_2000") -> Passage:
    return Passage(doc_id=doc, chunk_id=i, norma="Ley 1 de 2000", articulo=str(i),
                   texto=f"Ley 1 de 2000. ARTICULO {i}.", score=score, fuente_query=fuente)


class LLMFalso:
    def __init__(self, salida=None, error=False):
        self.salida, self.error, self.prompts = salida, error, []

    def complete_json(self, prompt, schema, formato=None, calls=None):
        self.prompts.append(prompt)
        if self.error:
            calls.append({"intento": 1, "error": "timeout"})
            raise LLMError("timeout")
        calls.append({"intento": 1, "segundos": 0.1})
        return self.salida


def _planner(salida=None, error=False, **planner_cfg):
    cfg = {**CFG, "planner": {**CFG["planner"], **planner_cfg}}
    return SubqueryPlanner(LLMFalso(salida, error), 3, cfg)


# --- planner ---------------------------------------------------------------

def test_normalizar_dedup_tope_y_sin_copia_de_la_pregunta():
    larga = " ".join(["palabra"] * (MAX_PALABRAS + 10))
    subs = ["  acción  popular ", "Acción popular", "", 7, ABIERTA.pregunta, larga, "habeas data", "cuarta"]
    out = normalizar(subs, ABIERTA, 3)
    assert out == ["acción popular", " ".join(["palabra"] * MAX_PALABRAS), "habeas data"]
    assert normalizar("no es lista", ABIERTA, 3) == []


def test_plan_incluye_la_pregunta_primero_y_registra_la_llamada():
    calls = []
    p = _planner({"problema_juridico": "x", "figuras_juridicas": ["f1"], "subconsultas": ["s1", "s2"]})
    assert p.plan(ABIERTA, "motivo", calls) == [ABIERTA.texto_busqueda(), "s1", "s2"]
    assert calls == [{"etapa": "planner", "intento": 1, "segundos": 0.1, "figuras_juridicas": ["f1"]}]
    assert "motivo" in p.llm.prompts[0] and "exactamente 3" in p.llm.prompts[0]


def test_plan_solo_subconsultas():
    p = _planner({"subconsultas": ["s1"]}, incluir_pregunta=False)
    assert p.plan(ABIERTA) == ["s1"]


def test_plan_fallback_a_la_pregunta():
    """Si el LLM falla o no da subconsultas útiles, se recupera como el baseline."""
    calls = []
    assert _planner(error=True).plan(ABIERTA, calls=calls) == [ABIERTA.texto_busqueda()]
    assert calls[0]["etapa"] == "planner" and calls[0]["error"] == "timeout"
    assert _planner({"subconsultas": []}).plan(ABIERTA) == [ABIERTA.texto_busqueda()]


# --- señal de evidencia débil ------------------------------------------------

def test_evidencia_debil():
    debil = [_pasaje(1, 0.3), _pasaje(2, 0.1)]
    assert evidencia_debil(ABIERTA, debil, CFG) == MOTIVO_DEBIL  # fijo: no depende de qué se recuperó
    assert evidencia_debil(ABIERTA, [_pasaje(1, 0.9)], CFG) is None
    assert evidencia_debil(CERRADA, debil, CFG) is None  # cerradas nunca
    assert evidencia_debil(ABIERTA, [_pasaje(9, 2.0, "lookup"), *debil], CFG) is None  # la norma nombrada ya está
    assert evidencia_debil(ABIERTA, [], CFG) is None
    sin_umbral = {**CFG, "verification": {**CFG["verification"], "replan_min_rerank_score": None}}
    assert evidencia_debil(ABIERTA, debil, sin_umbral) is None


# --- bucle -----------------------------------------------------------------

class RecuperadorFalso:
    """La pregunta trae evidencia débil (0,3); cualquier subconsulta, fuerte (0,9)."""

    def __init__(self, fuerte_siempre=False):
        self.fuerte_siempre = fuerte_siempre

    def search(self, query, k):
        fuerte = self.fuerte_siempre or query.startswith("sub")
        base = 100 if query.startswith("sub") else 0
        return [_pasaje(base + i, 0.9 if fuerte else 0.3, query) for i in range(3)]


class PlannerFalso:
    def __init__(self):
        self.feedbacks = []

    def plan(self, question, feedback=None, calls=None):
        self.feedbacks.append(feedback)
        return [question.texto_busqueda(), "sub 1", "sub 2"]


class Agentico(AgenticPipeline):
    """answer() guionado: devuelve los veredictos de la lista en orden."""

    def __init__(self, veredictos, fuerte_siempre=False):
        stages = Stages(planner=PlannerFalso(), lookup=None, retriever=RecuperadorFalso(fuerte_siempre),
                        reranker=None, generator=None)
        super().__init__(stages, CFG)
        self.veredictos = list(veredictos)
        self.vistos = []

    def answer(self, question, passages, trace):
        self.vistos.append(passages)
        v = self.veredictos.pop(0)
        trace.verdicts.append(v)
        return Answer(id=question.id, formato=question.formato, respuesta_correcta="A"), v


def test_evidencia_fuerte_sigue_el_camino_del_baseline():
    pipe = Agentico([Verdict.OK], fuerte_siempre=True)
    _, trace = pipe.run(ABIERTA)
    assert pipe.stages.planner.feedbacks == []
    assert trace.iterations == 1 and trace.replan_reasons == []
    assert trace.subqueries == [ABIERTA.texto_busqueda()]


def test_cerradas_nunca_replanean():
    pipe = Agentico([Verdict.OK])
    _, trace = pipe.run(CERRADA)
    assert pipe.stages.planner.feedbacks == [] and trace.iterations == 1


def test_evidencia_debil_replanea_una_vez_antes_de_generar():
    pipe = Agentico([Verdict.EVIDENCIA_INSUFICIENTE])
    answer, trace = pipe.run(ABIERTA)
    assert pipe.stages.planner.feedbacks == [MOTIVO_DEBIL]
    assert trace.iterations == 2 and len(trace.replan_reasons) == 1
    assert len(pipe.vistos) == 1  # max_iter = 1: no hay segundo re-planeo tras generar
    assert any(p.chunk_id >= 100 for p in pipe.vistos[0])  # el LLM vio lo que trajeron las subconsultas
    assert len(answer.pasajes_recuperados) <= 10
    assert answer.abstencion is True


def test_respuesta_vacia_replanea_tras_generar():
    pipe = Agentico([Verdict.EVIDENCIA_INSUFICIENTE, Verdict.OK], fuerte_siempre=True)
    answer, trace = pipe.run(ABIERTA)
    assert pipe.stages.planner.feedbacks and trace.iterations == 2
    assert trace.verdicts == [Verdict.EVIDENCIA_INSUFICIENTE, Verdict.OK]
    assert trace.abstention_reason is None and answer.abstencion is False


def test_sin_iteraciones_no_replanea():
    pipe = Agentico([Verdict.OK])
    pipe.cfg = {**CFG, "verification": {**CFG["verification"], "max_iter": 0}}
    _, trace = pipe.run(ABIERTA)
    assert pipe.stages.planner.feedbacks == [] and trace.iterations == 1
