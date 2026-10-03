"""Cliente HTTP de la ingesta: cortés, con reintentos y decodificación explícita.

- Una pausa mínima por host entre peticiones (los sitios oficiales son lentos y
  no conviene saturarlos).
- Reintentos con espera creciente ante errores de red y 5xx.
- Los bytes se guardan tal cual en corpus/raw/; la decodificación se hace aparte,
  con el charset del documento (el Senado sirve ISO-8859-1 y la Corte, cp1252).
"""
from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass
from urllib.parse import urlparse

import requests
import truststore

# Algunos servidores oficiales (Función Pública) no envían su certificado intermedio;
# el almacén del sistema operativo lo completa, el paquete de CA de requests no.
# truststore verifica igual (no desactiva nada), solo con las CA del sistema.
truststore.inject_into_ssl()

USER_AGENT = ("hackathon-2026-corpus/0.1 (+investigacion academica; "
              "Universidad de los Andes, AI Week 2026)")


@dataclass
class Respuesta:
    url: str
    status: int
    contenido: bytes
    content_type: str

    @property
    def ok(self) -> bool:
        return self.status == 200 and bool(self.contenido)

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.contenido).hexdigest()


class Cliente:
    def __init__(self, pausa: float = 1.0, reintentos: int = 3, timeout: float = 60.0):
        self.pausa = pausa
        self.reintentos = reintentos
        self.timeout = timeout
        self._ultimo: dict[str, float] = {}
        self._s = requests.Session()
        self._s.headers["User-Agent"] = USER_AGENT

    def _esperar_turno(self, url: str) -> None:
        host = urlparse(url).netloc
        falta = self.pausa - (time.monotonic() - self._ultimo.get(host, 0.0))
        if falta > 0:
            time.sleep(falta)
        self._ultimo[host] = time.monotonic()

    def get(self, url: str) -> Respuesta:
        ultimo_error: Exception | None = None
        for intento in range(self.reintentos):
            self._esperar_turno(url)
            try:
                r = self._s.get(url, timeout=self.timeout, allow_redirects=True)
            except requests.RequestException as e:
                ultimo_error = e
                time.sleep(2 ** intento)
                continue
            if r.status_code >= 500:
                time.sleep(2 ** intento)
                ultimo_error = RuntimeError(f"HTTP {r.status_code}")
                continue
            return Respuesta(r.url, r.status_code, r.content, r.headers.get("Content-Type", ""))
        return Respuesta(url, 0, b"", f"error: {ultimo_error}")

    def tamano(self, url: str) -> int | None:
        """Tamaño total del archivo sin descargarlo (petición Range de 1 byte).

        Sirve para sondear existencia donde la fuente responde 200 con una página de
        error (relatoría de la Corte). None si la red falla o el servidor no informa.
        """
        for intento in range(self.reintentos):
            self._esperar_turno(url)
            try:
                r = self._s.get(url, timeout=self.timeout, headers={"Range": "bytes=0-0"})
            except requests.RequestException:
                time.sleep(2 ** intento)
                continue
            if r.status_code >= 500:
                time.sleep(2 ** intento)
                continue
            m = re.search(r"/(\d+)$", r.headers.get("Content-Range", ""))
            if r.status_code == 206 and m:
                return int(m.group(1))
            return len(r.content) if r.status_code == 200 else 0
        return None


_META_CHARSET = re.compile(rb"""<meta[^>]+charset=["']?([\w-]+)""", re.I)


def decodificar(contenido: bytes, content_type: str = "") -> str:
    """Bytes -> texto con el charset declarado; ISO-8859-1 se lee como cp1252 (superconjunto).

    Si los bytes son UTF-8 válido y no ASCII puro, se usa UTF-8 aunque la página declare
    otra cosa (Función Pública declara ISO-8859-1 y sirve UTF-8). Un texto cp1252 con
    tildes casi nunca es UTF-8 válido, así que la regla no confunde los dos casos.
    """
    if not contenido.isascii():
        try:
            return contenido.decode("utf-8").replace("﻿", "")
        except UnicodeDecodeError:
            pass
    charset = None
    m = re.search(r"charset=([\w-]+)", content_type or "", re.I)
    if m:
        charset = m.group(1)
    else:
        m2 = _META_CHARSET.search(contenido[:4096])
        if m2:
            charset = m2.group(1).decode("ascii", "ignore")
    charset = (charset or "utf-8").lower()
    if charset in ("iso-8859-1", "latin-1", "latin1", "windows-1252"):
        charset = "cp1252"
    try:
        return contenido.decode(charset)
    except (UnicodeDecodeError, LookupError):
        # Bytes sin carácter en cp1252 (0x81, 0x8D, 0x8F, 0x90, 0x9D) son basura de la
        # fuente (p. ej. "amplio”\x80\x9d" en la C-540/23): se descartan.
        return re.sub("€?�", "", contenido.decode("cp1252", errors="replace"))


# Algunas redes (proxies de seguridad) inyectan <script> en las páginas HTTP. El
# texto normativo nunca vive en un <script>, así que se eliminan todos antes de parsear.
_SCRIPTS = re.compile(r"<script\b.*?</script\s*>", re.I | re.S)


def sin_scripts(html: str) -> str:
    return _SCRIPTS.sub("", html)
