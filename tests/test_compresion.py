"""generation/compresion.py: vista comprimida de sentencias para el LLM (sin modelo real)."""
from src.common.types import Passage, Question
from src.generation.compresion import Compresor, mmr, partir

TEXTO = ("Sentencia T-256 de 2025, Corte Constitucional. Consideraciones > Problema jurídico. "
         "La Sala debe resolver si se vulneró el derecho a la educación. El colegio expulsó a la menor. "
         "Los padres presentaron tutela.\nEl juez de primera instancia negó el amparo. "
         "La Corte reitera su jurisprudencia sobre debido proceso disciplinario escolar.")


class ModeloFalso:
    """Puntúa más alto las oraciones que mencionan 'educación' o 'debido proceso'."""

    def predict(self, pares, batch_size=8, show_progress_bar=False):
        return [0.9 if ("educación" in f or "debido proceso" in f) else 0.1 for _, f in pares]


def test_partir_conserva_el_encabezado_citable():
    cabeza, frases = partir(TEXTO)
    assert cabeza.startswith("Sentencia T-256 de 2025, Corte Constitucional. ")
    assert frases[0].startswith("La Sala debe resolver") and len(frases) == 5


def test_mmr_respeta_presupuesto_y_orden_del_texto():
    frases = ["a b c", "d e f", "a b c d"]
    assert mmr(frases, [0.2, 1.0, 0.9], 6, 0.8) == [1]          # solo cabe una
    assert mmr(frases, [0.2, 1.0, 0.9], 100, 0.8) == [0, 1, 2]   # cabe todo, en orden del texto
    assert mmr(["x" * 50], [1.0], 10, 0.8) == [0]                # al menos una aunque no quepa


def test_vista_solo_comprime_sentencias_largas_y_conserva_el_inicio():
    c = Compresor(type("R", (), {"modelo": ModeloFalso(), "batch_size": 8})(),
                  {"compresion": {"presupuesto": 0.6, "min_caracteres": 100}})
    q = Question(id=1, formato="semi_open", pregunta="¿Se vulneró el derecho a la educación?")
    sent = Passage(doc_id="sentencia_t_256_2025", chunk_id=1, norma="Sentencia T-256 de 2025", articulo=None, texto=TEXTO)
    ley = Passage(doc_id="ley_115_1994", chunk_id=2, norma="Ley 115 de 1994", articulo="1", texto="Ley 115 de 1994. " + "x " * 200)
    v = c.vista(q, [sent, ley])
    assert v[1] is ley                                            # las normas van completas
    assert v[0].texto.startswith("Sentencia T-256 de 2025, Corte Constitucional. ")
    assert "educación" in v[0].texto and len(v[0].texto) < len(TEXTO)
    assert (v[0].doc_id, v[0].chunk_id) == (sent.doc_id, sent.chunk_id)
