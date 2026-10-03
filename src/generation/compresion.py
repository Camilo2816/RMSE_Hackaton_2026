"""Vista comprimida de los pasajes de sentencia para el LLM (HCLeK, CIKM 2025). Sin LLM.

Las sentencias son conocimiento "práctico": largas y con mucho texto que no responde la
pregunta, mientras las normas (conocimiento "núcleo") son cortas y densas. De cada pasaje
de sentencia el LLM ve su encabezado citable y las oraciones más relevantes para la
pregunta (puntaje del cross-encoder del reranker, normalizado en el pasaje), elegidas con MMR —relevancia y
diversidad por Jaccard, λ = 0,8 como en el artículo— hasta `presupuesto` de sus
caracteres; las omitidas se marcan con "[…]". Las normas van completas.

La entrega (pasajes_recuperados) y la verificación de citas usan el pasaje completo: la
vista es un subconjunto del mismo texto, que empieza igual (nombre citable incluido).
"""
from __future__ import annotations

import dataclasses
import re

from src.common.config import Config
from src.common.types import Passage, Question
from src.index.tokenizar import tokenizar

# Encabezado de los fragmentos de sentencia (src/ingest/segmentar.py):
# "{norma}, {órgano}. {Sección}[ > {subtítulo}]. "; el subtítulo puede llevar puntos.
_ENCABEZADO = re.compile(r"^[^\n]*?, [^\n.]+\. [^\n]*?\. ")
_FRASE = re.compile(r"(?<=[.;:!?])\s+(?=[A-ZÁÉÍÓÚÑ¿¡“\"(0-9])")
OMISION = " […] "


def partir(texto: str) -> tuple[str, list[str]]:
    """(encabezado, oraciones del cuerpo en orden)."""
    m = _ENCABEZADO.match(texto)
    cabeza = m.group(0) if m else ""
    frases = [f.strip() for linea in texto[len(cabeza):].split("\n") for f in _FRASE.split(linea) if f.strip()]
    return cabeza, frases


def _jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def mmr(frases: list[str], relevancia: list[float], presupuesto: int, lam: float) -> list[int]:
    """Índices elegidos (en orden del texto) por MMR hasta agotar el presupuesto de caracteres."""
    tokens = [set(tokenizar(f)) for f in frases]
    elegidas: list[int] = []
    restante = presupuesto
    candidatas = set(range(len(frases)))
    while candidatas:
        def valor(i: int) -> tuple[float, int]:
            div = 1.0 - max((_jaccard(tokens[i], tokens[j]) for j in elegidas), default=0.0)
            return lam * relevancia[i] + (1 - lam) * div, -i  # desempate estable: la primera en el texto
        caben = [i for i in candidatas if len(frases[i]) <= restante]
        if not caben:
            if not elegidas:  # al menos la más relevante, aunque exceda el presupuesto
                elegidas.append(max(candidatas, key=valor))
            break
        i = max(caben, key=valor)
        elegidas.append(i)
        candidatas.discard(i)
        restante -= len(frases[i]) + 1
    return sorted(elegidas)


class Compresor:
    def __init__(self, reranker, cfg: Config) -> None:
        p = cfg.get("compresion", {})
        self.presupuesto = p.get("presupuesto", 0.4)
        self.min_caracteres = p.get("min_caracteres", 600)
        self.lam = p.get("lambda", 0.8)
        self.modelo = reranker.modelo
        self.batch_size = reranker.batch_size

    def vista(self, question: Question, passages: list[Passage]) -> list[Passage]:
        """Los mismos pasajes; los de sentencia largos, con solo sus oraciones relevantes."""
        query = question.texto_busqueda()
        partes: dict[int, tuple[str, list[str]]] = {}
        for k, p in enumerate(passages):
            if p.doc_id.startswith("sentencia_") and len(p.texto) >= self.min_caracteres:
                cabeza, frases = partir(p.texto)
                if cabeza and len(frases) >= 3:
                    partes[k] = (cabeza, frases)
        if not partes:
            return list(passages)
        pares = [(query, f) for _, frases in partes.values() for f in frases]
        puntajes = iter(float(s) for s in self.modelo.predict(pares, batch_size=self.batch_size,
                                                                show_progress_bar=False))
        out = list(passages)
        for k, (cabeza, frases) in partes.items():
            crudo = [next(puntajes) for _ in frases]
            # Min-max dentro del pasaje: la sigmoide del cross-encoder deja a veces todas las
            # oraciones cerca de 0 y MMR elegiría por diversidad, no por relevancia.
            lo, hi = min(crudo), max(crudo)
            rel = [(s - lo) / (hi - lo) if hi > lo else 1.0 for s in crudo]
            presupuesto = int(self.presupuesto * len(passages[k].texto)) - len(cabeza)
            elegidas = mmr(frases, rel, presupuesto, self.lam)
            cuerpo, previa = [], -1
            for i in elegidas:
                if previa >= 0 and i != previa + 1:
                    cuerpo.append(OMISION.strip())
                cuerpo.append(frases[i])
                previa = i
            if elegidas[0] > 0:
                cuerpo.insert(0, OMISION.strip())
            if elegidas[-1] < len(frases) - 1:
                cuerpo.append(OMISION.strip())
            out[k] = dataclasses.replace(passages[k], texto=cabeza + " ".join(cuerpo))
        return out
