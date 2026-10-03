"""Generación de la respuesta en el JSON de su formato (enunciado, paso 3).

Prompts en src/generation/prompts/answer/<formato>.md. El LLM recibe como
máximo los 10 pasajes fusionados, que son los mismos pasajes_recuperados. La
pregunta (y las opciones) va antes y después de la evidencia: con 4.000+
tokens de evidencia en medio, repetirla al final la deja cerca de la salida.

Tras la llamada se normaliza la salida sin LLM: abreviaturas de códigos a su
nombre completo, sin meta-frases ("según la evidencia…"), topes de oraciones y
palabras por formato, y descarte_opciones con exactamente las otras tres letras.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from src.common.texto import acotar, limpiar
from src.common.types import Answer, Formato, Passage, Question
from src.generation.llm import LLMClient
from src.generation.respaldo import JURISPRUDENCIA_VACIA, cita

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts" / "answer"

LETRAS = ("A", "B", "C", "D")
DESCARTE_POR_DEFECTO = "No corresponde a la regla aplicable."

# El orden de las propiedades es el orden de generación: en cerradas la
# justificación va antes de la letra, para que la elección siga al razonamiento.
_SCHEMAS: dict[Formato, dict] = {
    "multiple_choice": {
        "type": "object",
        "properties": {
            "justificacion": {"type": "string"},
            "respuesta_correcta": {"type": "string", "enum": list(LETRAS)},
            "descarte_opciones": {
                "type": "object",
                "properties": {l: {"type": "string"} for l in LETRAS},
                "additionalProperties": False,
            },
        },
        "required": ["justificacion", "respuesta_correcta", "descarte_opciones"],
    },
    "semi_open": {
        "type": "object",
        "properties": {
            "respuesta": {"type": "string"},
            "palabras_clave": {"type": "array", "items": {"type": "string"}},
            "referencia_legal": {"type": "string"},
        },
        "required": ["respuesta", "palabras_clave", "referencia_legal"],
    },
    "open_ended": {
        "type": "object",
        "properties": {
            "marco_normativo": {"type": "string"},
            "analisis": {"type": "string"},
            "jurisprudencia": {"type": "string"},
            "conclusion": {"type": "string"},
        },
        "required": ["marco_normativo", "analisis", "jurisprudencia", "conclusion"],
    },
}

# generation.estructura = "partes": el enunciado exige semiabiertas de 3–5 oraciones y análisis de
# 5–8, pero Llama-3.1-8B responde 1–2 y 3–4 aunque el prompt lo pida (sample_50: 20/30 y 5/5 por
# debajo). Guided JSON impone la forma: tres oraciones con papel fijo que el código une en
# "respuesta", y un análisis de exactamente cinco. Sin minLength: con él el modelo rellena basura.
# "partes_razonadas" antepone "razonamiento" (no se entrega ni va al juez): la respuesta se
# escribe después de fijar qué pasaje responde y qué dice, en la misma llamada.
_PARTES_SEMI = ("respuesta_directa", "fundamento", "alcance")
RAZONAMIENTO = ('- "razonamiento" (va primero y no se muestra): en dos o tres oraciones, qué pasaje\n'
                '  responde la pregunta, qué dice exactamente sobre lo preguntado y qué respuesta se\n'
                '  sigue de él.\n')
_SCHEMAS_PARTES: dict[Formato, dict] = {
    "semi_open": {
        "type": "object",
        "properties": {
            **{c: {"type": "string"} for c in _PARTES_SEMI},
            "palabras_clave": {"type": "array", "items": {"type": "string"}},
            "referencia_legal": {"type": "string"},
        },
        "required": [*_PARTES_SEMI, "palabras_clave", "referencia_legal"],
    },
    "open_ended": {
        "type": "object",
        "properties": {
            "marco_normativo": {"type": "string"},
            "analisis": {"type": "array", "items": {"type": "string"}, "minItems": 5, "maxItems": 5},
            "jurisprudencia": {"type": "string"},
            "conclusion": {"type": "string"},
        },
        "required": ["marco_normativo", "analisis", "jurisprudencia", "conclusion"],
    },
}

# Topes del enunciado (paso 3): semiabiertas 3–5 oraciones y ≤ 150 palabras; análisis 5–8 oraciones.
_TOPES: dict[str, tuple[Optional[int], Optional[int]]] = {
    "justificacion": (4, None),
    "respuesta": (5, 150),
    "analisis": (8, None),
    "conclusion": (3, None),
}


def output_schema(formato: Formato, estructura: Optional[str] = None) -> dict:
    """JSON schema para guided JSON: las claves oficiales del formato o, con `estructura`, sus partes."""
    if not estructura or formato not in _SCHEMAS_PARTES:
        return _SCHEMAS[formato]
    schema = _SCHEMAS_PARTES[formato]
    if estructura == "partes_razonadas":  # el orden de las propiedades es el de generación
        schema = {**schema, "properties": {"razonamiento": {"type": "string"}, **schema["properties"]},
                  "required": ["razonamiento", *schema["required"]]}
    return schema


def _cargar_prompt(formato: Formato, estructura: Optional[str] = None) -> str:
    nombre = f"{formato}_partes" if estructura and formato in _SCHEMAS_PARTES else formato
    return (PROMPTS_DIR / f"{nombre}.md").read_text(encoding="utf-8")


# Marca visible de los fragmentos que ya no rigen (vigencia del índice); solo va en el
# prompt: el texto de pasajes_recuperados sigue siendo literal.
MARCA_VIGENCIA = {"derogado": " [DEROGADO]", "inexequible": " [INEXEQUIBLE]"}
# Instrucción que acompaña a la marca. Solo entra si algún pasaje la lleva: como línea
# fija cambiaba la letra de cerradas sin pasajes marcados (308 y 647 de sample_50).
NOTA_VIGENCIA = ("- Los pasajes marcados [DEROGADO] o [INEXEQUIBLE] ya no rigen: prefiere la\n"
                 "  norma vigente que regule lo mismo. Usa la no vigente solo si la pregunta se\n"
                 "  refiere a ella o al régimen anterior, y di que fue derogada o declarada inexequible.\n")


def formatear_evidencia(passages: list[Passage]) -> str:
    """Pasajes numerados con su cita completa (y su marca de vigencia) en la primera línea."""
    if not passages:
        return "(sin pasajes recuperados)"
    return "\n\n".join(f"[{i}] {cita(p)}{MARCA_VIGENCIA.get(p.vigencia or '', '')}\n{p.texto}"
                       for i, p in enumerate(passages, start=1))


def _formatear_opciones(question: Question) -> str:
    if not question.opciones:
        return ""
    return "\n".join(f"{letra}. {texto}" for letra, texto in sorted(question.opciones.items()))


def construir_prompt(question: Question, passages: list[Passage], estructura: Optional[str] = None) -> str:
    return _cargar_prompt(question.formato, estructura).format(
        pregunta=question.pregunta.strip(),
        evidencia=formatear_evidencia(passages),
        opciones=_formatear_opciones(question),
        nota_vigencia=NOTA_VIGENCIA if any(p.vigencia in MARCA_VIGENCIA for p in passages) else "",
        razonamiento=RAZONAMIENTO if estructura == "partes_razonadas" else "",
    )


def _texto(valor) -> str:
    return valor.strip() if isinstance(valor, str) else ""


def _normalizar(campo: str, valor) -> str:
    texto = limpiar(_texto(valor))
    max_or, max_pal = _TOPES.get(campo, (None, None))
    return acotar(texto, max_or, max_pal) if (max_or or max_pal) else texto


def normalizar_descarte(descarte, elegida: Optional[str]) -> dict[str, str]:
    """Exactamente las tres letras no elegidas, en orden, cada una con una razón no vacía."""
    descarte = descarte if isinstance(descarte, dict) else {}
    out: dict[str, str] = {}
    for l in LETRAS:
        if l == elegida:
            continue
        out[l] = limpiar(_texto(descarte.get(l))) or DESCARTE_POR_DEFECTO
    return out


def a_answer(question: Question, passages: list[Passage], salida: dict) -> Answer:
    """Arma el Answer desde el JSON del LLM, ya normalizado (sin verificar citas)."""
    answer = Answer(id=question.id, formato=question.formato, pasajes_recuperados=list(passages))
    if question.formato == "multiple_choice":
        letra = salida.get("respuesta_correcta")
        answer.respuesta_correcta = letra if letra in LETRAS else None
        answer.justificacion = _normalizar("justificacion", salida.get("justificacion"))
        answer.descarte_opciones = normalizar_descarte(salida.get("descarte_opciones"), answer.respuesta_correcta)
    elif question.formato == "semi_open":
        if "respuesta_directa" in salida:  # generation.estructura: tres oraciones con papel fijo
            salida = {**salida, "respuesta": " ".join(_texto(salida.get(c)).strip() for c in _PARTES_SEMI
                                                      if _texto(salida.get(c)).strip())}
        answer.respuesta = _normalizar("respuesta", salida.get("respuesta"))
        claves = salida.get("palabras_clave") or []
        answer.palabras_clave = [c.strip() for c in claves if isinstance(c, str) and c.strip()][:6]
        answer.referencia_legal = _normalizar("referencia_legal", salida.get("referencia_legal"))
    else:  # open_ended
        if isinstance(salida.get("analisis"), list):  # generation.estructura: lista de oraciones
            salida = {**salida, "analisis": " ".join(_texto(o).strip() for o in salida["analisis"]
                                                     if _texto(o).strip())}
        for campo in ("marco_normativo", "analisis", "jurisprudencia", "conclusion"):
            setattr(answer, campo, _normalizar(campo, salida.get(campo)))
        # Sin sentencias en la evidencia el prompt pide cadena vacía, pero el campo es obligatorio.
        if not answer.jurisprudencia and (answer.analisis or answer.conclusion):
            answer.jurisprudencia = JURISPRUDENCIA_VACIA
    return answer


class AnswerGenerator:
    def __init__(self, llm: LLMClient, estructura: Optional[str] = None) -> None:
        self.llm = llm
        self.estructura = estructura  # generation.estructura: None, "partes" o "partes_razonadas"

    def generate(self, question: Question, passages: list[Passage], calls: Optional[list] = None) -> Answer:
        """Rellena el prompt del formato, llama al LLM y arma el Answer.

        No decide abstención ni filtra citas sin respaldo: eso corresponde a
        src/verification (etapa posterior en el pipeline). Si el LLM falla dos
        veces propaga LLMError; el pipeline usa entonces respaldo.respuesta_respaldo.
        """
        prompt = construir_prompt(question, passages, self.estructura)
        salida = self.llm.complete_json(prompt, output_schema(question.formato, self.estructura),
                                        question.formato, calls)
        return a_answer(question, passages, salida)
