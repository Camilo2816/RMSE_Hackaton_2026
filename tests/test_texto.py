"""src/common/texto.py: oraciones, topes, abreviaturas y meta-frases."""
from src.common.texto import acotar, expandir_abreviaturas, n_palabras, oraciones, quitar_meta_frases
from src.verification.citations import bodies, extract


def test_oraciones_no_corta_en_abreviaturas():
    t = "Lo dice el Art. 5 de la Ley 100 de 1993. Y el Decreto No. 1072 de 2015 también. Fin."
    assert oraciones(t) == ["Lo dice el Art. 5 de la Ley 100 de 1993.",
                            "Y el Decreto No. 1072 de 2015 también.", "Fin."]


def test_acotar_respeta_oraciones_y_palabras():
    t = " ".join(f"Oración número {i} con cinco palabras." for i in range(10))
    assert len(oraciones(acotar(t, max_oraciones=5))) == 5
    assert n_palabras(acotar(t, max_palabras=12)) == 12


def test_abreviaturas_mismo_cuerpo_normativo():
    """La expansión nunca cambia el cuerpo citado; "C.G.P." (que el evaluador no reconoce) pasa a contar."""
    t = "Según el CST, artículo 64, y el C.G.P., artículo 25."
    expandido = expandir_abreviaturas(t)
    assert "Código Sustantivo del Trabajo" in expandido and "Código General del Proceso" in expandido
    assert bodies(extract(t)) == {("codigo_sustantivo_trabajo", None, None)}
    assert bodies(extract(expandido)) == {("codigo_sustantivo_trabajo", None, None),
                                          ("codigo_general_proceso", None, None)}


def test_quita_meta_frases():
    assert quitar_meta_frases("Según la evidencia recuperada, el plazo es de 4 meses [2].") == \
        "El plazo es de 4 meses."
    assert quitar_meta_frases("El plazo es de 4 meses, como se menciona en el pasaje 3.") == \
        "El plazo es de 4 meses."
