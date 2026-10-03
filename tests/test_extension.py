"""generation/extension.py: extensión mínima del enunciado con texto literal de los pasajes."""
from src.common.texto import n_palabras, oraciones
from src.common.types import Answer, Passage, Question
from src.generation.extension import Extension, formatear

ART = ("Código Civil. ARTICULO 1946. El contrato de compraventa podrá rescindirse por lesión enorme. "
       "El vendedor sufre lesión enorme cuando el precio que recibe es inferior a la mitad del justo precio. "
       "El justo precio se refiere al tiempo del contrato y a la cosa vendida.")
P = Passage(doc_id="codigo_civil", chunk_id=1, norma="Código Civil", articulo="1946", texto=ART)


class ModeloFalso:
    def predict(self, pares, batch_size=8, show_progress_bar=False):
        return [0.9 if "lesión" in f else 0.2 for _, f in pares]


def _ext():
    return Extension(type("R", (), {"modelo": ModeloFalso(), "batch_size": 8})(), {})


def test_completa_semiabierta_hasta_tres_oraciones_con_texto_literal():
    a = Answer(id=1, formato="semi_open", respuesta="Procede la rescisión por lesión enorme",
               referencia_legal="Código Civil, artículo 1946")
    assert _ext().completar(Question(id=1, formato="semi_open", pregunta="¿Cuándo hay lesión enorme?"), a, [P])
    assert len(oraciones(a.respuesta)) == 3 and n_palabras(a.respuesta) <= 150
    assert a.respuesta.startswith("Procede la rescisión por lesión enorme.")   # lo del LLM queda intacto
    assert "El Código Civil, artículo 1946, dispone: «" in a.respuesta


def test_no_toca_lo_que_ya_cumple_ni_las_vacias_ni_las_cerradas():
    q = Question(id=1, formato="semi_open", pregunta="p")
    llena = Answer(id=1, formato="semi_open", respuesta="Uno es así. Dos es así. Tres es así.")
    vacia = Answer(id=1, formato="semi_open", respuesta="")
    assert not _ext().completar(q, llena, [P]) and not _ext().completar(q, vacia, [P])
    cerrada = Answer(id=2, formato="multiple_choice", justificacion="Corta.")
    assert not _ext().completar(Question(id=2, formato="multiple_choice", pregunta="p"), cerrada, [P])


def test_analisis_hasta_cinco_y_formato_de_cita():
    a = Answer(id=3, formato="open_ended", marco_normativo="Código Civil, artículo 1946",
               analisis="Hubo lesión enorme. El precio fue bajo.")
    otro = Passage(doc_id="ley_1_2000", chunk_id=2, norma="Ley 1 de 2000", articulo="2",
                   texto="Ley 1 de 2000. ARTICULO 2. La acción rescisoria por lesión enorme expira en cuatro años. "
                         "El término se cuenta desde la fecha del contrato de compraventa.")
    _ext().completar(Question(id=3, formato="open_ended", pregunta="¿Hubo lesión enorme?"), a, [P, otro])
    assert len(oraciones(a.analisis)) == 5
    assert formatear(otro, "Texto.") == "La Ley 1 de 2000, artículo 2, dispone: «Texto»."
