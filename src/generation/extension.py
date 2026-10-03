"""Extensión mínima del enunciado (paso 3) con texto literal de la evidencia. Sin LLM.

El enunciado exige semiabiertas de 3 a 5 oraciones (≤ 150 palabras) y análisis de 5 a 8,
"dentro de los límites de extensión indicados". Llama-3.1-8B se queda corto aunque el
prompt lo pida (sample_50: 20/30 semiabiertas y 5/5 análisis por debajo del mínimo), y
pedirle más oraciones (generation.estructura) agrega afirmaciones inventadas o de relleno.

Cuando falta extensión, sin otra llamada al LLM y sin tocar lo que escribió:
1. parte en "; " (no cambia el contenido) y asegura el punto final;
2. agrega oraciones literales de los pasajes entregados —primero los de las normas que la
   respuesta ya cita, después los demás en su orden—, elegidas por el cross-encoder del
   reranker frente a la pregunta y sin repetir lo dicho:
   «El Código Civil, artículo 1954, dispone: "…"».
Todo lo agregado sale de un pasaje de los 10 entregados: no puede crear citas sin respaldo.
Simulación sobre sample_50 (C sin A): 50/50 cumplen; RAGAS 14,95 → 13,66 (media de dos
juicios), la misma pérdida que cumplir vía prompt (13,20 / 13,60) sin latencia extra.
"""
from __future__ import annotations

import re

from src.common.config import Config
from src.common.texto import n_palabras, oraciones
from src.common.types import Answer, Passage, Question
from src.generation.respaldo import cita, cuerpo
from src.index.tokenizar import tokenizar
from src.verification.citations import bodies, extract

# (campo, mínimo de oraciones, máximo de palabras) por formato, del enunciado (paso 3).
MINIMOS = {"semi_open": ("respuesta", 3, 150), "open_ended": ("analisis", 5, None)}
FEMENINOS = ("Ley", "Constitución", "Resolución", "Circular", "Sentencia", "Decisión", "Directiva")


def _jaccard(a: str, b: str) -> float:
    x, y = set(tokenizar(a)), set(tokenizar(b))
    return len(x & y) / len(x | y) if x and y else 0.0


def _partir_punto_y_coma(texto: str) -> str:
    texto = re.sub(r";\s+(\w)", lambda m: ". " + m.group(1).upper(), texto).rstrip()
    if texto and texto[-1] not in ".!?»\"":
        texto += "."  # sin punto final, lo agregado se uniría a la última oración
    return texto


def formatear(p: Passage, frase: str) -> str:
    frase = frase.strip().rstrip(".;:")
    c = cita(p)
    articulo = "La" if c.startswith(FEMENINOS) else "El"
    verbo = "señala" if p.doc_id.startswith("sentencia_") else "dispone"
    return f"{articulo} {c}, {verbo}: «{frase}»." if p.articulo else f"{articulo} {c} {verbo}: «{frase}»."


class Extension:
    def __init__(self, reranker, cfg: Config) -> None:
        p = cfg.get("verification", {}).get("extension", {})
        self.largo = (p.get("min_palabras_oracion", 5), p.get("max_palabras_oracion", 60))
        self.modelo = reranker.modelo
        self.batch_size = reranker.batch_size

    def completar(self, question: Question, answer: Answer, passages: list[Passage]) -> bool:
        """Lleva el campo del formato al mínimo de oraciones del enunciado. True si cambió."""
        if question.formato not in MINIMOS or answer.abstencion or not passages:
            return False
        campo, minimo, max_palabras = MINIMOS[question.formato]
        texto = getattr(answer, campo) or ""
        if not texto.strip() or len(oraciones(texto)) >= minimo:
            return False  # vacía: la decide la abstención, no se rellena
        citado = (f"{answer.respuesta} {answer.referencia_legal}" if question.formato == "semi_open"
                  else f"{answer.marco_normativo} {answer.analisis}")
        nuevo = self._completar(_partir_punto_y_coma(texto), minimo, max_palabras,
                                question.pregunta, passages, bodies(extract(citado)))
        if nuevo == texto:
            return False
        setattr(answer, campo, nuevo)
        return True

    def _completar(self, texto: str, minimo: int, max_palabras, pregunta: str,
                   passages: list[Passage], prioridad: set) -> str:
        if len(oraciones(texto)) >= minimo:
            return texto
        primero = [p for p in passages if bodies(extract(p.norma)) & prioridad]
        orden = primero + [p for p in passages if p not in primero]
        dichas = oraciones(texto)
        candidatas = []
        for rango, p in enumerate(orden):
            for f in oraciones(cuerpo(p)):
                if self.largo[0] <= n_palabras(f) <= self.largo[1] and not any(_jaccard(f, o) > 0.5 for o in dichas):
                    candidatas.append((p in primero, rango, f, p))
        if not candidatas:
            return texto
        puntajes = self.modelo.predict([(pregunta, c[2]) for c in candidatas], batch_size=self.batch_size,
                                       show_progress_bar=False)
        # Primero las de las normas que la respuesta cita; dentro de cada grupo, por relevancia.
        # Redondeado: una misma oración en dos pasajes (Ley 1819 de 2016, art. 61 y E.T., art. 105
        # en la 142) empata, y el ruido de fp16 según el tamaño de lote invertía el empate.
        ordenadas = sorted(zip(candidatas, puntajes),
                           key=lambda x: (not x[0][0], -round(float(x[1]), 3), x[0][1], x[0][2]))
        agregadas: list[str] = []
        for (_, _, f, p), _ in ordenadas:
            if len(dichas) + len(agregadas) >= minimo:
                break
            nueva = formatear(p, f)
            if any(_jaccard(f, a) > 0.5 for a in agregadas):
                continue
            if max_palabras and n_palabras(texto) + sum(map(n_palabras, agregadas)) + n_palabras(nueva) > max_palabras:
                continue
            agregadas.append(nueva)
        return " ".join([texto, *agregadas]) if agregadas else texto
