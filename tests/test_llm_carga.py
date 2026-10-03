"""generation/llm.py: la carga del modelo en frío va aparte, con su propio timeout (Ollama simulado)."""
import pytest

from src.generation import llm as modulo
from src.generation.llm import LLMClient, LLMError

CFG = {"seed": 42, "generation": {"model": "meta-llama/Llama-3.1-8B-Instruct", "num_ctx": 16384,
                                  "timeout_s": 30, "timeout_carga_s": 600, "keep_alive": "30m"}}


class Resp:
    def __init__(self, data):
        self.data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self.data


@pytest.fixture
def ollama(monkeypatch):
    estado = {"modelos": [], "cargas": []}

    def get(url, timeout):
        assert url.endswith("/api/ps")
        return Resp({"models": estado["modelos"]})

    def post(url, json, timeout):
        assert url.endswith("/api/generate")
        estado["cargas"].append((json["options"], timeout))
        return Resp({"done_reason": "load"})

    monkeypatch.setattr(modulo.requests, "get", get)
    monkeypatch.setattr(modulo.requests, "post", post)
    return estado


def test_no_recarga_si_ya_esta_con_el_contexto_de_la_config(ollama):
    ollama["modelos"] = [{"name": "llama3.1:8b", "context_length": 16384}]
    assert LLMClient(CFG).asegurar_cargado() == 0.0 and ollama["cargas"] == []


def test_carga_con_su_timeout_si_falta_o_tiene_otro_contexto(ollama):
    ollama["modelos"] = [{"name": "llama3.1:8b", "context_length": 4096}]
    LLMClient(CFG).asegurar_cargado()
    assert ollama["cargas"] == [({"num_ctx": 16384}, 600)]


def test_una_carga_fallida_es_llmerror(monkeypatch, ollama):
    def falla(url, json, timeout):
        raise modulo.requests.ConnectionError("Ollama apagado")
    monkeypatch.setattr(modulo.requests, "post", falla)
    with pytest.raises(LLMError):
        LLMClient(CFG).asegurar_cargado()
