"""Tabla de alias de normas: carga configs/alias_normas.yaml (nombre común -> nombre citable)."""
from __future__ import annotations

from functools import lru_cache
from typing import Any

import yaml

from src.common import rutas

ALIAS = rutas.RAIZ / "configs" / "alias_normas.yaml"


@lru_cache(maxsize=1)
def cargar() -> dict[str, dict[str, Any]]:
    """{clave del código en citations.CODES: {nombre_citable, equivale_a, variantes}}."""
    return yaml.safe_load(ALIAS.read_text(encoding="utf-8")) or {}


def nombre_citable(clave: str) -> str | None:
    """Nombre con el que empiezan los pasajes de ese cuerpo ("Código Civil"), o None."""
    entrada = cargar().get(clave)
    return entrada["nombre_citable"] if entrada else None
