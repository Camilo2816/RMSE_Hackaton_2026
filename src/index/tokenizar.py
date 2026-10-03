"""Tokenización de BM25, la misma para el corpus (construir.py) y las consultas (bm25.py).

Normaliza lo que en texto jurídico es identificador y no palabra:
- minúsculas y sin tildes ("artículo" = "articulo");
- ordinales pegados al número: "ARTICULO 3o." y "3º" → "3";
- sentencias como un solo token: "C-355" → "c_355", "SU-016" → "su_016";
- números con puntos o guiones internos como un solo token: "2.2.1.1.1" →
  "2_2_1_1_1", "240-1" → "240_1", "1.000.000" → "1_000_000";
- conserva tokens de un carácter (el patrón por defecto de bm25s descarta el "5"
  de "artículo 5"); las letras sueltas caen con las stopwords.
Las palabras pasan por Snowball español; las stopwords son las de bm25s sin tildes.

Si cambia esta función hay que reconstruir el índice: construir.py guarda VERSION
en corpus/index/config.json y cargar.py la verifica.
"""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

VERSION = 1

_ORDINAL = re.compile(r"(\d)[oº°ª]\b")
_SENTENCIA = re.compile(r"\b(su|stc|stl|sl|sp|sc|ac|au|c|t)\s*-\s*(\d+)\b")
_NUM_COMPUESTO = re.compile(r"(?<=\d)[.\-](?=\d)")
_TOKEN = re.compile(r"\w+")


def normalizar(texto: str) -> str:
    """Minúsculas, sin tildes (conserva la ñ), identificadores unidos con "_"."""
    t = unicodedata.normalize("NFD", texto.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn" or c == "̃")
    t = unicodedata.normalize("NFC", t)  # n + tilde combinante vuelve a ser ñ
    t = _ORDINAL.sub(r"\1", t)
    t = _SENTENCIA.sub(r"\1_\2", t)
    return _NUM_COMPUESTO.sub("_", t)


@lru_cache(maxsize=1)
def _stopwords() -> frozenset[str]:
    from bm25s.stopwords import STOPWORDS_SPANISH
    return frozenset(normalizar(w) for w in STOPWORDS_SPANISH)


@lru_cache(maxsize=1)
def _stemmer():
    import Stemmer
    return Stemmer.Stemmer("spanish")


@lru_cache(maxsize=500_000)
def _raiz(palabra: str) -> str:
    if not palabra.isalpha():
        return palabra  # números e identificadores ("c_355", "2_2_1") no se lematizan
    return _stemmer().stemWord(palabra)


def tokenizar(texto: str) -> list[str]:
    stop = _stopwords()
    return [_raiz(w) for w in _TOKEN.findall(normalizar(texto)) if w not in stop]
