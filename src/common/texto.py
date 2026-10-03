"""Utilidades de texto para la respuesta: oraciones, topes, abreviaturas y meta-frases.

Las usan la generación (posprocesado y respaldo) y el verificador (que elimina
oraciones completas). La división en oraciones no corta tras abreviaturas
jurídicas ("Art. 5", "No. 1072", "inc. 2"), para no partir una cita en dos.
"""
from __future__ import annotations

import re

_CORTE = re.compile(r"(?<=[.!?])\s+")
# Tokens que, al final de un trozo, indican que el punto no cierra la oración.
_ABREVIATURA = re.compile(
    r"(?:\b(?:arts?|art[ií]culos?|n[oº°]|núm|num|nums|inc|incs|lit|lits|par|parág|ord|cfr|ss|sr|sra|dr|dra|"
    r"ibíd|ibid|op|cit|pág|págs|pp|vol|cap|tít|dcto|decr|res|sent|mag|al)"
    r"|\b[A-ZÁÉÍÓÚ])\.$",
    re.IGNORECASE,
)


def oraciones(texto: str) -> list[str]:
    """Divide en oraciones sin cortar tras abreviaturas, iniciales ni números ("1.", "C.")."""
    texto = (texto or "").strip()
    if not texto:
        return []
    trozos = _CORTE.split(texto)
    out: list[str] = []
    for t in trozos:
        if out and _ABREVIATURA.search(out[-1]):
            out[-1] = f"{out[-1]} {t}"
        else:
            out.append(t)
    return [o.strip() for o in out if o.strip()]


def unir(partes: list[str]) -> str:
    return " ".join(p.strip() for p in partes if p and p.strip()).strip()


def n_palabras(texto: str) -> int:
    return len(re.findall(r"\S+", texto or ""))


def acotar(texto: str, max_oraciones: int | None = None, max_palabras: int | None = None) -> str:
    """Conserva oraciones completas desde el inicio hasta los topes (al menos la primera)."""
    out: list[str] = []
    palabras = 0
    for o in oraciones(texto):
        n = n_palabras(o)
        if out and ((max_oraciones and len(out) >= max_oraciones)
                    or (max_palabras and palabras + n > max_palabras)):
            break
        out.append(o)
        palabras += n
    return unir(out)


# Abreviaturas de códigos → nombre completo. Solo las inequívocas y en mayúsculas;
# "C.C." (cédula) y "C.P." (Constitución o Código Penal) se dejan como vienen.
# Cada nombre completo corresponde al mismo cuerpo que la abreviatura en scripts/citations.py.
_ABREVIATURAS_CODIGOS: list[tuple[re.Pattern, str]] = [
    (re.compile(p), nombre) for p, nombre in [
        (r"(?<![\w.])(?:CST|C\.S\.T\.?)(?![\w])", "Código Sustantivo del Trabajo"),
        (r"(?<![\w.])(?:CGP|C\.G\.P\.?)(?![\w])", "Código General del Proceso"),
        (r"(?<![\w.])CPACA(?![\w])", "Código de Procedimiento Administrativo y de lo Contencioso Administrativo"),
        (r"(?<![\w.])(?:CPTSS|CPT|C\.P\.T\.(?:\s?y\s?S\.S\.)?)(?![\w])",
         "Código Procesal del Trabajo y de la Seguridad Social"),
        (r"(?<![\w.])(?:CPP|C\.P\.P\.?)(?![\w])", "Código de Procedimiento Penal"),
        (r"(?<![\w.])(?:C\.\s?Co\.|C\.\s?de\s?Co\.)(?![\w])", "Código de Comercio"),
        (r"(?<![\w.])E\.T\.(?![\w])", "Estatuto Tributario"),
    ]
]


def expandir_abreviaturas(texto: str) -> str:
    for patron, nombre in _ABREVIATURAS_CODIGOS:
        texto = patron.sub(nombre, texto)
    return texto


_META = [
    re.compile(r"(?i)\b(?:seg[uú]n|de acuerdo con|conforme a|con base en|a partir de)\s+(?:la|las|los|el)\s+"
               r"(?:evidencia|pasajes?|fragmentos?|textos?|documentos?)"
               r"(?:\s+(?:recuperad|proporcionad|entregad|disponib|suministrad|presentad|citad)\w*)?\s*,?\s*"),
    re.compile(r"(?i)\s*,?\s*(?:como|tal como)\s+(?:se\s+)?(?:menciona|indica|señala|establece|observa|aparece|muestra)\w*"
               r"\s+en\s+(?:la|el|los)\s+(?:evidencia|pasajes?|encabezado|fragmentos?)(?:\s*\[?\d+\]?)?"
               r"(?:\s+de\s+la\s+evidencia)?"),
    re.compile(r"\s*\((?:pasajes?|evidencia|fragmentos?)\s*\[?\d+(?:\s*[,y]\s*\d+)*\]?\)", re.IGNORECASE),
    re.compile(r"\s*\[\d+(?:\s*[,-]\s*\d+)*\]"),
]


def quitar_meta_frases(texto: str) -> str:
    """Quita referencias a "la evidencia" o a los números de pasaje y recompone mayúsculas."""
    for patron in _META:
        texto = patron.sub(" " if patron is _META[0] else "", texto)
    texto = re.sub(r"\s+([,.;:])", r"\1", texto)
    texto = re.sub(r"\s{2,}", " ", texto).strip()
    # Mayúscula al inicio de cada oración que haya quedado en minúscula tras quitar la meta-frase.
    return re.sub(r"(^|[.!?]\s+)([a-záéíóúñ])", lambda m: m.group(1) + m.group(2).upper(), texto)


def limpiar(texto: str) -> str:
    return quitar_meta_frases(expandir_abreviaturas(texto or ""))
