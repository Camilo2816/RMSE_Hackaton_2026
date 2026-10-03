"""Importa docs/inventario_fuentes_corpus.xlsx a sources/*.yaml.

El xlsx es la vista de planeación del equipo (prioridad, estado, justificación);
sources/*.yaml es lo que consume la ingesta. Este script:

1. Empata cada fila de la hoja "Inventario completo" con un documento de
   sources/ por su cuerpo normativo canónico (tupla de scripts/citations.py), no
   por doc_id: el xlsx usa otra convención (ley_1564_2012 vs codigo_general_proceso).
2. A los empatados les añade prioridad, justificación y estado.
3. Crea los que faltan, con doc_id en snake_case y nombre_citable verificado
   contra el extractor oficial.
4. Asigna la ola de ingesta (0 piloto, 1 códigos, 2 seed + altas, 3 resto).

Idempotente: correrlo dos veces deja los YAML iguales.

    python -m src.ingest.importar_inventario [--dry-run]
"""
from __future__ import annotations

import argparse
import re
import unicodedata
from collections import Counter
from typing import Any

import openpyxl

from src.common import rutas
from src.ingest import fuentes
from src.ingest.fuentes import Doc

HOJA = "Inventario completo"

OLA0 = {"constitucion", "codigo_general_proceso", "ley_472_1998"}
# Además de los cuerpos de citations.CODES: los más citados del seed fuera de ellos.
OLA1_EXTRA = {("ley", "80", "1993"), ("ley", "2220", "2022"),
              ("decreto", "2153", "1992"), ("ley", "1116", "2006")}

TIPOS = {
    "sentencia": "sentencia", "ley": "ley", "decreto": "decreto", "código": "codigo",
    "decisión andina": "decision_andina", "constitución": "constitucion",
    "acuerdo": "acuerdo", "doctrina": "doctrina", "auto": "auto",
    "resolución": "resolucion", "decisión administrativa": "decision_administrativa",
}
# Tipos cuyo número no reconoce scripts/citations.py: nunca suman en citación.
TIPOS_EXCLUIDOS = {
    "doctrina": "Doctrina administrativa: no es norma citable por el extractor oficial "
                "y su volumen es alto frente a su aporte.",
    "auto": "Auto de superintendencia: el extractor oficial no lo reconoce como cita.",
    "decision_administrativa": "Decisiones administrativas masivas: sin cita extraíble "
                               "por el extractor oficial.",
}
FUENTES = {
    "Relatoría Corte Constitucional": "Relatoría de la Corte Constitucional",
    "Relatoría Corte Suprema de Justicia": "Relatoría de la Corte Suprema de Justicia",
    "Relatoría Consejo de Estado": "Relatoría del Consejo de Estado",
}
# Encabezados duales, revisados a mano (ver fuentes.norma_de).
ALIAS_CITABLES = {
    "ley_2452_2025": ["Código Procesal del Trabajo y de la Seguridad Social"],
    "codigo_procesal_trabajo": ["Decreto Ley 2158 de 1948"],
}
# Documentos que el xlsx da por identificados pero requieren confirmación humana.
VERIFICAR = {
    "sentencia_t_256_2025": "La pregunta de muestra nombra 't-256' sin año; confirmar que "
                            "es la T-256 de 2025 antes de ingerirla.",
}
# Documentos "por verificar" en el xlsx que el equipo ya confirmó (y su motivo).
CONFIRMADOS = {
    "sentencia_c_1141_2000": "Confirmada por el equipo: responsabilidad del productor y derechos del consumidor.",
    "sentencia_c_591_2005": "Confirmada por el equipo: sistema penal acusatorio y juez de control de garantías.",
    "sentencia_c_71_2015": "Confirmada por el equipo: adopción complementaria homoparental.",
    "sentencia_c_816_2011": "Confirmada por el equipo: extensión de la jurisprudencia de unificación (CPACA).",
    "sentencia_c_93_2001": "Confirmada por el equipo: juicio integrado de igualdad, edad para adoptar.",
}
# Erratas de año o número del seed/xlsx corregidas por el equipo: canónico citado -> real.
CORRECCIONES = {
    ("ley", "1692", "2017"): ("ley", "1692", "2013"),  # no existe una Ley 1692 de 2017
}
SALAS_CSJ = {"SL": "Laboral", "SC": "Civil", "SP": "Penal", "STC": "Civil", "STL": "Laboral"}


def _slug(s: str) -> str:
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def _clave(c) -> tuple:
    """Clave de empate: el extractor compara números como texto ("046" != "46"), pero
    el xlsx y el seed no siempre escriben igual el mismo documento."""
    tipo, num, anio = c
    clave = (tipo, str(int(num)) if num and num.isdigit() else num, anio)
    return CORRECCIONES.get(clave, clave)


def _cita_desde_id(excel_id: str) -> str | None:
    """Cita textual a partir del doc_id del xlsx (ley_599_2000 -> 'Ley 599 de 2000')."""
    m = re.fullmatch(r"(ley|decreto|resolucion|acuerdo)_(\d+)_(\d{4})", excel_id)
    if m:
        tipo = {"resolucion": "Resolución"}.get(m.group(1), m.group(1).capitalize())
        return f"{tipo} {int(m.group(2))} de {m.group(3)}"
    m = re.fullmatch(r"sentencia_([a-z]+)-(\d+)_(\d{4})", excel_id)
    if m:
        return f"Sentencia {m.group(1).upper()}-{m.group(2)} de {m.group(3)}"
    return None


def _nombre_sentencia(sala: str, numero: int, anio: str) -> str:
    # Forma de cita usual de la Corte Constitucional: número con tres dígitos.
    if sala in ("C", "T", "SU"):
        return f"Sentencia {sala}-{numero:03d} de {anio}"
    return f"Sentencia {sala}-{numero} de {anio}"


def _nuevo_doc(fila: dict[str, Any], canonico: tuple | None) -> Doc:
    tipo = TIPOS.get(fila["tipo"], _slug(fila["tipo"]))
    titulo = fila["titulo"]
    numero = anio = None
    organo = None
    if canonico and canonico[0] == "jurisprudencia":
        sala, num = canonico[1].split("-")
        numero, anio = f"{sala}-{int(num)}", canonico[2]
        nombre = _nombre_sentencia(sala, int(num), anio)
        doc_id = f"sentencia_{sala.lower()}_{int(num)}_{anio}"
        organo = ("Corte Constitucional" if sala in ("C", "T", "SU")
                  else f"Corte Suprema de Justicia, Sala de Casación {SALAS_CSJ.get(sala, '')}".strip())
    elif canonico and canonico[1]:
        numero, anio = canonico[1], canonico[2]
        nombre = {"resolucion": "Resolución"}.get(canonico[0], canonico[0].capitalize())
        nombre = f"{nombre} {numero} de {anio}"
        doc_id = f"{canonico[0]}_{numero}_{anio}"
        organo = {"ley": "Congreso de la República", "decreto": "Gobierno Nacional"}.get(canonico[0])
    else:
        nombre = re.split(r"\s+·\s+|\s+\(", titulo)[0].strip()
        doc_id = _slug(fila["excel_id"])
        m = re.search(r"(\d{1,5}) de (\d{4})", titulo)
        if m:
            numero, anio = m.group(1), m.group(2)
        if tipo == "decision_andina":
            organo = "Comisión de la Comunidad Andina"
    return {
        "doc_id": doc_id,
        "nombre_citable": nombre,
        "tipo": tipo,
        "numero": numero,
        "anio": anio,
        "organo_emisor": organo,
        "fuente": FUENTES.get(fila["fuente"], fila["fuente"]),
        "donde_buscar": fila["url"] or "",
        "url": "",
        "items_del_banco": None,
        "areas": fila["areas"],
        "canonico": list(canonico) if canonico else None,
        "origen": "inventario_xlsx",
    }


def leer_xlsx() -> list[dict[str, Any]]:
    wb = openpyxl.load_workbook(rutas.INVENTARIO_XLSX, read_only=True, data_only=True)
    filas = []
    for r in wb[HOJA].iter_rows(min_row=4, values_only=True):
        if not r[0]:
            continue
        filas.append({
            "excel_id": r[0], "titulo": r[1], "tipo": r[2], "fuente": r[3], "url": r[4],
            "estado": r[5], "prioridad": r[6], "justificacion": r[7] or "",
            "areas": sorted({_slug(a) for a in (r[8] or "").split(",") if a.strip()}),
        })
    return filas


def candidatos_fila(fila: dict[str, Any]) -> tuple[set[tuple], tuple | None]:
    """(todos los cuerpos que nombra la fila, el canónico propio si es inequívoco).

    El título puede nombrar varias normas ("Código Sustantivo del Trabajo (Decreto
    Ley 2663 de 1950)"): todas sirven para empatar con sources/, pero el canónico de
    un documento nuevo sale del doc_id del xlsx o de un título con una sola norma.
    """
    cita = _cita_desde_id(fila["excel_id"])
    de_cita = fuentes.canonico_de(cita) if cita else set()
    de_titulo = fuentes.canonico_de(fila["titulo"])
    propio = None
    for cuerpos in (de_cita, de_titulo):
        if len(cuerpos) == 1:
            propio = next(iter(cuerpos))
            break
    return de_cita | de_titulo, propio


def estado_de(fila: dict[str, Any], tipo: str) -> tuple[str, str | None]:
    if tipo in TIPOS_EXCLUIDOS:
        return "excluido", TIPOS_EXCLUIDOS[tipo]
    e = fila["estado"]
    if "revisar" in e or "verificar" in e:
        return "por_verificar", None
    return "pendiente", None


def ola_de(d: Doc) -> int:
    if d["doc_id"] in OLA0:
        return 0
    can = tuple(d["canonico"]) if d.get("canonico") else None
    if can and (can[0] in fuentes.oficial.CODES or can in OLA1_EXTRA):
        return 1
    if d.get("origen") in ("seed_targets", "sample_50.legal_basis", "citations.CODES") \
            or d.get("prioridad") == "alta":
        return 2
    return 3


def prioridad_por_defecto(d: Doc) -> str:
    n = d.get("items_del_banco") or 0
    if d.get("origen") in ("citations.CODES", "sample_50.legal_basis") or n >= 5:
        return "alta"
    return "media" if n >= 2 else "baja"


def importar(dry_run: bool = False) -> Counter:
    stats: Counter = Counter()
    por_archivo = {p.stem: fuentes.cargar_archivo(p) for p in fuentes.archivos()}
    existentes: dict[tuple, Doc] = {}
    for _, (_, _, docs) in por_archivo.items():
        for d in docs:
            if d.get("canonico"):
                existentes[_clave(d["canonico"])] = d
    ids = {d["doc_id"] for _, (_, _, docs) in por_archivo.items() for d in docs}

    for fila in leer_xlsx():
        todos, can = candidatos_fila(fila)
        # Primero el canónico propio ("Ley 600 de 2000 (Código de Procedimiento Penal
        # anterior)" es la Ley 600, no el CPP vigente); si no existe, un código nombrado
        # en el título ("Código Sustantivo del Trabajo (Decreto Ley 2663 de 1950)").
        # Otras normas del título no empatan: "Reglamentario del Decreto 2591 de 1991
        # (Decreto 306 de 1992)" es el Decreto 306.
        orden = ([can] if can else []) + sorted(c for c in todos if c[1] is None)
        d = next((existentes[_clave(c)] for c in orden if _clave(c) in existentes), None)
        if d is None:
            d = _nuevo_doc(fila, can)
            if d["doc_id"] in ids:
                stats["id_repetido_omitido"] += 1
                continue
            areas = [a for a in d["areas"] if a in fuentes.PESO_AREA] or ["transversales"]
            destino = min(areas, key=lambda a: fuentes.PESO_AREA.get(a, 0))
            por_archivo[destino][2].append(d)
            ids.add(d["doc_id"])
            if can:
                existentes[_clave(can)] = d
            stats["nuevos"] += 1
        else:
            stats["empatados"] += 1
        estado, motivo = estado_de(fila, d["tipo"])
        if d["doc_id"] in VERIFICAR:
            estado, motivo = "por_verificar", VERIFICAR[d["doc_id"]]
        if d["doc_id"] in CONFIRMADOS:
            estado, motivo = "pendiente", None
            d["nota_verificacion"] = CONFIRMADOS[d["doc_id"]]
        d["prioridad"] = fila["prioridad"] if fila["prioridad"] in fuentes.PRIORIDADES else "baja"
        d["estado"] = estado
        d["justificacion"] = fila["justificacion"]
        if motivo:
            d["motivo_exclusion" if estado == "excluido" else "nota_verificacion"] = motivo
        if estado == "por_verificar":
            stats["por_verificar"] += 1

    for _, (_, _, docs) in por_archivo.items():
        for d in docs:
            d.setdefault("prioridad", prioridad_por_defecto(d))
            d.setdefault("estado", "pendiente")
            d.setdefault("justificacion", "")
            if d["doc_id"] in ALIAS_CITABLES:
                d["alias_citables"] = ALIAS_CITABLES[d["doc_id"]]
            d["ola"] = ola_de(d)
            stats[f"ola_{d['ola']}"] += 1 if d["estado"] != "excluido" else 0
            stats[f"estado_{d['estado']}"] += 1

    if not dry_run:
        # Sin reordenar: los existentes conservan su posición y los nuevos van al final.
        for stem, (enc, _, docs) in por_archivo.items():
            fuentes.guardar_archivo(rutas.SOURCES / f"{stem}.yaml", enc, docs)
    return stats


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    for k, v in sorted(importar(args.dry_run).items()):
        print(f"{k:24s} {v}")


if __name__ == "__main__":
    main()
