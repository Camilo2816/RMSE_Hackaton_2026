"""El corpus no contiene material con respuestas (causal de descalificación, enunciado §8)."""
import json
import re
from urllib.parse import urlparse

import pytest

from src.common import rutas
from src.ingest import fuentes

# Fuentes públicas admitidas por el enunciado (paso 5) y la oficial de la CAN.
DOMINIOS = ("secretariasenado.gov.co", "suin-juriscol.gov.co", "corteconstitucional.gov.co",
            "cortesuprema.gov.co", "consejodeestado.gov.co", "dian.gov.co", "sic.gov.co",
            "funcionpublica.gov.co", "comunidadandina.org", "imprenta.gov.co",
            "cancilleria.gov.co",
            # Superintendencia Financiera: Circular Básica Jurídica (C.E. 029 de 2014), fuente oficial.
            "superfinanciera.gov.co",
            # El enunciado admite "cualquier fuente pública y de libre distribución": el SISJUR de la
            # Alcaldía de Bogotá publica el Acuerdo 02 de 2015 (Reglamento de la Corte Constitucional).
            "alcaldiabogota.gov.co",
            # Fuentes oficiales de actos que el banco nombra: Resolución 368 de 2014 (MinAmbiente) y
            # Boletín de Jurisprudencia n.º 5 de 2016 (Delegatura de Procedimientos Mercantiles).
            "minambiente.gov.co", "supersociedades.gov.co")

if not rutas.FRAGMENTOS.exists():
    pytest.skip("corpus sin construir", allow_module_level=True)

FRAGS = [json.loads(l) for l in rutas.FRAGMENTOS.read_text(encoding="utf-8").splitlines() if l]


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower()).strip()


def test_solo_documentos_del_inventario_y_fuentes_admitidas():
    docs = fuentes.cargar()
    for f in FRAGS:
        assert f["doc_id"] in docs, f["frag_id"]
        host = urlparse(f["url"]).netloc
        assert host.endswith(DOMINIOS), (f["frag_id"], host)


def test_indice_sin_preguntas():
    """Ningún fragmento contiene una pregunta completa de data/*.jsonl."""
    preguntas = []
    for path in rutas.DATA.glob("*.jsonl"):
        for linea in path.read_text(encoding="utf-8").splitlines():
            if linea.strip():
                p = _norm(json.loads(linea).get("pregunta") or "")
                if len(p) >= 60:
                    preguntas.append(p)
    textos = [_norm(f["texto"]) for f in FRAGS]
    fugas = [p[:80] for p in preguntas if any(p in t for t in textos)]
    assert not fugas, fugas
