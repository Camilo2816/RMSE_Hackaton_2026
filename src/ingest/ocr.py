"""OCR de PDF escaneados: corpus/raw/<doc_id>/<pdf> -> corpus/raw/<doc_id>/ocr.json.

Para sentencias publicadas como imagen o con una capa de texto ilegible (SC18392-2017:
"Repdbl i cadeCol ombi a..."). Motor abierto: EasyOCR (Apache 2.0), modelo latino
en español, en GPU si hay. Solo corre en la ingesta: el resultado queda en
corpus/raw/ y parsers/pdf_sentencia.py lo usa en lugar de la capa de texto del PDF.

Cada página se renderiza a `--dpi` y las cajas de texto se agrupan en líneas por
la posición vertical (centro de la caja dentro de media altura de línea), de
izquierda a derecha. Determinista para una misma versión de motor y modelo.

    python -m src.ingest.ocr --ids sentencia_sc_18392_2017 [--dpi 300]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pymupdf

from src.common import rutas

ARCHIVO = "ocr.json"


def _lineas_de(cajas: list[tuple[list, str, float]]) -> list[str]:
    """Agrupa las cajas de EasyOCR ([[x,y]x4], texto, confianza) en líneas de lectura."""
    items = []
    for caja, texto, _ in cajas:
        ys = [p[1] for p in caja]
        xs = [p[0] for p in caja]
        items.append(((min(ys) + max(ys)) / 2, max(ys) - min(ys), min(xs), texto))
    items.sort(key=lambda t: (t[0], t[2]))
    lineas: list[list[tuple]] = []
    for it in items:
        if lineas and abs(it[0] - lineas[-1][0][0]) <= max(lineas[-1][0][1], it[1]) / 2:
            lineas[-1].append(it)
        else:
            lineas.append([it])
    return [" ".join(t[3] for t in sorted(l, key=lambda t: t[2])).strip() for l in lineas]


def ocr_pdf(pdf: Path, dpi: int = 300) -> dict[str, Any]:
    import easyocr
    import torch

    lector = easyocr.Reader(["es"], gpu=torch.cuda.is_available(), verbose=False)
    paginas = []
    for pagina in pymupdf.open(pdf):
        pix = pagina.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
        paginas.append(_lineas_de(lector.readtext(img, detail=1, paragraph=False)))
    return {"motor": f"easyocr {easyocr.__version__}", "idiomas": ["es"], "dpi": dpi,
            "pdf": pdf.name, "paginas": paginas}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ids", nargs="+", required=True)
    ap.add_argument("--dpi", type=int, default=300)
    args = ap.parse_args()
    for doc_id in args.ids:
        carpeta = rutas.RAW / doc_id
        info = json.loads((carpeta / "_descarga.json").read_text(encoding="utf-8"))
        salida = ocr_pdf(carpeta / info["paginas"][0], args.dpi)
        (carpeta / ARCHIVO).write_text(json.dumps(salida, ensure_ascii=False, indent=1) + "\n",
                                       encoding="utf-8", newline="\n")
        n = sum(len(p) for p in salida["paginas"])
        print(f"ok             {doc_id:40s} {len(salida['paginas'])} págs · {n} líneas · {salida['motor']}")


if __name__ == "__main__":
    main()
