"""Declara el enlace público del corpus e índice en README.md y corpus_manifest.json.

Escribe la URL y el tamaño de corpus/dist/corpus_RMSE.zip en la tabla de "## Corpus e índice"
del README y en `enlace_nube` del manifiesto (y en la copia de la raíz; el zip ya publicado no
cambia).

    python tools/poner_enlace.py "https://..."
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
ZIP = RAIZ / "corpus" / "dist" / "corpus_RMSE.zip"


def main() -> None:
    if len(sys.argv) != 2 or not sys.argv[1].startswith("http"):
        sys.exit('uso: python tools/poner_enlace.py "https://..."')
    url = sys.argv[1]
    tam = f"{ZIP.stat().st_size / 1e9:.1f} GB".replace(".", ",") if ZIP.exists() else ""

    readme = RAIZ / "README.md"
    texto = readme.read_text(encoding="utf-8")
    fila = re.compile(r"^\| Corpus procesado e índice vectorial \|.*$", re.M)
    if not fila.search(texto):
        sys.exit("No encontré la fila 'Corpus procesado e índice vectorial' en README.md")
    texto = fila.sub(f"| Corpus procesado e índice vectorial | {url} | {tam} | CC-BY-4.0 |", texto)
    readme.write_text(texto, encoding="utf-8", newline="\n")

    ruta = RAIZ / "corpus_manifest.json"
    manifiesto = json.loads(ruta.read_text(encoding="utf-8"))
    manifiesto["enlace_nube"] = url
    ruta.write_text(json.dumps(manifiesto, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"README.md y corpus_manifest.json: enlace {url} ({tam})")


if __name__ == "__main__":
    main()
