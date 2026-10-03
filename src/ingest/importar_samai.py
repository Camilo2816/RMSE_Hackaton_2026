"""Importa sentencias de unificación del Consejo de Estado exportadas de SAMAI.

SAMAI (https://samai.consejodeestado.gov.co/) no da un enlace estable por documento:
la exportación es un zip por providencia con el documento (PDF, DOC o DOCX) y su
`FichaProvidencia_*.html` oficial (radicado, sala, despacho, tipo, fecha, decisión,
titulación). Este módulo reemplaza resolver + descargar para esa fuente:

- toma solo las providencias de tipo "Unificación - Sentencia" (o "Sentencia"), sin
  salvamentos, aclaraciones ni autos (pesarían en la recuperación sin ser la regla);
- copia documento y ficha a corpus/raw/<doc_id>/ con un _descarga.json (sha256,
  radicado, URL de SAMAI) para que el inventario sea trazable;
- DOC (antiword, Latin-1) y DOCX (XML) se pasan a líneas en `texto.json`, que
  parsers/pdf_sentencia.py lee igual que el `ocr.json` de un PDF escaneado;
- registra cada sentencia en sources/consejo_estado.yaml. El nombre citable lleva el
  código de unificación si el texto lo trae ("2020CE-SUJ-4-005"), si no el radicado.

    python -m src.ingest.importar_samai --zip consejo_estado.zip
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import shutil
import subprocess
import tempfile
import zipfile
from datetime import date
from pathlib import Path
from typing import Any

import pymupdf
from bs4 import BeautifulSoup

from src.common import rutas
from src.ingest import fuentes

URL_SAMAI = "https://samai.consejodeestado.gov.co/"
ARCHIVO_FUENTES = rutas.SOURCES / "consejo_estado.yaml"
ENCABEZADO = """# Consejo de Estado: sentencias de unificación exportadas de SAMAI (src/ingest/importar_samai.py).
# Lo genera el importador; `url` es el portal de SAMAI y el radicado identifica la providencia.
area: administrativo
"""
_TIPOS = re.compile(r"^(?:Unificación - )?Sentencia$")
_SUJ = re.compile(r"\b(\d{4})\s*CE\s*-\s*SUJ\s*-\s*(\d)\s*-\s*(\d{3})\b")
_CAMPOS = ["Núm. del proceso", "Núm. interno", "Despacho", "Titular vigente", "Sala Decisión", "Actor",
           "Demandado", "Naturaleza del proceso", "Clase del proceso", "Descripción", "Índice", "Decisión",
           "Anotación", "Providencia del", "Tipo", "Cuaderno", "Estado"]
_MESES = {m: i for i, m in enumerate(["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
                                      "septiembre", "octubre", "noviembre", "diciembre"], 1)}
_SECCION_AREAS = {"Sección Cuarta": ["tributario", "administrativo"],
                  "Sección Segunda": ["administrativo", "laboral"]}


def ficha(html: bytes) -> dict[str, str]:
    texto = re.sub(r"[\xa0\s]+", " ", BeautifulSoup(html, "lxml").get_text(" ", strip=True))
    corte = texto.find("Titulación")
    cabeza = texto[:corte] if corte > 0 else texto
    # "(?<!Sala )": "Decisión:" también aparece dentro de "Sala Decisión:"
    pos = sorted((m.start(), k, m.end()) for k in _CAMPOS
                 for m in [re.search(r"(?<!Sala )" + re.escape(k) + r":", cabeza)] if m)
    out = {k: cabeza[e:(pos[i + 1][0] if i + 1 < len(pos) else len(cabeza))].strip()
           for i, (_, k, e) in enumerate(pos)}
    out["Titulación"] = texto[corte + len("Titulación"):].strip() if corte > 0 else ""
    return out


def _fecha(texto: str) -> str | None:
    m = re.search(r"(\d{1,2}) de (\w+) de (\d{4})", texto or "")
    if not m or m.group(2).lower() not in _MESES:
        return None
    return f"{m.group(3)}-{_MESES[m.group(2).lower()]:02d}-{int(m.group(1)):02d}"


def lineas_doc(path: Path) -> tuple[str, list[str]]:
    """(motor, líneas) de un DOC (antiword) o DOCX (XML de Word)."""
    if path.suffix.lower() == ".docx":
        with zipfile.ZipFile(path) as z:
            xml = z.read("word/document.xml").decode("utf-8")
        parrafos = []
        for p in re.findall(r"<w:p[ >].*?</w:p>", xml, re.S):
            t = "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", p))
            parrafos.append(BeautifulSoup(t, "lxml").get_text() if "&" in t else t)
        return "docx (XML de Word)", [p.strip() for p in parrafos]
    salida = subprocess.run(["antiword", "-w", "0", str(path)], capture_output=True, check=True).stdout
    return "antiword", [l.strip() for l in salida.decode("latin-1").splitlines()]


def texto_documento(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        return "\n".join(p.get_text() for p in pymupdf.open(path))
    return "\n".join(lineas_doc(path)[1])


def _documento_de(carpeta: Path, n_fichas: int) -> Path | None:
    docs = sorted(p for p in carpeta.iterdir() if p.suffix.lower() in (".pdf", ".doc", ".docx"))
    if n_fichas == 1 and len(docs) == 1:
        return docs[0]
    candidatos = [p for p in docs if re.search(r"SENTENCIA|FALLO", p.name, re.I)
                  and not re.search(r"SALVAMENTO|ACLARACI|AUTO", p.name, re.I)]
    return candidatos[0] if len(candidatos) == 1 else None


def recorrer(raiz: Path):
    """(carpeta, ficha_html, datos) de cada providencia de los zips anidados ya extraídos."""
    for html in sorted(raiz.rglob("FichaProvidencia_*.html")):
        yield html.parent, html, ficha(html.read_bytes())


def importar(zip_path: Path) -> list[dict[str, Any]]:
    tmp = Path(tempfile.mkdtemp(prefix="samai_", dir=rutas.RAIZ))  # dentro del repo: rutas cortas
    try:
        pendientes = [zip_path]
        while pendientes:
            z = pendientes.pop()
            destino = tmp / f"z{len(list(tmp.iterdir()))}"
            with zipfile.ZipFile(z) as zf:
                zf.extractall(destino)
            pendientes += list(destino.rglob("*.zip"))
        hoy = date.today().isoformat()
        registros: list[dict[str, Any]] = []
        vistos: set[str] = set()
        documentos: set[str] = set()  # sha256: la exportación repite providencias en varios paquetes
        for carpeta, html, f in recorrer(tmp):
            if not _TIPOS.match(f.get("Tipo", "").strip()):
                continue
            n_fichas = len(list(carpeta.glob("FichaProvidencia_*.html")))
            doc = _documento_de(carpeta, n_fichas)
            if doc is None:
                print(f"sin_documento  {f.get('Núm. del proceso')} ({carpeta.name})")
                continue
            huella = hashlib.sha256(doc.read_bytes()).hexdigest()
            if huella in documentos:
                print(f"repetido       {f.get('Núm. del proceso')} ({doc.name})")
                continue
            documentos.add(huella)
            radicado = re.sub(r"\D", "", f["Núm. del proceso"])
            fecha = _fecha(f.get("Providencia del", ""))
            doc_id = base = f"sentencia_ce_{radicado}"
            n = 1
            while doc_id in vistos:
                n += 1
                doc_id = f"{base}_{n}"
            vistos.add(doc_id)
            texto = texto_documento(doc)
            m = _SUJ.search(texto[:20000])
            suj = f"{m.group(1)}CE-SUJ-{m.group(2)}-{m.group(3)}" if m else None
            seccion = f.get("Sala Decisión") or "Sala Plena"
            # El segmentador agrega ", <organo_emisor>" (Consejo de Estado, Sección X): no va en el nombre.
            nombre = (f"Sentencia de unificación {suj}" if suj else
                      f"Sentencia de unificación, radicado {radicado}")
            if fuentes.canonico_de_encabezado(nombre):
                raise ValueError(f"{doc_id}: el extractor oficial lee una cita en {nombre!r}")

            carpeta_raw = rutas.RAW / doc_id
            if carpeta_raw.exists():
                shutil.rmtree(carpeta_raw)
            carpeta_raw.mkdir(parents=True)
            archivos = []
            for origen in (doc, html):
                shutil.copy2(origen, carpeta_raw / origen.name)
                datos = origen.read_bytes()
                archivos.append({"archivo": origen.name, "bytes": len(datos),
                                 "sha256": hashlib.sha256(datos).hexdigest()})
            if doc.suffix.lower() != ".pdf":
                motor, lineas = lineas_doc(doc)
                (carpeta_raw / "texto.json").write_text(json.dumps(
                    {"motor": motor, "documento": doc.name, "paginas": [lineas]}, ensure_ascii=False, indent=1)
                    + "\n", encoding="utf-8", newline="\n")
            (carpeta_raw / "_descarga.json").write_text(json.dumps({
                "doc_id": doc_id, "url": URL_SAMAI, "parser": "pdf_sentencia", "fecha_consulta": hoy,
                "paginas": [doc.name], "archivos": archivos, "completo": True,
                "origen": "exportación de SAMAI (consejo_estado.zip)", "radicado": radicado,
                "ficha": {k: f.get(k) for k in ("Sala Decisión", "Despacho", "Tipo", "Providencia del",
                                                "Decisión", "Clase del proceso")},
            }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            registros.append({
                "doc_id": doc_id, "nombre_citable": nombre, "tipo": "sentencia", "numero": suj or radicado,
                "anio": (fecha or "")[:4] or None, "organo_emisor": f"Consejo de Estado, {seccion}",
                "fuente": "SAMAI (Consejo de Estado)", "donde_buscar": f"{URL_SAMAI} · radicado {radicado}",
                "url": URL_SAMAI, "items_del_banco": None,
                "areas": _SECCION_AREAS.get(seccion, ["administrativo"]), "canonico": None,
                "origen": "samai_unificacion", "prioridad": "media", "ola": 3, "estado": "pendiente",
                "justificacion": f"Sentencia de unificación ({fecha}). {f.get('Titulación', '')[:200]}".strip(),
            })
            print(f"ok             {doc_id:42s} {suj or '-':18s} {seccion:16s} {fecha} {doc.suffix.lower()}")
        registros.sort(key=lambda d: d["doc_id"])
        fuentes.guardar_archivo(ARCHIVO_FUENTES, ENCABEZADO, registros)
        return registros
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--zip", type=Path, required=True)
    args = ap.parse_args()
    regs = importar(args.zip)
    print(f"{len(regs)} sentencias en {ARCHIVO_FUENTES.relative_to(rutas.RAIZ)}")


if __name__ == "__main__":
    main()
