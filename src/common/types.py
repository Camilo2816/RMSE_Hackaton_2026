"""Contratos de datos entre etapas del pipeline.

Son los únicos tipos que cruzan fronteras de módulo. Los nombres de campo de
Answer replican las llaves oficiales de schema/submission.schema.json.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Literal, Optional

Formato = Literal["multiple_choice", "semi_open", "open_ended"]

CLAVES_FORMATO: dict[str, tuple[str, ...]] = {
    "multiple_choice": ("respuesta_correcta", "justificacion", "descarte_opciones"),
    "semi_open": ("respuesta", "palabras_clave", "referencia_legal"),
    "open_ended": ("marco_normativo", "analisis", "jurisprudencia", "conclusion"),
}


@dataclass(frozen=True)
class Question:
    """Ítem de data/sample_50.jsonl o data/test_992.jsonl (sin respuesta esperada)."""

    id: int
    formato: Formato
    pregunta: str
    opciones: Optional[dict[str, str]] = None  # solo multiple_choice: {"A": ..., "D": ...}
    area: Optional[str] = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Question":
        """Toma solo los campos de entrada; legal_basis y respuestas esperadas nunca pasan."""
        return cls(id=int(d["id"]), formato=d["formato"], pregunta=d["pregunta"],
                   opciones=d.get("opciones") or None, area=d.get("area"))

    def texto_busqueda(self) -> str:
        """Pregunta más el texto de las opciones (en cerradas las opciones suelen nombrar la norma)."""
        if not self.opciones:
            return self.pregunta
        return self.pregunta + "\n" + "\n".join(self.opciones[k] for k in sorted(self.opciones))


@dataclass(frozen=True)
class Passage:
    """Fragmento recuperado. `texto` empieza con el nombre citable de la norma."""

    doc_id: str
    chunk_id: int  # fila en corpus/index/metadata.jsonl
    norma: str  # "Ley 472 de 1998"
    articulo: Optional[str]  # None en sentencias
    texto: str
    inicio: Optional[int] = None  # offsets sobre corpus/processed/<doc_id>.txt
    fin: Optional[int] = None
    score: float = 0.0
    fuente_query: Optional[str] = None  # subconsulta que lo trajo, o "lookup"
    vigencia: Optional[str] = None  # vigente | modificado | derogado | inexequible | desconocida (src/ingest/metadatos.py)

    @property
    def clave(self) -> tuple[str, int]:
        """Clave de identidad y de desempate estable en fusión y rerank."""
        return (self.doc_id, self.chunk_id)

    def to_submission(self) -> dict[str, Any]:
        """Campos del schema oficial; score como float de Python (nunca numpy ni NaN)."""
        out: dict[str, Any] = {"doc_id": self.doc_id}
        if self.inicio is not None:
            out["inicio"] = int(self.inicio)
        if self.fin is not None:
            out["fin"] = int(self.fin)
        out["texto"] = self.texto
        out["score"] = round(float(self.score), 6)
        return out

    def to_json(self) -> dict[str, Any]:
        d = asdict(self)
        d["score"] = round(float(self.score), 6)
        return d


@dataclass
class Answer:
    """Respuesta de un ítem. Solo se serializan las claves de su formato."""

    id: int
    formato: Formato
    abstencion: bool = False
    pasajes_recuperados: list[Passage] = field(default_factory=list)  # ≤ 10, los mismos que vio el LLM
    # multiple_choice
    respuesta_correcta: Optional[str] = None
    justificacion: str = ""
    descarte_opciones: dict[str, str] = field(default_factory=dict)
    # semi_open
    respuesta: str = ""
    palabras_clave: list[str] = field(default_factory=list)
    referencia_legal: str = ""
    # open_ended
    marco_normativo: str = ""
    analisis: str = ""
    jurisprudencia: str = ""
    conclusion: str = ""
    latencia_ms: Optional[int] = None

    def to_submission(self) -> dict:
        """Línea de submissions.jsonl: claves del formato + pasajes (doc_id, inicio, fin, texto, score)."""
        out: dict[str, Any] = {"id": self.id, "formato": self.formato, "abstencion": self.abstencion}
        for clave in CLAVES_FORMATO[self.formato]:
            valor = getattr(self, clave)
            out[clave] = dict(valor) if isinstance(valor, dict) else list(valor) if isinstance(valor, list) else valor
        out["pasajes_recuperados"] = [p.to_submission() for p in self.pasajes_recuperados]
        if self.latencia_ms is not None:
            out["latencia_ms"] = int(self.latencia_ms)
        return out


class Verdict(str, Enum):
    """Resultado del verificador.

    CITA_SIN_RESPALDO: se eliminaron citas; no dispara re-planeo.
    EVIDENCIA_INSUFICIENTE: dispara re-planeo (agéntico) o abstención.
    """

    OK = "ok"
    CITA_SIN_RESPALDO = "cita_sin_respaldo"
    EVIDENCIA_INSUFICIENTE = "evidencia_insuficiente"


@dataclass
class Trace:
    """Registro completo de una pregunta; una línea de traces.jsonl.

    La interfaz y la verificación en vivo leen de aquí. Los campos acumulan
    todas las iteraciones.
    """

    question_id: int
    subqueries: list[str] = field(default_factory=list)
    passages_by_query: dict[str, list[Passage]] = field(default_factory=dict)
    fused_passages: list[Passage] = field(default_factory=list)
    verdicts: list[Verdict] = field(default_factory=list)
    iterations: int = 0
    timings: dict[str, float] = field(default_factory=dict)  # segundos por etapa
    llm_calls: list[dict] = field(default_factory=list)  # por intento: tokens, done_reason, segundos o error
    fallback: Optional[str] = None  # motivo si se usó la respuesta de respaldo (LLMError)
    dropped_citations: list[list] = field(default_factory=list)  # citas sin respaldo quitadas por el verificador
    filled_fields: list[str] = field(default_factory=list)  # campos rellenados sin LLM tras verificar
    abstention_reason: Optional[str] = None  # sin_pasajes | respuesta_vacia | score_bajo
    replan_reasons: list[str] = field(default_factory=list)  # motivo de cada re-planeo (agéntico)

    def to_json(self) -> dict:
        """Serialización para traces.jsonl."""
        return {
            "question_id": self.question_id,
            "subqueries": list(self.subqueries),
            "passages_by_query": {q: [p.to_json() for p in ps] for q, ps in self.passages_by_query.items()},
            "fused_passages": [p.to_json() for p in self.fused_passages],
            "verdicts": [v.value for v in self.verdicts],
            "iterations": self.iterations,
            "timings": {k: round(v, 4) for k, v in self.timings.items()},
            "llm_calls": list(self.llm_calls),
            "fallback": self.fallback,
            "dropped_citations": [list(c) for c in self.dropped_citations],
            "filled_fields": list(self.filled_fields),
            "abstention_reason": self.abstention_reason,
            "replan_reasons": list(self.replan_reasons),
        }
