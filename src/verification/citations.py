"""Wrapper del extractor oficial de citas (scripts/citations.py). No reimplementar.

Carga el módulo oficial tal cual y reexpone lo que usa el sistema, de modo que
el verificador compare citas exactamente como lo hace scripts/evaluate.py.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from src.common.types import Passage

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import citations as oficial  # noqa: E402  scripts/citations.py

extract = oficial.extract
bodies = oficial.bodies
article_level = oficial.article_level
norm = oficial.norm  # minúsculas, sin tildes, espacios colapsados

MAX_PASAJES_EVIDENCIA = 10


def _cargar_evaluador():
    """scripts/evaluate.py con nombre propio (un paquete "evaluate" instalado no lo tapa)."""
    spec = importlib.util.spec_from_file_location("evaluador_oficial", _SCRIPTS / "evaluate.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


evaluador = _cargar_evaluador()
answer_text = evaluador.answer_text  # texto del que el evaluador extrae las citas de la respuesta


def respaldadas(passages: list[Passage]) -> set[tuple]:
    """Citas presentes en el texto de los primeros 10 pasajes (igual que evaluate.py).

    Se extrae pasaje por pasaje, como evaluate.citas_respaldadas: concatenar los
    textos podría fabricar citas que cruzan el límite entre dos pasajes.
    """
    cites: set[tuple] = set()
    for p in passages[:MAX_PASAJES_EVIDENCIA]:
        cites |= extract(p.texto or "")
    return cites


def respaldo_cuerpos(passages: list[Passage]) -> set[tuple]:
    """Cuerpos normativos (tipo, número, año) respaldados por los 10 primeros pasajes."""
    return bodies(respaldadas(passages))


def sin_respaldo(sub: dict, passages: list[Passage]) -> set[tuple]:
    """Cuerpos citados en la respuesta y ausentes de los pasajes, como los cuenta evaluate.py.

    `sub` es la línea de la entrega (o un dict con "formato" y las claves de texto).
    """
    return bodies(extract(answer_text(sub))) - respaldo_cuerpos(passages)
