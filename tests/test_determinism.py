"""Verificación en vivo: dos corridas iguales dan los mismos pasajes y las mismas citas.

Corre el pipeline completo (Ollama incluido) sobre un id por formato, dos veces.
Hace skip si el índice no está construido o si Ollama no responde.
"""
import pytest
import requests

from src.common import io, rutas
from src.common.config import load_config
from src.common.types import Question
from src.verification.citations import answer_text, extract

IDS = [58, 589, 253]  # cerrada, semiabierta, abierta

if not (rutas.INDEX / "config.json").exists():
    pytest.skip("índice sin construir (python -m src.index.construir)", allow_module_level=True)

_CFG = load_config("configs/baseline.yaml")
try:
    requests.get(_CFG["generation"].get("ollama_base_url", "http://localhost:11434") + "/api/tags",
                 timeout=3).raise_for_status()
except requests.RequestException:
    pytest.skip("Ollama no responde", allow_module_level=True)


def _huella(pipe, q: Question):
    answer, _ = pipe.run(q)
    sub = answer.to_submission()
    pasajes = [(p["doc_id"], p.get("inicio"), p.get("fin")) for p in sub["pasajes_recuperados"]]
    return pasajes, sorted(extract(answer_text(sub)), key=str), sub.get("respuesta_correcta")


def test_mismos_pasajes_y_citas():
    """Dos corridas del mismo pipeline → mismos pasajes y citas."""
    from src.pipelines.registry import build_pipeline

    pipe = build_pipeline(_CFG)
    filas = {f["id"]: f for f in io.read_jsonl(rutas.DATA / "sample_50.jsonl")}
    preguntas = [Question.from_dict(filas[i]) for i in IDS]
    primera = [_huella(pipe, q) for q in preguntas]
    segunda = [_huella(pipe, q) for q in reversed(preguntas)][::-1]  # otro orden: la caché no influye
    for q, a, b in zip(preguntas, primera, segunda):
        assert a == b, q.id
