"""Descarga a corpus/raw/<doc_id>/ los documentos resueltos en sources/urls.lock.json.

Guarda los bytes originales, sin tocar, y un `_descarga.json` por documento con
URL, fecha de consulta y sha256 de cada archivo: es lo que permite declarar el
corpus "reconstruible a partir de las URL" en CORPUS.md.

Por fuente:
- Senado: el documento está partido en páginas (`x.html`, `x_pr001.html`, ...)
  encadenadas por el enlace "Siguiente". Cada página tiene un JS compañero
  (`js/<página>.js`) con las notas de vigencia, que se descarga también.
- Corte Constitucional y PDF: un solo archivo.

No vuelve a descargar lo que ya está completo salvo con --forzar.

    python -m src.ingest.descargar [--ola 0] [--ids ley_472_1998 ...] [--forzar]
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urljoin

from src.common import rutas
from src.ingest import fuentes
from src.ingest.red import Cliente, Respuesta, decodificar, sin_scripts
from src.ingest.resolver import cargar_lock

MAX_PAGINAS = 400  # el Código Civil tiene ~80; tope contra bucles
_SIGUIENTE = re.compile(r'<a[^>]+class="?antsig"?[^>]+href="([^"]+)"[^>]*>\s*Siguiente', re.I)


def _nombre(url: str) -> str:
    return url.rstrip("/").rsplit("/", 1)[-1].split("?")[0]


def _guardar(carpeta: Path, relativo: str, resp: Respuesta, registro: list[dict]) -> None:
    destino = carpeta / relativo
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(resp.contenido)
    registro.append({"archivo": relativo,
                     "url": resp.url, "status": resp.status, "bytes": len(resp.contenido),
                     "sha256": resp.sha256, "content_type": resp.content_type})


def descargar_senado(cli: Cliente, url: str, carpeta: Path) -> tuple[list[dict], list[str]]:
    archivos: list[dict] = []
    paginas: list[str] = []
    visto: set[str] = set()
    actual: str | None = url
    while actual and actual not in visto and len(paginas) < MAX_PAGINAS:
        visto.add(actual)
        resp = cli.get(actual)
        if not resp.ok:
            raise RuntimeError(f"HTTP {resp.status} en {actual}")
        nombre = _nombre(actual)
        _guardar(carpeta, nombre, resp, archivos)
        paginas.append(nombre)
        js = urljoin(actual, "js/" + nombre.rsplit(".", 1)[0] + ".js")
        rjs = cli.get(js)
        if rjs.ok:
            _guardar(carpeta, "js/" + _nombre(js), rjs, archivos)
        html = sin_scripts(decodificar(resp.contenido, resp.content_type))
        sig = {urljoin(actual, h) for h in _SIGUIENTE.findall(html)}
        sig.discard(actual)
        actual = min(sig) if sig else None
    return archivos, paginas


def descargar_uno(cli: Cliente, url: str, carpeta: Path) -> tuple[list[dict], list[str]]:
    resp = cli.get(url)
    if not resp.ok:
        raise RuntimeError(f"HTTP {resp.status} en {url}")
    archivos: list[dict] = []
    _guardar(carpeta, _nombre(url), resp, archivos)
    return archivos, [_nombre(url)]


def descargar_doc(cli: Cliente, doc_id: str, entrada: dict, forzar: bool = False) -> dict:
    carpeta = rutas.RAW / doc_id
    registro = carpeta / "_descarga.json"
    if registro.exists() and not forzar:
        previo = json.loads(registro.read_text(encoding="utf-8"))
        if previo.get("url") == entrada["url"] and previo.get("completo"):
            return previo
    carpeta.mkdir(parents=True, exist_ok=True)
    if entrada["parser"] == "senado":
        archivos, paginas = descargar_senado(cli, entrada["url"], carpeta)
    else:
        archivos, paginas = descargar_uno(cli, entrada["url"], carpeta)
    info = {"doc_id": doc_id, "url": entrada["url"], "parser": entrada["parser"],
            "fecha_consulta": date.today().isoformat(), "paginas": paginas,
            "archivos": archivos, "completo": True}
    registro.write_text(json.dumps(info, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return info


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ola", type=int, nargs="*")
    ap.add_argument("--ids", nargs="*")
    ap.add_argument("--forzar", action="store_true")
    ap.add_argument("--pausa", type=float, default=1.0)
    args = ap.parse_args()

    lock = cargar_lock()
    cli = Cliente(pausa=args.pausa)
    for d in fuentes.seleccionar(fuentes.cargar(), args.ola, args.ids):
        entrada = lock.get(d["doc_id"])
        if not entrada or entrada.get("estado") != "ok":
            print(f"sin_url        {d['doc_id']}")
            continue
        try:
            info = descargar_doc(cli, d["doc_id"], entrada, args.forzar)
            print(f"ok             {d['doc_id']:40s} {len(info['paginas'])} pág.", flush=True)
        except Exception as e:  # un documento roto no detiene la ola
            print(f"error          {d['doc_id']:40s} {e}", flush=True)


if __name__ == "__main__":
    main()
