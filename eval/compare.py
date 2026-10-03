"""Tabla comparativa de corridas en eval/runs/ (lee report.json de cada una).

Uso:
    python eval/compare.py eval/runs/
"""
from __future__ import annotations

from pathlib import Path


def compare(runs_dir: Path) -> str:
    """Tabla markdown: corrida, pipeline, cerradas, citación, abstención, RAGAS, s/pregunta."""
    raise NotImplementedError


if __name__ == "__main__":
    raise NotImplementedError
