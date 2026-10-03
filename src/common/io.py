"""Lectura y escritura de JSON/JSONL en UTF-8, con saltos de línea "\n" en cualquier SO."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Iterator


def read_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(obj: Any, path: Path, indent: int | None = 2) -> None:
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=indent) + "\n",
                          encoding="utf-8", newline="\n")


def iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with Path(path).open(encoding="utf-8") as fh:
        for linea in fh:
            if linea.strip():
                yield json.loads(linea)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return list(iter_jsonl(path))


def write_jsonl(rows: Iterable[dict[str, Any]], path: Path) -> int:
    """Escribe una línea JSON por fila; devuelve cuántas escribió. Rechaza NaN/Infinity."""
    n = 0
    with Path(path).open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
            n += 1
    return n
