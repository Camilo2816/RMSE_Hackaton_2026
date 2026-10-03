"""API FastAPI para la interfaz.

POST /preguntar: el pipeline se construye una vez con registry.build_pipeline(cfg)
y, por petición, devuelve Answer + Trace + normas citadas (docs/CONTRATOS.md §8).
Las peticiones se atienden de a una (un lock): hay una sola GPU.
GET /salud: estado del servicio. En "/" se sirve la interfaz estática (interfaz/).
"""
from __future__ import annotations

import itertools
import logging
import threading
import time
from pathlib import Path
from typing import Any, Literal, Optional

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator, model_validator

from src.api import normas
from src.common import rutas
from src.common.config import Config
from src.common.types import Question

log = logging.getLogger(__name__)

INTERFAZ = rutas.RAIZ / "interfaz"
LETRAS = ("A", "B", "C", "D")


class Consulta(BaseModel):
    """Cuerpo de POST /preguntar."""

    pregunta: str = Field(min_length=1, max_length=10_000)
    formato: Literal["multiple_choice", "semi_open", "open_ended"]
    opciones: Optional[dict[str, str]] = None
    area: Optional[str] = None
    config: Optional[str] = None

    @field_validator("pregunta")
    @classmethod
    def _pregunta(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("la pregunta está vacía")
        return v.strip()

    @model_validator(mode="after")
    def _opciones(self) -> "Consulta":
        if self.formato != "multiple_choice":
            self.opciones = None
            return self
        ops = {k.strip().upper(): (v or "").strip() for k, v in (self.opciones or {}).items()}
        if sorted(ops) != list(LETRAS) or not all(ops.values()):
            raise ValueError("multiple_choice exige las opciones A, B, C y D, todas con texto")
        self.opciones = ops
        return self


def _misma_config(a: str, b: str) -> bool:
    return Path(a).as_posix().removeprefix("./") == Path(b).as_posix().removeprefix("./")


def create_app(cfg: Config, pipeline: Any = None, config_path: Optional[str] = None) -> FastAPI:
    """App FastAPI. Sin `pipeline` lo construye aquí (una vez); las pruebas inyectan uno falso."""
    if pipeline is None:
        from src.pipelines.registry import build_pipeline

        t0 = time.perf_counter()
        pipeline = build_pipeline(cfg)
        log.info("pipeline cargado en %.1f s", time.perf_counter() - t0)

    app = FastAPI(title="RAG de derecho colombiano", version="1.0")
    lock = threading.Lock()
    ids = itertools.count(1)
    estado = {"atendidas": 0}

    @app.get("/salud")
    def salud() -> dict:
        return {"estado": "ok", "pipeline": cfg.get("pipeline"), "config": config_path,
                "ocupado": lock.locked(), "atendidas": estado["atendidas"]}

    @app.post("/preguntar")
    def preguntar(consulta: Consulta) -> dict:
        if consulta.config and config_path and not _misma_config(consulta.config, config_path):
            raise HTTPException(409, f"el servidor corre con {config_path}; reinícielo para usar {consulta.config}")
        with lock:
            q = Question(id=next(ids), formato=consulta.formato, pregunta=consulta.pregunta,
                         opciones=consulta.opciones, area=consulta.area)
            t0 = time.perf_counter()
            try:
                answer, trace = pipeline.run(q)
            except Exception as e:  # noqa: BLE001 - el error llega a la interfaz, el servidor sigue
                log.exception("fallo del pipeline en la pregunta %s", q.id)
                raise HTTPException(500, f"error del pipeline: {type(e).__name__}: {e}") from e
            answer.latencia_ms = int(round((time.perf_counter() - t0) * 1000))
            estado["atendidas"] += 1
        citadas = normas.normas_citadas(answer)
        return {"answer": answer.to_submission(), "trace": trace.to_json(),
                "normas_citadas": citadas, "pasajes": normas.pasajes(answer, citadas)}

    if INTERFAZ.is_dir():
        app.mount("/", StaticFiles(directory=INTERFAZ, html=True), name="interfaz")
    return app
