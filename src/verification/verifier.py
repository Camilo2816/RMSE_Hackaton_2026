"""Verificador de citas: el código decide, sin volver a llamar al LLM.

El respaldo se calcula igual que scripts/evaluate.py: citas extraídas con
citations.extract del answer_text oficial, comparadas por cuerpo normativo
(tipo, número, año) contra las de los 10 primeros pasajes.

1. Sin pasajes, o texto libre con la respuesta principal vacía →
   EVIDENCIA_INSUFICIENTE (la abstención la decide abstention.decide).
2. Falsos positivos del extractor ("constitución de la sociedad", "et al.")
   se reescriben si su cuerpo no está respaldado, en vez de perder la oración.
3. Toda oración con al menos una cita sin respaldo se elimina, también las
   mixtas (una cita respaldada y otra no).
4. Los campos obligatorios que quedan vacíos se rellenan sin LLM con texto
   armado desde los pasajes (generation/respaldo.py), respaldado por construcción.
5. Aserción final sobre el texto unido, como lo lee el evaluador: cero citas
   sin respaldo. Si algo cruza oraciones o campos, se vacía el campo y se
   rellena; como último recurso se vacían y rellenan todos los campos citables.
"""
from __future__ import annotations

import re
from typing import Optional

from src.common.texto import oraciones, unir
from src.common.types import Answer, Passage, Question, Trace, Verdict
from src.generation.respaldo import rellenar
from src.verification.citations import bodies, extract, respaldo_cuerpos, sin_respaldo

CAMPOS_CITABLES = {  # los mismos que junta evaluate.answer_text
    "multiple_choice": ("justificacion",),
    "semi_open": ("respuesta", "referencia_legal"),
    "open_ended": ("marco_normativo", "analisis", "jurisprudencia", "conclusion"),
}

# Campos cuya ausencia en la salida del LLM significa "sin fundamento" (texto libre).
CAMPOS_PRINCIPALES = {
    "semi_open": ("respuesta",),
    "open_ended": ("analisis", "conclusion"),
}

# (cuerpo, patrón, reemplazo): usos que el extractor oficial toma por cita sin serlo.
_FALSOS_POSITIVOS = [
    # Solo en minúscula: "Constitución" con mayúscula sí nombra la Carta y se trata como cita.
    (("constitucion", None, None), re.compile(r"\bconstituci([oó])n\b(?!\s+(?:pol[ií]tica|nacional))"),
     lambda m: f"conformaci{m.group(1)}n"),
    (("estatuto_tributario", None, None), re.compile(r"\bet\s+al\.?", re.IGNORECASE), lambda m: "y otros"),
]


def _dict_texto(answer: Answer) -> dict:
    """Lo mínimo que evaluate.answer_text necesita."""
    d = {"formato": answer.formato}
    for campo in CAMPOS_CITABLES[answer.formato]:
        d[campo] = getattr(answer, campo)
    return d


def citas_sin_respaldo(answer: Answer, passages: list[Passage]) -> set[tuple]:
    """Cuerpos citados en la respuesta y ausentes de los 10 pasajes (igual que el evaluador)."""
    return sin_respaldo(_dict_texto(answer), passages)


def _reescribir_falsos_positivos(texto: str, respaldo: set[tuple]) -> str:
    for cuerpo, patron, reemplazo in _FALSOS_POSITIVOS:
        if cuerpo not in respaldo:
            texto = patron.sub(reemplazo, texto)
    return texto


def filtrar_oraciones(texto: str, respaldo: set[tuple]) -> tuple[str, set[tuple]]:
    """Quita toda oración que cite al menos un cuerpo sin respaldo. Devuelve (texto, cuerpos quitados)."""
    conservadas: list[str] = []
    quitados: set[tuple] = set()
    for o in oraciones(texto):
        malos = bodies(extract(o)) - respaldo
        if malos:
            quitados |= malos
            continue
        conservadas.append(o)
    return unir(conservadas), quitados


def respuesta_vacia(answer: Answer) -> bool:
    """Texto libre: el LLM no dio la respuesta principal (el prompt lo pide si no hay fundamento)."""
    campos = CAMPOS_PRINCIPALES.get(answer.formato)
    return bool(campos) and all(not getattr(answer, c) for c in campos)


def verify(answer: Answer, passages: list[Passage], drop_unsupported: bool = True,
           question: Optional[Question] = None, trace: Optional[Trace] = None) -> Verdict:
    """Modifica `answer` en sitio (elimina citas sin respaldo, rellena campos) y devuelve el veredicto."""
    if not passages:
        return Verdict.EVIDENCIA_INSUFICIENTE
    if respuesta_vacia(answer):
        return Verdict.EVIDENCIA_INSUFICIENTE

    respaldo = respaldo_cuerpos(passages)
    quitados: set[tuple] = set()
    if not drop_unsupported:
        return Verdict.CITA_SIN_RESPALDO if citas_sin_respaldo(answer, passages) else Verdict.OK

    for campo in CAMPOS_CITABLES[answer.formato]:
        texto = getattr(answer, campo)
        if not texto:
            continue
        texto = _reescribir_falsos_positivos(texto, respaldo)
        texto, q = filtrar_oraciones(texto, respaldo)
        quitados |= q
        setattr(answer, campo, texto)

    q = question or Question(id=answer.id, formato=answer.formato, pregunta="")
    rellenados = rellenar(answer, q, passages)

    # Citas que solo aparecen al unir oraciones o campos (como hace answer_text).
    restantes = citas_sin_respaldo(answer, passages)
    if restantes:
        quitados |= restantes
        for campo in CAMPOS_CITABLES[answer.formato]:
            if bodies(extract(getattr(answer, campo))) & restantes:
                setattr(answer, campo, "")
        rellenados += rellenar(answer, q, passages)
    if citas_sin_respaldo(answer, passages):
        for campo in CAMPOS_CITABLES[answer.formato]:
            setattr(answer, campo, "")
        rellenados += rellenar(answer, q, passages)
    assert not citas_sin_respaldo(answer, passages), (answer.id, citas_sin_respaldo(answer, passages))

    if trace is not None:
        trace.dropped_citations.extend(sorted(list(c) for c in quitados))
        trace.filled_fields.extend(rellenados)
    return Verdict.CITA_SIN_RESPALDO if quitados else Verdict.OK

