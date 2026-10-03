"""Exporta informe/INFORME_TECNICO.md a informe/INFORME_TECNICO.pdf (carta, márgenes de 2 cm, 10,5 pt).

Usa la librería `markdown` (pip install markdown) y Microsoft Edge en modo headless para imprimir
el HTML a PDF. Al final informa el número de páginas: el enunciado admite como máximo 3.

    python tools/informe_pdf.py
"""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

import markdown
import pymupdf

RAIZ = Path(__file__).resolve().parents[1]
MD = RAIZ / "informe" / "INFORME_TECNICO.md"
PDF = RAIZ / "informe" / "INFORME_TECNICO.pdf"
EDGE = [Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe")]
CSS = """@page{size:Letter;margin:2cm}
body{font-family:'Calibri','Segoe UI',Arial,sans-serif;font-size:10.5pt;line-height:1.3;color:#000}
h1{font-size:16pt;margin:0 0 4pt} h2{font-size:12.5pt;margin:10pt 0 3pt} p,li{margin:3pt 0}
table{border-collapse:collapse;width:100%;font-size:9pt;margin:4pt 0}
th,td{border:1px solid #888;padding:2pt 4pt;vertical-align:top}
code{font-family:Consolas,monospace;font-size:9pt} ol,ul{margin:2pt 0 2pt 18pt;padding:0}"""


def main() -> int:
    texto = re.sub(r"<!--.*?-->", "", MD.read_text(encoding="utf-8"), flags=re.S)
    texto = re.sub(r"\*\*\n\*\*", "**  \n**", texto)  # renglones en negrita seguidos: salto de línea
    html = (f'<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Informe técnico</title>'
            f"<style>{CSS}</style></head><body>{markdown.markdown(texto, extensions=['tables'])}</body></html>")
    edge = next((e for e in EDGE if e.exists()), None)
    if edge is None:
        sys.exit("No se encontró Microsoft Edge; abra el HTML en un navegador e imprima a PDF.")
    with tempfile.TemporaryDirectory() as tmp:
        pagina = Path(tmp) / "informe.html"
        pagina.write_text(html, encoding="utf-8")
        subprocess.run([str(edge), "--headless", "--disable-gpu", "--no-pdf-header-footer",
                        f"--print-to-pdf={PDF}", pagina.as_uri()], check=True, capture_output=True)
    paginas = len(pymupdf.open(PDF))
    print(f"{PDF.relative_to(RAIZ)}: {paginas} páginas" + ("" if paginas <= 3 else " — SUPERA EL MÁXIMO DE 3"))
    return 0 if paginas <= 3 else 1


if __name__ == "__main__":
    sys.exit(main())
