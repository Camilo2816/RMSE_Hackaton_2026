"""Cliente del servidor Ollama (API nativa, no la compatible con OpenAI).

Se usa la API nativa (`/api/chat`) en vez de la compatible con OpenAI porque
`think: false` como parámetro top-level es la forma confiable de desactivar el
razonamiento de Qwen3 en Ollama; vía la ruta compatible con OpenAI o dentro de
`options`, Ollama a veces lo ignora (ollama/ollama#13154, #14793).

temperature = 0 y seed fija siempre (enunciado 3.1: el sistema debe ser
determinista). guided_json: Ollama restringe la salida al JSON schema pasado
en el campo `format` (soporte nativo desde dic-2024, sin necesidad de vLLM).

Opciones que se fijan en cada llamada (configs/base.yaml, generation):
- num_ctx: el contexto por defecto de Ollama (4096) es menor que los prompts
  reales (3.400–5.500 tokens) y Ollama recorta el INICIO del prompt, donde van
  la pregunta y las opciones (tools/medir_llm.py).
- num_predict por formato: tope de salida; sin él un bucle de repetición
  cuelga la llamada hasta el timeout.
- reset_cache: Ollama reutiliza la caché KV del prefijo común con la petición
  anterior y recalcula solo el resto con otro tamaño de lote; eso cambia el
  redondeo y, en empates cercanos, el token elegido. Una petición mínima previa
  (1 token, mismas opciones) vacía ese prefijo y hace que cada llamada procese
  el prompt completo igual, sin importar el historial (medido: salidas
  idénticas en órdenes distintos y tras recargar el modelo).

Las llamadas son secuenciales (nunca en paralelo), por determinismo.

Carga del modelo: en frío, Ollama tarda 34–60 s en cargar Llama-3.1-8B con num_ctx 16384,
más que timeout_s (30 s). La primera petición vencía dos veces y la pregunta salía con la
respuesta de respaldo (2026-10-02: 50/50 de una corrida). Antes de cada llamada se consulta
/api/ps (milisegundos) y, si el modelo no está cargado con el num_ctx de la config, se carga
con su propio timeout (timeout_carga_s). Cubre la primera pregunta, la verificación en vivo
horas después de la corrida (keep_alive vencido) y un reinicio de Ollama.
"""
from __future__ import annotations

import json
import time
from typing import Optional

import requests

from src.common.config import Config

_PROMPT_RESET = "."


class LLMError(RuntimeError):
    """El decoder falló dos veces seguidas (HTTP, timeout, JSON inválido o salida truncada).

    El pipeline la captura y usa la respuesta de respaldo determinista.
    """

    def __init__(self, motivo: str, detalle: str = "") -> None:
        super().__init__(f"{motivo}: {detalle}" if detalle else motivo)
        self.motivo = motivo  # http | timeout | json_invalido | truncada


class LLMClient:
    def __init__(self, cfg: Config) -> None:
        """Lee cfg["generation"] (modelo, temperatura, contexto, topes, reintento) y cfg["seed"]."""
        gen = cfg["generation"]
        self.model = gen["model_ollama"] if "model_ollama" in gen else _a_tag_ollama(gen["model"])
        self.temperature = gen.get("temperature", 0)
        self.thinking = gen.get("thinking", False)
        self.guided_json = gen.get("guided_json", True)
        self.seed = cfg.get("seed", 42)
        self.base_url = gen.get("ollama_base_url", "http://localhost:11434")
        self.num_ctx = gen.get("num_ctx")
        self.num_predict: dict[str, int] = dict(gen.get("num_predict") or {})
        self.timeout_s = gen.get("timeout_s", 60)
        self.timeout_carga_s = gen.get("timeout_carga_s", 600)
        self.keep_alive = gen.get("keep_alive", "30m")
        self.repeat_penalty = gen.get("repeat_penalty")
        self.reset_cache = gen.get("reset_cache", True)
        self.factor_reintento = gen.get("reintento_factor_num_predict", 1.5)

    def _opciones(self, num_predict: Optional[int]) -> dict:
        opciones: dict = {"temperature": self.temperature, "seed": self.seed}
        if self.num_ctx:
            opciones["num_ctx"] = self.num_ctx
        if num_predict:
            opciones["num_predict"] = int(num_predict)
        if self.repeat_penalty is not None:
            opciones["repeat_penalty"] = self.repeat_penalty
        return opciones

    def cargado(self) -> bool:
        """El modelo está en memoria con el num_ctx de la config (no hace falta cargarlo)."""
        try:
            resp = requests.get(f"{self.base_url}/api/ps", timeout=10)
            resp.raise_for_status()
            modelos = resp.json().get("models") or []
        except (requests.RequestException, ValueError):
            return False
        return any(m.get("name") == self.model and (not self.num_ctx or m.get("context_length") == self.num_ctx)
                   for m in modelos)

    def asegurar_cargado(self) -> float:
        """Carga el modelo si no está en memoria, con timeout propio. Devuelve los segundos que tardó."""
        if self.cargado():
            return 0.0
        t0 = time.perf_counter()
        opciones = {"num_ctx": self.num_ctx} if self.num_ctx else {}
        try:
            resp = requests.post(f"{self.base_url}/api/generate", timeout=self.timeout_carga_s,
                                 json={"model": self.model, "prompt": "", "keep_alive": self.keep_alive,
                                       "options": opciones})
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise LLMError("carga", str(exc)[:300]) from exc
        return round(time.perf_counter() - t0, 1)

    def _post(self, payload: dict) -> dict:
        resp = requests.post(f"{self.base_url}/api/chat", json=payload, timeout=self.timeout_s)
        resp.raise_for_status()
        return resp.json()

    def _vaciar_cache(self, opciones: dict) -> None:
        """Petición mínima con las mismas opciones (mismo num_ctx: no recarga el modelo)."""
        self._post({"model": self.model, "stream": False, "think": False, "keep_alive": self.keep_alive,
                    "messages": [{"role": "user", "content": _PROMPT_RESET}],
                    "options": {**opciones, "num_predict": 1}})

    def _intento(self, prompt: str, schema: dict, num_predict: Optional[int]) -> tuple[dict, dict]:
        """Una llamada. Devuelve (objeto JSON, métricas) o lanza LLMError."""
        opciones = self._opciones(num_predict)
        payload: dict = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "think": self.thinking,
            "keep_alive": self.keep_alive,
            "options": opciones,
        }
        if self.guided_json:
            payload["format"] = schema
        self.asegurar_cargado()  # fuera del cronómetro y del timeout de la llamada
        t0 = time.perf_counter()
        try:
            if self.reset_cache:
                self._vaciar_cache(opciones)
            data = self._post(payload)
        except requests.Timeout as exc:
            raise LLMError("timeout", f"{self.timeout_s} s") from exc
        except (requests.RequestException, ValueError) as exc:
            raise LLMError("http", str(exc)[:300]) from exc
        metricas = {
            "prompt_tokens": data.get("prompt_eval_count"),
            "gen_tokens": data.get("eval_count"),
            "done_reason": data.get("done_reason"),
            "num_predict": num_predict,
            "segundos": round(time.perf_counter() - t0, 3),
        }
        contenido = (data.get("message") or {}).get("content", "")
        if data.get("done_reason") == "length":
            raise LLMError("truncada", f"{data.get('eval_count')} tokens; {contenido[-200:]!r}")
        try:
            obj = json.loads(contenido)
        except json.JSONDecodeError as exc:
            raise LLMError("json_invalido", repr(contenido[:300])) from exc
        if not isinstance(obj, dict):
            raise LLMError("json_invalido", f"se esperaba un objeto, llegó {type(obj).__name__}")
        return obj, metricas

    def complete_json(self, prompt: str, schema: dict, formato: Optional[str] = None,
                      calls: Optional[list] = None) -> dict:
        """Una llamada al decoder con un reintento; devuelve el objeto JSON ya parseado.

        Usa /api/chat con think=false (top-level) y format=<schema> para
        restringir la salida. Sin streaming: se espera la respuesta completa.
        Como la decodificación es determinista, repetir una salida truncada da
        la misma salida: el reintento amplía num_predict (factor fijo). Si el
        reintento también falla, lanza LLMError. `calls`, si se pasa, recibe
        las métricas de cada intento (van al Trace).
        """
        num_predict = self.num_predict.get(formato) if formato else None
        error: Optional[LLMError] = None
        for intento in (1, 2):
            if intento == 2 and error is not None and error.motivo in ("truncada", "json_invalido") and num_predict:
                num_predict = int(num_predict * self.factor_reintento)
            try:
                obj, metricas = self._intento(prompt, schema, num_predict)
            except LLMError as exc:
                error = exc
                if calls is not None:
                    calls.append({"intento": intento, "error": exc.motivo, "num_predict": num_predict})
                continue
            if calls is not None:
                calls.append({"intento": intento, **metricas})
            return obj
        assert error is not None
        raise error


def _a_tag_ollama(model_hf: str) -> str:
    """Traduce un id de Hugging Face (config canónica del reto) al tag local de Ollama.

    La config declara el modelo con su nombre de Hugging Face
    (p. ej. "Qwen/Qwen3-8B") porque así lo exige el enunciado; Ollama identifica
    el modelo ya descargado con su propio tag ("qwen3:8b"). Este mapeo cubre los
    modelos sugeridos; para otro modelo, declarar "model_ollama" explícito en
    generation dentro del config.
    """
    alias = {
        "qwen/qwen3-8b": "qwen3:8b",
        "meta-llama/llama-3.1-8b-instruct": "llama3.1:8b",
    }
    tag = alias.get(model_hf.lower())
    if tag is None:
        raise ValueError(
            f"no hay tag de Ollama conocido para '{model_hf}'; "
            "declare generation.model_ollama en el config."
        )
    return tag
