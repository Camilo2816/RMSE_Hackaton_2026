"""verifier.verify: filtrado de citas sin respaldo, relleno de campos y abstención."""
from src.common.config import load_config
from src.common.types import Answer, Passage, Question, Trace, Verdict
from src.pipelines.base import Stages
from src.pipelines.baseline import BaselinePipeline
from src.verification.citations import extract
from src.verification.verifier import citas_sin_respaldo, verify


def _pasaje(norma: str, articulo: str | None, cuerpo: str, chunk_id: int = 0) -> Passage:
    encabezado = f"ARTÍCULO {articulo}. " if articulo else ""
    return Passage(doc_id=norma.lower().replace(" ", "_"), chunk_id=chunk_id, norma=norma, articulo=articulo,
                   texto=f"{norma}. {encabezado}{cuerpo}", score=0.9, fuente_query="q")


LEY_100 = _pasaje("Ley 100 de 1993", "1", "El sistema de seguridad social integral tiene por objeto garantizar derechos.")
COMERCIO = _pasaje("Código de Comercio", "110", "La sociedad comercial se constituirá por escritura pública.", 1)
CONSTITUCION = _pasaje("Constitución Política de Colombia", "38", "Se garantiza el derecho de libre asociación.", 2)


def _semi(respuesta: str, referencia: str = "Ley 100 de 1993, artículo 1") -> Answer:
    return Answer(id=1, formato="semi_open", respuesta=respuesta, palabras_clave=["seguridad social"],
                  referencia_legal=referencia)


def test_cita_ausente_se_elimina():
    """Una cita ausente de los pasajes se elimina de la respuesta (con su oración)."""
    a = _semi("El sistema garantiza derechos. La Ley 50 de 1990, artículo 5, regula otra cosa. Aplica a todos.")
    trace = Trace(question_id=1)
    v = verify(a, [LEY_100], question=Question(id=1, formato="semi_open", pregunta="p"), trace=trace)
    assert v == Verdict.CITA_SIN_RESPALDO
    assert "Ley 50" not in a.respuesta
    assert a.respuesta == "El sistema garantiza derechos. Aplica a todos."
    assert trace.dropped_citations == [["ley", "50", "1990"]]
    assert not citas_sin_respaldo(a, [LEY_100])


def test_cita_respaldada_se_conserva():
    """Una cita presente en los 10 pasajes se conserva."""
    texto = "La Ley 100 de 1993, artículo 1, fija el objeto del sistema. Garantiza derechos irrenunciables."
    a = _semi(texto)
    assert verify(a, [LEY_100]) == Verdict.OK
    assert a.respuesta == texto
    assert ("ley", "100", "1993", "1") in extract(a.respuesta)


def test_oracion_mixta_se_elimina():
    """Una oración con una cita respaldada y otra sin respaldo se elimina completa."""
    a = _semi("Primera oración. Según la Ley 100 de 1993 y la Ley 50 de 1990, hay derechos. Última oración.")
    verify(a, [LEY_100])
    assert a.respuesta == "Primera oración. Última oración."
    assert not citas_sin_respaldo(a, [LEY_100])


def test_campo_que_queda_vacio_se_rellena():
    """Si el verificador vacía un campo obligatorio, se rellena con la norma del mejor pasaje."""
    a = _semi("La Ley 50 de 1990 lo regula.", referencia="Ley 50 de 1990, artículo 2")
    trace = Trace(question_id=1)
    verify(a, [LEY_100], question=Question(id=1, formato="semi_open", pregunta="¿Qué objeto tiene el sistema?"),
           trace=trace)
    assert a.referencia_legal == "Ley 100 de 1993, artículo 1"
    assert a.respuesta.startswith("Conforme a lo dispuesto en Ley 100 de 1993, artículo 1:")
    assert set(trace.filled_fields) == {"respuesta", "referencia_legal"}
    assert not citas_sin_respaldo(a, [LEY_100])


def test_justificacion_cerrada_vacia_se_rellena_con_la_letra_elegida():
    q = Question(id=2, formato="multiple_choice", pregunta="¿Objeto del sistema?",
                 opciones={"A": "x", "B": "garantizar derechos de seguridad social", "C": "y", "D": "z"})
    a = Answer(id=2, formato="multiple_choice", respuesta_correcta="B",
               justificacion="Lo dice la Ley 50 de 1990, artículo 3.",
               descarte_opciones={"A": "no", "C": "no", "D": "no"})
    verify(a, [LEY_100], question=q)
    assert a.respuesta_correcta == "B"
    assert a.justificacion == "La opción B se ajusta a lo dispuesto en Ley 100 de 1993, artículo 1."


def test_falso_positivo_constitucion_de_la_sociedad():
    """"constitución de la sociedad" no es la Carta: se reescribe si la Constitución no está en los pasajes."""
    texto = "La constitución de la sociedad exige escritura pública, según el Código de Comercio, artículo 110."
    assert ("constitucion", None, None, None) in extract(texto)  # así lo cuenta el evaluador
    a = _semi(texto, referencia="Código de Comercio, artículo 110")
    verify(a, [COMERCIO])
    assert a.respuesta == texto.replace("constitución", "conformación")
    assert not citas_sin_respaldo(a, [COMERCIO])
    # Con la Constitución en la evidencia no hay nada que corregir.
    b = _semi(texto, referencia="Código de Comercio, artículo 110")
    assert verify(b, [COMERCIO, CONSTITUCION]) == Verdict.OK
    assert b.respuesta == texto


def test_constitucion_con_mayuscula_sin_respaldo_se_elimina():
    a = _semi("La Ley 100 de 1993, artículo 1, fija el objeto. La Constitución Política protege el trabajo.")
    verify(a, [LEY_100])
    assert a.respuesta == "La Ley 100 de 1993, artículo 1, fija el objeto."


def test_no_corta_citas_en_abreviaturas():
    """"Art. 5" y "Decreto No. 1072" no se parten en dos oraciones."""
    decreto = _pasaje("Decreto 1072 de 2015", "2.2.1", "Reglamenta el sector trabajo.")
    a = _semi("El Art. 5 del Decreto No. 1072 de 2015 regula la materia. La Ley 50 de 1990 no aplica.",
              referencia="Decreto 1072 de 2015")
    verify(a, [decreto])
    assert a.respuesta == "El Art. 5 del Decreto No. 1072 de 2015 regula la materia."


def test_referencia_legal_cita_los_pasajes_entregados():
    """referencia_legal suma las normas de los pasajes que el LLM no citó, agrupando artículos."""
    from src.generation.respaldo import completar_referencia

    ec42 = _pasaje("Estatuto del Consumidor", "42", "Cláusulas abusivas.", 3)
    ec43 = _pasaje("Estatuto del Consumidor", "43", "Cláusulas abusivas ineficaces.", 4)
    sentencia = _pasaje("Sentencia C-145 de 2018", None, "Consideraciones.", 5)
    andina = _pasaje("Decisión Andina 345 de 1993", "1", "Objeto.", 6)
    pasajes = [LEY_100, ec42, sentencia, ec43, andina]
    a = _semi("Respuesta.", referencia="Ley 100 de 1993, artículo 1")
    agregadas = completar_referencia(a, pasajes)
    assert agregadas == ["Estatuto del Consumidor, artículos 42 y 43", "Sentencia C-145 de 2018",
                         "Decisión Andina 345 de 1993, artículo 1"]
    assert a.referencia_legal == ("Ley 100 de 1993, artículo 1; Estatuto del Consumidor, artículos 42 y 43; "
                                  "Sentencia C-145 de 2018; Decisión Andina 345 de 1993, artículo 1")
    assert {("estatuto_consumidor", None, None, "42"), ("estatuto_consumidor", None, None, "43"),
            ("jurisprudencia", "C-145", "2018", None)} <= extract(a.referencia_legal)
    assert not citas_sin_respaldo(a, pasajes)
    assert completar_referencia(a, pasajes) == []  # idempotente
    assert completar_referencia(Answer(id=1, formato="semi_open", abstencion=True), pasajes) == []
    assert completar_referencia(_semi("R."), pasajes, fuentes=0) == []
    b = _semi("R.", referencia="Ley 100 de 1993, artículo 1")
    assert completar_referencia(b, pasajes, fuentes=1) == ["Estatuto del Consumidor, artículos 42 y 43"]


def test_cerrada_agrega_fundamento_normativo_a_la_justificacion():
    from src.generation.respaldo import completar_referencia

    mc = Answer(id=1, formato="multiple_choice", respuesta_correcta="B",
                justificacion="La opción B garantiza derechos.", descarte_opciones={})
    assert completar_referencia(mc, [LEY_100, COMERCIO]) == ["Ley 100 de 1993, artículo 1",
                                                            "Código de Comercio, artículo 110"]
    assert mc.justificacion == ("La opción B garantiza derechos. Fundamento normativo: "
                                "Ley 100 de 1993, artículo 1; Código de Comercio, artículo 110.")
    assert not citas_sin_respaldo(mc, [LEY_100, COMERCIO])
    assert completar_referencia(mc, [LEY_100, COMERCIO]) == []  # idempotente


def test_menciones_por_frecuencia_quedan_respaldadas():
    """Las normas citadas dentro de los pasajes se agregan de la más a la menos mencionada."""
    from src.generation.respaldo import completar_referencia, cuerpos_mencionados

    s1 = _pasaje("Sentencia C-614 de 2009", None, "Viola el artículo 25 de la Constitución Política y la Ley 79 de 1988.")
    s2 = _pasaje("Sentencia C-614 de 2009", None, "La Constitución Política protege el trabajo.", 1)
    assert cuerpos_mencionados([s1, s2])[:2] == [("constitucion", None, None), ("jurisprudencia", "C-614", "2009")]
    a = _semi("R.", referencia="Sentencia C-614 de 2009")
    assert completar_referencia(a, [s1, s2], fuentes=5, menciones=1) == ["Constitución Política de Colombia"]
    assert completar_referencia(a, [s1, s2], fuentes=5, menciones=5) == ["Ley 79 de 1988"]
    assert not citas_sin_respaldo(a, [s1, s2])


def test_nombre_cuerpo_hace_ida_y_vuelta_con_el_extractor():
    from src.generation.respaldo import nombre_cuerpo
    from src.verification.citations import bodies

    for c in [("ley", "1581", "2012"), ("decreto", "663", "1993"), ("jurisprudencia", "SU-16", "2020"),
              ("constitucion", None, None), ("codigo_sustantivo_trabajo", None, None),
              ("estatuto_consumidor", None, None), ("acto_legislativo", "1", "2005")]:
        nombre = nombre_cuerpo(c)
        assert nombre and bodies(extract(nombre)) == {c}, c


def test_abierta_agrega_al_marco_normativo():
    from src.generation.respaldo import completar_referencia

    ab = Answer(id=1, formato="open_ended", marco_normativo="Ley 100 de 1993, artículo 1.", analisis="a",
                jurisprudencia="j", conclusion="c")
    assert completar_referencia(ab, [LEY_100, COMERCIO], fuentes=2) == ["Código de Comercio, artículo 110"]
    assert ab.marco_normativo == "Ley 100 de 1993, artículo 1; Código de Comercio, artículo 110."


def test_evidencia_insuficiente():
    assert verify(_semi("algo"), []) == Verdict.EVIDENCIA_INSUFICIENTE
    vacia = Answer(id=1, formato="semi_open", respuesta="", referencia_legal="")
    assert verify(vacia, [LEY_100]) == Verdict.EVIDENCIA_INSUFICIENTE


def _pipeline() -> BaselinePipeline:
    return BaselinePipeline(Stages(None, None, None, None, None), load_config("configs/baseline.yaml"))


def test_abstencion_emite_llaves_vacias_y_conserva_pasajes():
    q = Question(id=3, formato="open_ended", pregunta="caso")
    a = Answer(id=3, formato="open_ended", analisis="", conclusion="")
    out = _pipeline().finalize(q, a, Verdict.EVIDENCIA_INSUFICIENTE, [LEY_100], Trace(question_id=3)).to_submission()
    assert out["abstencion"] is True
    assert {k: out[k] for k in ("marco_normativo", "analisis", "jurisprudencia", "conclusion")} == \
        dict.fromkeys(("marco_normativo", "analisis", "jurisprudencia", "conclusion"), "")
    assert [p["doc_id"] for p in out["pasajes_recuperados"]] == [LEY_100.doc_id]


def test_cerradas_nunca_se_abstienen():
    q = Question(id=4, formato="multiple_choice", pregunta="p", opciones=dict.fromkeys("ABCD", "x"))
    a = Answer(id=4, formato="multiple_choice", respuesta_correcta="C", justificacion="j",
               descarte_opciones={"A": "a", "B": "b", "D": "d"})
    out = _pipeline().finalize(q, a, Verdict.EVIDENCIA_INSUFICIENTE, [LEY_100], Trace(question_id=4))
    assert out.abstencion is False and out.respuesta_correcta == "C"


def test_evidencia_marca_lo_que_ya_no_rige():
    """El prompt marca derogados e inexequibles junto a la cita; el texto del pasaje no cambia."""
    from dataclasses import replace

    from src.generation.answer import formatear_evidencia

    vigente = _pasaje("Ley 2010 de 2019", "1", "Texto.", 1)
    inexequible = replace(_pasaje("Ley 1943 de 2018", "1", "Texto.", 2), vigencia="inexequible")
    derogado = replace(_pasaje("Ley 640 de 2001", "1", "Texto.", 3), vigencia="derogado")
    evidencia = formatear_evidencia([vigente, inexequible, derogado])
    assert "[1] Ley 2010 de 2019, artículo 1\n" in evidencia
    assert "[2] Ley 1943 de 2018, artículo 1 [INEXEQUIBLE]\nLey 1943 de 2018. ARTÍCULO 1. Texto." in evidencia
    assert "[3] Ley 640 de 2001, artículo 1 [DEROGADO]\n" in evidencia


def test_nota_de_vigencia_solo_si_hay_pasajes_marcados():
    """La instrucción sobre [DEROGADO] solo entra al prompt cuando algún pasaje lleva la marca."""
    from dataclasses import replace

    from src.generation.answer import NOTA_VIGENCIA, construir_prompt

    q = Question(id=1, formato="semi_open", pregunta="¿Qué dice la ley?")
    assert NOTA_VIGENCIA not in construir_prompt(q, [LEY_100])
    assert NOTA_VIGENCIA in construir_prompt(q, [LEY_100, replace(COMERCIO, vigencia="derogado")])
