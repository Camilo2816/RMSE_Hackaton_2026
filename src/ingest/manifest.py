"""Genera corpus_manifest.json desde lo que realmente hay en corpus/processed/.

Un registro por documento procesado, con los campos de la plantilla oficial
(doc_id, titulo, fuente, url, fecha_consulta, areas, n_articulos, n_fragmentos,
metodo_ingesta, sha256). Nadie lo edita a mano: si cambia el corpus, se regenera.
Conserva de la versión anterior los campos de nivel superior que no calcula
(equipo, licencia, enlace_nube).

    python -m src.ingest.manifest
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import date
from typing import Any
from urllib.parse import urlparse

from src.common import rutas
from src.ingest import fuentes

if str(rutas.SCRIPTS) not in sys.path:
    sys.path.insert(0, str(rutas.SCRIPTS))
from common import AREA_SLUG  # noqa: E402  scripts/common.py, sin modificar

AREA_NOMBRE = {slug: nombre for nombre, slug in AREA_SLUG.items()}

METODO = {
    "senado": "parser HTML (basedoc del Senado, páginas encadenadas + notas de vigencia en JS) "
              "+ segmentación por artículo",
    "corte_constitucional": "parser HTML (relatoría) + segmentación por sección",
    "pdf": "extracción de texto de PDF + segmentación por artículo",
    "pdf_sentencia": "extracción de texto de PDF (relatoría de la Corte Suprema) + segmentación por sección",
    "funcion_publica": "parser HTML (Gestor Normativo de Función Pública) + segmentación por artículo",
    "sfc_cbj": "zip de la SFC (un archivo por capítulo o anexo: DOC con antiword, DOCX, PDF) "
               "+ segmentación por numeral de segundo nivel",
    "legalize": "parser Markdown (legalize-co: texto consolidado de SUIN-Juriscol, fijado a un commit) "
                "+ segmentación por artículo",
}


# La fuente declarada es la de la URL efectiva (la del YAML es la de planeación).
FUENTE_DE_HOST = {
    "secretariasenado.gov.co": "Secretaría del Senado",
    "corteconstitucional.gov.co": "Relatoría de la Corte Constitucional",
    "cortesuprema.gov.co": "Relatoría de la Corte Suprema de Justicia",
    "funcionpublica.gov.co": "Función Pública (Gestor Normativo)",
    "comunidadandina.org": "Comunidad Andina",
    "cancilleria.gov.co": "Cancillería (normograma)",
    "normograma.dian.gov.co": "DIAN (normograma)",
    "raw.githubusercontent.com": "SUIN-Juriscol (vía legalize-co)",
    "samai.consejodeestado.gov.co": "SAMAI (Consejo de Estado)",
    "superfinanciera.gov.co": "Superintendencia Financiera de Colombia",
    "alcaldiabogota.gov.co": "Alcaldía de Bogotá (SISJUR)",
    "suin-juriscol.gov.co": "SUIN-Juriscol",
}


def fuente_de(url: str, declarada: str | None) -> str | None:
    host = urlparse(url or "").netloc
    return next((n for h, n in FUENTE_DE_HOST.items() if host.endswith(h)), declarada)


def _leer_jsonl(path) -> list[dict[str, Any]]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def construir() -> dict[str, Any]:
    docs = fuentes.cargar()
    previo = json.loads(rutas.MANIFEST.read_text(encoding="utf-8")) if rutas.MANIFEST.exists() else {}
    previos = {r["doc_id"]: r for r in previo.get("documentos", [])}
    registros = []
    for path in sorted(rutas.FRAGMENTOS_DIR.glob("*.jsonl")):
        d = docs.get(path.stem)
        if not d or d.get("estado") == "excluido":
            continue
        frags = _leer_jsonl(path)
        txt = (rutas.PROCESSED / f"{path.stem}.txt").read_bytes()
        if not ((rutas.RAW / path.stem / "_descarga.json").exists()
                and (rutas.INTERIM / f"{path.stem}.json").exists()):
            # Sin originales o sin intermedio (corpus_snapshot.zip solo trae processed/): vale la
            # entrada previa mientras el texto procesado sea el mismo que ella declara.
            r = previos.get(path.stem)
            if not r or r["sha256"] != hashlib.sha256(txt).hexdigest():
                raise FileNotFoundError(f"{path.stem}: sin corpus/raw/ y sin entrada previa con el mismo sha256")
            registros.append({**r, "fuente": fuente_de(r["url"], r.get("fuente"))})
            continue
        descarga = json.loads((rutas.RAW / path.stem / "_descarga.json").read_text(encoding="utf-8"))
        interim = json.loads((rutas.INTERIM / f"{path.stem}.json").read_text(encoding="utf-8"))
        articulos = {f["frag_id"].rsplit(":", 1)[0] for f in frags if f.get("articulo")}
        titulo = d["nombre_citable"]
        if interim.get("epigrafe"):
            titulo = f"{titulo}. {interim['epigrafe']}"
        url = interim.get("fuente_original") or descarga["url"]  # legalize-co: la URL oficial de SUIN
        registros.append({
            "doc_id": d["doc_id"],
            "titulo": titulo,
            "fuente": fuente_de(descarga["url"], d.get("fuente")),
            "url": url,
            **({"url_descarga": descarga["url"]} if url != descarga["url"] else {}),
            "fecha_consulta": descarga["fecha_consulta"],
            "areas": [AREA_NOMBRE.get(a, a) for a in d.get("areas") or []],
            "n_articulos": len(articulos) or None,
            "n_fragmentos": len(frags),
            "metodo_ingesta": METODO.get(descarga["parser"], descarga["parser"]),
            "sha256": hashlib.sha256(txt).hexdigest(),
            "tipo": d.get("tipo"),
            "norma": d["nombre_citable"],
            "canonico": d.get("canonico"),
            "paginas_descargadas": len(descarga["paginas"]),
            "ola": d.get("ola"),
        })
    return {
        "equipo": previo.get("equipo", ""),
        "licencia": previo.get("licencia", "CC-BY-4.0"),
        "fecha_generacion": date.today().isoformat(),
        "enlace_nube": previo.get("enlace_nube", ""),
        "n_documentos": len(registros),
        "n_fragmentos": sum(r["n_fragmentos"] for r in registros),
        "documentos": registros,
    }


def main() -> None:
    m = construir()
    rutas.MANIFEST.write_text(json.dumps(m, ensure_ascii=False, indent=2) + "\n",
                              encoding="utf-8", newline="\n")
    print(f"corpus_manifest.json: {m['n_documentos']} documentos, {m['n_fragmentos']} fragmentos")


if __name__ == "__main__":
    main()
