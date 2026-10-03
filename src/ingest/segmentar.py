"""Segmenta leyes por artículo (y sentencias por sección) y escribe los fragmentos.

Entrada: corpus/interim/<doc_id>.json (estructura que produce extraer.py).
Salida:
- corpus/processed/<doc_id>.txt: el texto procesado, que es la concatenación de
  los fragmentos (separados por una línea en blanco). Así `texto` es literal:
  `txt[inicio:fin] == texto` para todo fragmento.
- corpus/processed/fragmentos/<doc_id>.jsonl: fragmentos del documento.
- corpus/processed/fragmentos.jsonl: todos, en orden (doc_id, posición), con
  `chunk_id` = número de fila. Es la única entrada de src/index/construir.py.

Cada fragmento empieza con el nombre citable de su norma (y sus alias), porque el
evaluador reconoce el respaldo de una cita solo si la norma aparece en el texto
del pasaje: "Ley 472 de 1998. TITULO I. ... ARTICULO 3. ...".

    python -m src.ingest.segmentar [--ola 0] [--ids ley_472_1998 ...]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from typing import Any, Iterable
from urllib.parse import urljoin

from src.common import rutas
from src.ingest import fuentes, metadatos
from src.ingest.fuentes import Doc

MAX_CHARS = 2000      # ~500 tokens: cabe con holgura en encoder, reranker y prompt
MAX_RUTA_PARTE = 90   # cada nivel de la ruta (Libro/Título/Capítulo) se recorta
SEP = "\n\n"


def _slug(s: str) -> str:
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def _ruta(ruta: list[str]) -> str:
    partes = [p if len(p) <= MAX_RUTA_PARTE else p[:MAX_RUTA_PARTE].rsplit(" ", 1)[0] + "…"
              for p in ruta]
    return " > ".join(partes)


def _trozos(texto: str, limite: int) -> list[str]:
    """Parte un párrafo demasiado largo por oraciones (o por palabras si hace falta)."""
    if len(texto) <= limite:
        return [texto]
    oraciones = re.split(r"(?<=[.;:])\s+", texto)
    out, actual = [], ""
    for o in oraciones:
        while len(o) > limite:  # oración gigante (tablas): corte duro en un espacio
            corte = o[:limite].rsplit(" ", 1)[0] or o[:limite]
            if actual:
                out.append(actual)
                actual = ""
            out.append(corte)
            o = o[len(corte):].lstrip()
        if actual and len(actual) + 1 + len(o) > limite:
            out.append(actual)
            actual = o
        else:
            actual = f"{actual} {o}".strip()
    if actual:
        out.append(actual)
    return out


def _partes(parrafos: list[str], limite: int) -> list[list[str]]:
    """Agrupa párrafos en partes de hasta `limite` caracteres, sin cortar un párrafo
    salvo que él solo exceda el límite."""
    partes: list[list[str]] = [[]]
    largo = 0
    for p in parrafos:
        for t in _trozos(p, limite):
            if partes[-1] and largo + len(t) + 1 > limite:
                partes.append([])
                largo = 0
            partes[-1].append(t)
            largo += len(t) + 1
    return [p for p in partes if p]


def fragmentos_ley(d: Doc, est: dict[str, Any]) -> list[dict[str, Any]]:
    """Fragmentos de una norma con articulado (Senado): encabezado + un fragmento por
    artículo, partido en partes con "(continuación)" si excede MAX_CHARS."""
    norma = fuentes.norma_de(d)
    base = metadatos.base(d)
    url_base = est.get("fuente_original") or est.get("url") or ""  # legalize-co: la URL de SUIN
    frags: list[dict[str, Any]] = []

    pre = est.get("preambulo") or {}
    parrafos_pre = [p for p in pre.get("parrafos", []) if p.strip()]
    if parrafos_pre:
        notas = metadatos.linea_notas(pre.get("notas", {}),
                                      ("resumen de notas de vigencia", "notas de vigencia"))
        for i, trozo in enumerate(_partes(parrafos_pre, MAX_CHARS)):
            texto = f"{norma}. Encabezado. " + "\n".join(trozo)
            frags.append({**base, "frag_id": f"{d['doc_id']}:encabezado:{i}", "articulo": None,
                          "seccion": "encabezado", "ruta": [], "vigencia": "desconocida",
                          "texto": texto, "url": url_base})
        if notas:
            frags[-1]["texto"] += "\n" + notas

    repetidos: dict[str, int] = {}
    for a in est.get("articulos", []):
        num = a["articulo"]
        repetidos[num] = repetidos.get(num, 0) + 1
        clave = f"art_{_slug(num)}" + (f"~{repetidos[num]}" if repetidos[num] > 1 else "")
        ruta = _ruta(a.get("ruta") or [])
        cabeza = f"{norma}. {ruta}. " if ruta else f"{norma}. "
        cabeza_cont = f"{cabeza}ARTÍCULO {num} (continuación). "
        notas = metadatos.linea_notas(a.get("notas", {}))
        partes = _partes(a["parrafos"], MAX_CHARS - len(cabeza_cont))
        vig = metadatos.vigencia(a["parrafos"], a.get("notas", {}))
        url = urljoin(url_base, a["pagina"]) if a.get("pagina") else url_base
        for i, trozo in enumerate(partes):
            texto = (cabeza if i == 0 else cabeza_cont) + "\n".join(trozo)
            if i == len(partes) - 1 and notas:
                texto += "\n" + notas
            frags.append({**base, "frag_id": f"{d['doc_id']}:{clave}:{i}", "articulo": num,
                          "seccion": None, "ruta": a.get("ruta") or [], "vigencia": vig,
                          "texto": texto, "url": url})
    n_por_articulo: dict[str, int] = {}
    for f in frags:
        k = f["frag_id"].rsplit(":", 1)[0]
        n_por_articulo[k] = n_por_articulo.get(k, 0) + 1
    for f in frags:
        k, parte = f["frag_id"].rsplit(":", 1)
        f["parte"], f["n_partes"] = int(parte), n_por_articulo[k]
    return frags


def fragmentos_sentencia(d: Doc, est: dict[str, Any]) -> list[dict[str, Any]]:
    """Fragmentos de una sentencia de la Corte Constitucional.

    - `ficha`: ponente, fecha, referencia y lo que resolvió (clave para "sentido del fallo").
    - `descriptores`: temas y extractos de la relatoría.
    - Una serie de fragmentos por sección (antecedentes, consideraciones, decisión,
      salvamentos...), de hasta MAX_CHARS, con el subtítulo vigente en el encabezado.
    """
    from src.ingest.parsers.corte_constitucional import NOMBRE_SECCION

    norma = fuentes.norma_de(d)
    organo = d.get("organo_emisor") or "Corte Constitucional"
    base = {**metadatos.base(d)}
    url = est.get("url") or ""
    frags: list[dict[str, Any]] = []
    contador: dict[str, int] = {}

    def cabeza(seccion: str, sub: str | None) -> str:
        sub = _ruta([sub]) if sub else ""
        return f"{norma}, {organo}. {NOMBRE_SECCION[seccion]}" + (f" > {sub}" if sub else "") + ". "

    def agregar(seccion: str, bloques: list[tuple[str | None, list[str]]]) -> None:
        n = contador[seccion] = contador.get(seccion, 0) + 1
        clave = f"{seccion}" + (f"~{n}" if n > 1 else "")
        nuevos = []
        for sub, textos in bloques:
            texto = cabeza(seccion, sub) + "\n".join(textos)
            nuevos.append({**base, "frag_id": f"{d['doc_id']}:{clave}:{len(nuevos)}",
                           "articulo": None, "seccion": seccion, "ruta": [sub] if sub else [],
                           "vigencia": "desconocida", "texto": texto, "url": url,
                           "parte": len(nuevos)})
        for f in nuevos:
            f["n_partes"] = len(nuevos)
        frags.extend(nuevos)

    limite = MAX_CHARS - len(cabeza("consideraciones", "x" * MAX_RUTA_PARTE))

    ficha = est.get("ficha") or {}
    lineas = []
    if ficha.get("ponentes"):
        lineas.append("Magistrado ponente: " + "; ".join(ficha["ponentes"]) + ".")
    if ficha.get("fecha"):
        lineas.append(f"Fecha: {ficha['fecha']}.")
    if ficha.get("referencia"):
        lineas.append(ficha["referencia"])
    lineas += (ficha.get("otros") or [])[:4]
    resuelve = [x for x in ficha.get("resuelve") or [] if not re.match(r"^RESUELVE\s*:?$", x, re.I)]
    if resuelve:
        lineas.append("Decisión: " + " ".join(resuelve))
    if lineas:
        agregar("ficha", [(None, p) for p in _partes(lineas, limite)])
    if est.get("descriptores"):
        agregar("descriptores", [(None, p) for p in _partes(est["descriptores"], limite)])

    for sec in est.get("secciones", []):
        bloques: list[tuple[str | None, list[str]]] = []
        actual: list[str] = []
        largo, sub_actual = 0, None
        for par in sec["parrafos"]:
            for t in _trozos(par["texto"], limite):
                cambia_sub = par["sub"] != sub_actual and largo >= limite // 2
                if actual and (largo + len(t) + 1 > limite or cambia_sub):
                    bloques.append((sub_actual, actual))
                    actual, largo = [], 0
                if not actual:
                    sub_actual = par["sub"]
                actual.append(t)
                largo += len(t) + 1
        if actual:
            bloques.append((sub_actual, actual))
        if bloques:
            agregar(sec["seccion"], bloques)
    return frags


CAMPOS = ["chunk_id", "frag_id", "doc_id", "norma", "tipo", "numero", "anio", "articulo",
          "seccion", "ruta", "organo_emisor", "vigencia", "parte", "n_partes", "inicio", "fin",
          "texto", "cuerpos", "url"]


def escribir_documento(d: Doc, frags: list[dict[str, Any]]) -> dict[str, Any]:
    """Escribe <doc_id>.txt y fragmentos/<doc_id>.jsonl con offsets exactos."""
    doc_id = d["doc_id"]
    partes, pos = [], 0
    for f in frags:
        f["inicio"], f["fin"] = pos, pos + len(f["texto"])
        pos = f["fin"] + len(SEP)
        partes.append(f["texto"])
        f["cuerpos"] = sorted([list(c) for c in fuentes.canonico_de(f["texto"])],
                              key=lambda c: tuple(x or "" for x in c))
        f["chunk_id"] = None  # se asigna al consolidar
    txt = SEP.join(partes)
    rutas.PROCESSED.mkdir(parents=True, exist_ok=True)
    rutas.FRAGMENTOS_DIR.mkdir(parents=True, exist_ok=True)
    (rutas.PROCESSED / f"{doc_id}.txt").write_text(txt, encoding="utf-8", newline="\n")
    with (rutas.FRAGMENTOS_DIR / f"{doc_id}.jsonl").open("w", encoding="utf-8", newline="\n") as fh:
        for f in frags:
            fh.write(json.dumps({k: f.get(k) for k in CAMPOS}, ensure_ascii=False) + "\n")
    return {"doc_id": doc_id, "n_fragmentos": len(frags),
            "sha256": hashlib.sha256(txt.encode("utf-8")).hexdigest()}


def verificar_encabezados(d: Doc, frags: Iterable[dict[str, Any]]) -> list[str]:
    """Fragmentos cuyo inicio no hace que el extractor oficial lea la norma propia."""
    if not d.get("canonico"):
        return []
    propio = tuple(d["canonico"])
    n = len(fuentes.norma_de(d)) + 2
    return [f["frag_id"] for f in frags if propio not in fuentes.canonico_de(f["texto"][:n])]


def consolidar() -> int:
    """Une fragmentos/<doc_id>.jsonl de los documentos vigentes en sources/ en
    fragmentos.jsonl, en orden estable, asignando chunk_id = fila."""
    activos = {k for k, d in fuentes.cargar().items() if d.get("estado") != "excluido"}
    fila = 0
    with rutas.FRAGMENTOS.open("w", encoding="utf-8", newline="\n") as out:
        for path in sorted(rutas.FRAGMENTOS_DIR.glob("*.jsonl")):
            if path.stem not in activos:
                continue
            for linea in path.read_text(encoding="utf-8").splitlines():
                f = json.loads(linea)
                f["chunk_id"] = fila
                out.write(json.dumps(f, ensure_ascii=False) + "\n")
                fila += 1
    return fila


def segmentar_doc(d: Doc) -> dict[str, Any] | None:
    path = rutas.INTERIM / f"{d['doc_id']}.json"
    if not path.exists():
        return None
    est = json.loads(path.read_text(encoding="utf-8"))
    if est.get("parser") in ("senado", "pdf", "funcion_publica", "legalize", "sfc_cbj"):
        frags = fragmentos_ley(d, est)
    elif est.get("parser") in ("corte_constitucional", "pdf_sentencia", "relatoria_csj"):
        frags = fragmentos_sentencia(d, est)
    else:
        raise NotImplementedError(f"segmentación para parser {est.get('parser')!r}")
    malos = verificar_encabezados(d, frags)
    if malos:
        raise ValueError(f"{len(malos)} fragmentos sin encabezado citable: {malos[:3]}")
    return escribir_documento(d, frags)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ola", type=int, nargs="*")
    ap.add_argument("--ids", nargs="*")
    args = ap.parse_args()
    for d in fuentes.seleccionar(fuentes.cargar(), args.ola, args.ids):
        try:
            info = segmentar_doc(d)
        except Exception as e:
            print(f"error          {d['doc_id']:40s} {e}")
            continue
        if info:
            print(f"ok             {d['doc_id']:40s} {info['n_fragmentos']} fragmentos")
    print(f"fragmentos.jsonl: {consolidar()} filas")


if __name__ == "__main__":
    main()
