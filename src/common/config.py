"""Carga de configuración: configs/base.yaml + config del pipeline.

El archivo del pipeline (configs/baseline.yaml, configs/agentic.yaml) sobrescribe
a base.yaml con merge profundo. El resultado es un dict; `cfg["pipeline"]`
decide qué Pipeline construye src/pipelines/registry.py.
"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

from src.common import rutas

Config = dict[str, Any]

BASE = rutas.RAIZ / "configs" / "base.yaml"


def deep_merge(base: Config, override: Config) -> Config:
    """Merge recursivo de dicts; los valores de `override` ganan. No muta las entradas."""
    out = copy.deepcopy(base)
    for clave, valor in override.items():
        if isinstance(valor, dict) and isinstance(out.get(clave), dict):
            out[clave] = deep_merge(out[clave], valor)
        else:
            out[clave] = copy.deepcopy(valor)
    return out


def _leer(path: str | Path) -> Config:
    path = Path(path)
    if not path.is_absolute() and not path.exists():
        path = rutas.RAIZ / path  # relativo a la raíz del repo, no al cwd
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_config(path: str | Path, base: str | Path = BASE) -> Config:
    """Lee base.yaml y el YAML del pipeline y devuelve la config fusionada."""
    return deep_merge(_leer(base), _leer(path))
