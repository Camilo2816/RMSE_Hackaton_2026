"""Lectura y escritura de sources/*.yaml, el inventario de documentos del corpus.

`sources/*.yaml` es la fuente de verdad de qué se descarga (el xlsx de docs/ es
una vista). La escritura conserva el encabezado de comentarios de cada archivo y
emite cada documento con un orden de claves fijo, para que los diffs sean legibles
y la reescritura sea idempotente.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Iterable, Iterator

import yaml

from src.common import rutas

if str(rutas.SCRIPTS) not in sys.path:
    sys.path.insert(0, str(rutas.SCRIPTS))
import citations as oficial  # noqa: E402  scripts/citations.py, sin modificar

Doc = dict[str, Any]

CLAVES = [
    "doc_id", "nombre_citable", "tipo", "numero", "anio", "organo_emisor",
    "alias_citables", "fuente", "donde_buscar", "url", "items_del_banco", "areas", "canonico",
    "origen", "prioridad", "ola", "estado", "justificacion",
]
ESTADOS = ("pendiente", "por_verificar", "excluido")
PRIORIDADES = ("alta", "media", "baja")

# Peso de cada área en el banco (enunciado, tabla 4.2): decide en qué archivo vive
# un documento compartido (el área de menor peso entre las suyas).
PESO_AREA = {
    "constitucional": 134, "administrativo": 124, "penal": 123, "procesal": 111,
    "comercial": 104, "civil": 102, "familia": 93, "tributario": 92,
    "laboral": 87, "mercados": 72,
}


def archivos() -> list[Path]:
    return sorted(rutas.SOURCES.glob("*.yaml"))


def cargar_archivo(path: Path) -> tuple[str, str, list[Doc]]:
    """Devuelve (encabezado de comentarios, área, documentos) de un YAML de fuentes."""
    texto = path.read_text(encoding="utf-8")
    encabezado = texto.split("documentos:", 1)[0]
    data = yaml.safe_load(texto) or {}
    return encabezado, data.get("area", path.stem), list(data.get("documentos") or [])


def cargar() -> dict[str, Doc]:
    """Todos los documentos de sources/, por doc_id. Añade `_archivo` (stem del YAML)."""
    docs: dict[str, Doc] = {}
    for path in archivos():
        _, _, lista = cargar_archivo(path)
        for d in lista:
            if d["doc_id"] in docs:
                raise ValueError(f"doc_id duplicado: {d['doc_id']} ({path.name})")
            docs[d["doc_id"]] = {**d, "_archivo": path.stem}
    return docs


def _valor(v: Any) -> str:
    """Escalares y listas en estilo flujo JSON (YAML válido), acentos sin escapar."""
    return json.dumps(v, ensure_ascii=False)


def emitir(encabezado: str, docs: Iterable[Doc]) -> str:
    lineas = [encabezado.rstrip("\n"), "documentos:"]
    for d in docs:
        claves = [k for k in CLAVES if k in d] + sorted(
            k for k in d if k not in CLAVES and not k.startswith("_"))
        for i, k in enumerate(claves):
            prefijo = "  - " if i == 0 else "    "
            lineas.append(f"{prefijo}{k}: {_valor(d[k])}")
    return "\n".join(lineas) + "\n"


def guardar_archivo(path: Path, encabezado: str, docs: Iterable[Doc]) -> None:
    path.write_text(emitir(encabezado, docs), encoding="utf-8", newline="\n")


def canonico_de(texto: str) -> set[tuple]:
    """Cuerpos normativos (tipo, número, año) que el extractor oficial lee en `texto`."""
    return oficial.bodies(oficial.extract(texto))


def canonico_de_encabezado(nombre_citable: str) -> set[tuple]:
    """Lo que el evaluador leerá en un pasaje que empiece con este nombre citable."""
    return canonico_de(f"{nombre_citable}. ARTICULO 5.")


def norma_de(d: Doc) -> str:
    """Prefijo de cada pasaje del documento: nombre citable y, si hay, sus alias.

    Los alias sirven cuando un mismo texto se cita de dos formas que el extractor
    trata como cuerpos distintos (Ley 2452 de 2025 = Código Procesal del Trabajo y
    de la Seguridad Social): así el pasaje respalda ambas.
    """
    alias = d.get("alias_citables") or []
    return d["nombre_citable"] + (f" ({'; '.join(alias)})" if alias else "")


def seleccionar(docs: dict[str, Doc], olas: Iterable[int] | None = None,
                ids: Iterable[str] | None = None,
                incluir_no_pendientes: bool = False) -> Iterator[Doc]:
    """Documentos a procesar, en orden estable (ola, doc_id).

    Por defecto solo los `pendiente`; `excluido` nunca, `por_verificar` solo si se
    pide explícitamente por id o con `incluir_no_pendientes`.
    """
    ids = set(ids or [])
    olas = set(olas) if olas is not None else None
    for d in sorted(docs.values(), key=lambda d: (d.get("ola", 9), d["doc_id"])):
        if ids and d["doc_id"] not in ids:
            continue
        if olas is not None and d.get("ola") not in olas:
            continue
        estado = d.get("estado", "pendiente")
        if estado == "excluido":
            continue
        if estado == "por_verificar" and not (ids or incluir_no_pendientes):
            continue
        yield d
