"""Importa la Circular Básica Jurídica de la SFC (C.E. 029 de 2014) desde el zip que publica la SFC.

La página oficial (URL_SFC) ofrece la circular como un zip de capítulos y anexos, sin
enlace por archivo. Este módulo reemplaza resolver + descargar para esa fuente:
copia a corpus/raw/circular_externa_029_2014/ los documentos de texto (un archivo
por capítulo o anexo; si viene en DOC/DOCX y en PDF, el editable), sin hojas de
cálculo ni temporales de Word, y escribe _descarga.json con el sha256 de cada uno y
el del zip. La estructura la extrae parsers/sfc_cbj.py.

    python -m src.ingest.importar_sfc --zip "JURIDICA CE29_14.zip"
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import tempfile
import unicodedata
import zipfile
from datetime import date
from pathlib import Path

from src.common import rutas

DOC_ID = "circular_externa_029_2014"
URL_SFC = ("https://www.superfinanciera.gov.co/publicaciones/10083443/"
           "normativanormativa-generalcircular-basica-juridica-ce-10083443/")
_ROMANOS = {"I": 1, "V": 5, "X": 10, "L": 50}
_PREFERENCIA = {".docx": 0, ".doc": 1, ".pdf": 2}


def _romano(s: str) -> int:
    total = 0
    for a, b in zip(s, s[1:] + " "):
        v = _ROMANOS.get(a, 0)
        total += -v if _ROMANOS.get(b, 0) > v else v
    return total


def _clave_orden(rel: Path) -> tuple:
    """PARTE, Título y Capítulo en orden numérico; los anexos detrás de su capítulo."""
    texto = unicodedata.normalize("NFC", str(rel)).replace("­", "")
    nums = [_romano(m) for m in re.findall(r"(?:PARTE|T[íi]t(?:ulo)?|Cap)\s+([IVXL]+)\b", texto)]
    anexo = re.search(r"Anexo\s*(\d+)", texto, re.I)
    return (*nums, *([0] * (3 - len(nums))), 1 if anexo else 0, int(anexo.group(1)) if anexo else 0, texto)


def importar(zip_path: Path) -> dict:
    destino = rutas.RAW / DOC_ID
    with tempfile.TemporaryDirectory(dir=rutas.RAIZ) as tmp:
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(tmp)
        raiz = next(Path(tmp).iterdir())
        tallos: dict[tuple, Path] = {}
        for p in raiz.rglob("*"):
            if not p.is_file() or p.name.startswith("~$") or p.suffix.lower() not in _PREFERENCIA:
                continue
            if re.match(r"Tabla de Contenido General", p.name, re.I):  # índice de toda la circular, sin texto
                continue
            clave = (p.parent, unicodedata.normalize("NFC", p.stem.replace("­", "")).lower())
            if clave not in tallos or _PREFERENCIA[p.suffix.lower()] < _PREFERENCIA[tallos[clave].suffix.lower()]:
                tallos[clave] = p
        elegidos = sorted((p.relative_to(raiz) for p in tallos.values()), key=_clave_orden)
        if destino.exists():
            shutil.rmtree(destino)
        archivos = []
        for rel in elegidos:
            (destino / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(raiz / rel, destino / rel)
            datos = (raiz / rel).read_bytes()
            archivos.append({"archivo": rel.as_posix(), "bytes": len(datos),
                             "sha256": hashlib.sha256(datos).hexdigest()})
    info = {"doc_id": DOC_ID, "url": URL_SFC, "parser": "sfc_cbj", "fecha_consulta": date.today().isoformat(),
            "paginas": [a["archivo"] for a in archivos], "archivos": archivos, "completo": True,
            "origen": f"zip publicado por la SFC ({zip_path.name})",
            "sha256_zip": hashlib.sha256(zip_path.read_bytes()).hexdigest()}
    (destino / "_descarga.json").write_text(json.dumps(info, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return info


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--zip", type=Path, required=True)
    info = importar(ap.parse_args().zip)
    print(f"ok             {DOC_ID:40s} {len(info['paginas'])} archivos")


if __name__ == "__main__":
    main()
