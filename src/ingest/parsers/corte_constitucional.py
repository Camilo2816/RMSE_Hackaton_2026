"""Parser de la relatoría de la Corte Constitucional (HTML exportado de Word).

Estructura común verificada en sentencias de 1992 a 2025 (T-406/92, T-025/04,
C-355/06, C-145/18, C-207/19, T-323/24, SU-277/25):

1. Descriptores de la relatoría: "TEMA-Subtema" seguidos de un extracto. Es un
   resumen de la propia Corte, muy útil para recuperar.
2. Encabezado: Referencia/expediente, Magistrado(s) ponente(s), fecha, y en las
   recientes una "Síntesis de la decisión".
3. "SENTENCIA" y el cuerpo con secciones en romanos: ANTECEDENTES, (NORMA
   DEMANDADA, DEMANDA, INTERVENCIONES, CONCEPTO DEL PROCURADOR, PRUEBAS),
   CONSIDERACIONES, DECISIÓN / RESUELVE.
4. Firmas, salvamentos y aclaraciones de voto, anexos, constancias.
5. Notas al pie de Word (`div#ftnN`) y sus llamadas `[N]`: se quitan.

Salida (ver `parsear_documento`): ficha (metadatos + resuelve), descriptores y
secciones con párrafos anotados con su subtítulo, más un bloque `qa`.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import lxml.html

from src.ingest.red import decodificar, sin_scripts

SECCIONES: list[tuple[str, str]] = [
    ("sintesis", r"S[IÍ]NTESIS DE LA DECISI[OÓ]N"),
    ("salvamento_voto", r"SALVAMENTO"),
    ("aclaracion_voto", r"ACLARACI[OÓ]N"),
    ("anexo", r"(?:[IÍ]NDICE DE )?ANEXOS?\b"),
    ("concepto_procurador", r"CONCEPTO DEL? (?:SE[NÑ]OR )?(?:PROCURADOR|MINISTERIO P[UÚ]BLICO|VISTA FISCAL)"),
    ("norma_demandada", r"(?:NORMAS?|DISPOSICI[OÓ]N(?:ES)?|TEXTOS?)(?: LEGAL(?:ES)?)? (?:DEMANDAD|ACUSAD|OBJETO|REVISAD)"),
    ("demanda", r"(?:LA |LAS )?DEMANDAS?\b|CARGOS? DE LA DEMANDA|FUNDAMENTOS DE LA DEMANDA"),
    ("intervenciones", r"INTERVENCI[OÓ]N|INTERVENCIONES|INTERVINIENTES|CONCEPTOS? (?:RECAUDAD|T[EÉ]CNIC)"),
    ("pruebas", r"PRUEBAS|ACTUACI[OÓ]N(?:ES)? EN SEDE DE REVISI[OÓ]N"),
    ("antecedentes", r"ANTEC\w{0,5}DENTES"),  # la relatoría trae "ANTECENDENTES", "ANTECEDEDENTES"
    ("consideraciones", r"CONSIDERACIONES|FUNDAMENTOS? JUR[IÍ]DICOS?|CONSIDERANDO"),
    ("decision", r"DECISI[OÓ]N|RESUELVE"),
]
NOMBRE_SECCION = {
    "ficha": "Ficha", "descriptores": "Descriptores de la relatoría",
    "sintesis": "Síntesis de la decisión", "antecedentes": "Antecedentes",
    "norma_demandada": "Norma demandada", "demanda": "Demanda",
    "intervenciones": "Intervenciones", "concepto_procurador": "Concepto del Procurador",
    "pruebas": "Pruebas", "consideraciones": "Consideraciones", "decision": "Decisión",
    "salvamento_voto": "Salvamento de voto", "aclaracion_voto": "Aclaración de voto",
    "anexo": "Anexo", "cuerpo": "Texto",
    # Compilaciones de la Relatoría de la Corte Suprema (parsers/relatoria_csj.py).
    "extracto": "Extracto temático", "providencia": "Reseña de la Relatoría",
}
# Una vez dentro de un voto particular o de un anexo, solo otro de ellos cambia de sección.
_TERMINALES = {"salvamento_voto", "aclaracion_voto", "anexo"}
# Orden natural de una sentencia: un título de sección solo abre sección si avanza en
# este orden ("5. ANTECEDENTES JURISPRUDENCIALES" dentro de las consideraciones no
# devuelve a los antecedentes).
ORDEN = {"cuerpo": 0, "sintesis": 1, "antecedentes": 2, "norma_demandada": 3, "demanda": 4,
         "intervenciones": 5, "concepto_procurador": 6, "pruebas": 7, "consideraciones": 8,
         "decision": 9, "salvamento_voto": 10, "aclaracion_voto": 10, "anexo": 10}

_PREFIJO = r"^(?:(?:[IVXL]+|\d{1,2}|[A-H])\s*[.\-–)]+\s*)?"
# Líneas de índice: "I. ANTECEDENTES.......... 16", "III. ANTECENDENTES. 4", "V. DECISIÓN.. 70"
_INDICE = re.compile(r"\.{6,}\s*\d*\s*$|…{3,}|^(?:[IVXL]+|\d{1,2})\s*\.\s+[^.]{3,100}?\.+\s*\d{1,3}\s*$")
_ESPACIADO = re.compile(r"(?:[A-ZÁÉÍÓÚÑ]{1,2}\s+){3,}[A-ZÁÉÍÓÚÑ]{1,2}\s*:?")  # "R E S U E LV E"
_CIERRE = re.compile(r"^(?:C[oó]piese|Notif[ií]quese|Comun[ií]quese|C[uú]mplase|Publ[ií]quese)", re.I)
_CONSTANCIA = re.compile(r"^(?:EL|LA) (?:SUSCRITO|SUSCRITA)\b|^HACE CONSTAR", re.I)
_BOILERPLATE = re.compile(
    r"^(?:TEMAS?-SUBTEMAS?|REP[UÚ]BLICA DE COLOMBIA|CORTE CONSTITUCIONAL|Sala (?:Plena|\w+ de Revisi[oó]n.*)"
    r"|EN NOMBRE DEL PUEBLO|POR MANDATO DE LA CONSTITUCI[OÓ]N|Y POR MANDATO DE LA CONSTITUCI[OÓ]N)\.?$", re.I)


def _limpio(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("\xa0", " ")).strip()


def parrafos(html: str) -> list[str]:
    """Párrafos del cuerpo en orden, sin notas al pie, llamadas [N] ni índices."""
    html = sin_scripts(html)
    doc = lxml.html.document_fromstring(html)
    for el in doc.xpath("//head|//style|//div[starts-with(@id,'ftn')]|//div[starts-with(@id,'edn')]"
                        "|//a[starts-with(@href,'#_ftn')]|//a[starts-with(@href,'#_edn')]"):
        el.drop_tree()
    out = []
    for el in doc.xpath("//body//p|//body//h1|//body//h2|//body//h3|//body//h4|//body//h5|//body//h6"):
        if el.xpath("ancestor::p"):
            continue
        t = _limpio(el.text_content())
        if _ESPACIADO.fullmatch(t):
            t = t.replace(" ", "")
        if t and not _INDICE.search(t):
            out.append(t)
    return out


def seccion_de(texto: str) -> str | None:
    """Sección de primer nivel si el párrafo es su título ("II. CONSIDERACIONES").

    Solo cuentan títulos con numeral romano o escritos en mayúsculas sin numeral:
    "13. Intervención ciudadana..." o "C. Decisión a revisar" son subtítulos.
    """
    t = texto.strip(" .:")
    if len(t) > 130:
        return None
    mayus = t.upper()
    letras = re.sub(r"[^A-Za-zÁÉÍÓÚÑáéíóúñ]", "", t)
    en_mayusculas = bool(letras) and letras.isupper()
    # Numeral romano; o arábigo si el título va en mayúsculas ("3. CONSIDERACIONES").
    romano = re.match(r"^[IVXL]+\s*[.\-–)]+\s*", mayus) or \
        (re.match(r"^\d{1,2}\s*[.\-–)]+\s*", mayus) if en_mayusculas else None)
    cuerpo = mayus[romano.end():] if romano else mayus
    for nombre, patron in SECCIONES:
        if not re.match(patron, cuerpo):
            continue
        if nombre == "sintesis":
            return nombre if romano or len(t) <= 40 else None
        if nombre in ("salvamento_voto", "aclaracion_voto"):
            # "SALVAMENTO DE VOTO DEL MAGISTRADO", "ACLARACION DE VOTO A LA Sentencia..."
            return nombre if re.match(r"(?:SALVAMENTO|ACLARACI[OÓ]N)\b", t) and "VOTO" in mayus else None
        if nombre == "anexo":
            return nombre if en_mayusculas and len(cuerpo) <= 40 else None
        if romano or (en_mayusculas and len(t) <= 70):
            return nombre
        return None
    return None


def es_subtitulo(texto: str) -> bool:
    if len(texto) > 120 or texto.endswith((".", ";", ",")) and not texto.isupper():
        return False
    numerado = re.match(r"^(?:[IVXL]+|\d+(?:\.\d+)*|[a-h])\s*[.\-–)]\s*\S", texto)
    letras = re.sub(r"[^A-Za-zÁÉÍÓÚÑáéíóúñ]", "", texto)
    mayusculas = bool(letras) and letras.isupper() and len(letras) >= 6
    return bool(numerado) or mayusculas


def _ficha(encabezado: list[str]) -> dict[str, Any]:
    """Metadatos del encabezado: ponente(s), fecha, referencia, asunto; y descriptores."""
    ficha: dict[str, Any] = {"ponentes": [], "fecha": None, "referencia": None, "otros": []}
    descriptores: list[str] = []
    en_ponentes = False
    for i, p in enumerate(encabezado):
        if _BOILERPLATE.match(p) or re.match(r"^Sentencia (?:No\.? )?[A-Z]+[-.]?\s*\d+", p, re.I) \
                and len(p) < 40:
            continue
        m = re.match(r"^Magistrad[oa]s?\s+(?:\(e\)\s+)?(?:ponentes?|sustanciador(?:a|as|es)?)\s*:?\s*(.*)$",
                     p, re.I)
        if m:
            en_ponentes = True
            if m.group(1) and _es_nombre(m.group(1)):
                ficha["ponentes"].append(re.sub(r"^Dr[a]?\.\s*", "", m.group(1)).strip(" ."))
            continue
        if re.match(r"^(?:Bogot[aá]|Santa ?Fe de Bogot[aá]).{0,15}\(?\d|^(?:Bogot[aá]).*\(\d{4}\)", p) \
                and ficha["fecha"] is None and len(p) < 160:
            ficha["fecha"] = p.strip(" .")
            en_ponentes = False
            continue
        if en_ponentes and _es_nombre(p) and len(ficha["ponentes"]) < 3:
            ficha["ponentes"].append(re.sub(r"^Dr[a]?\.\s*", "", p).strip(" ."))
            continue
        en_ponentes = False
        if re.match(r"^(?:Referencia|Ref\.|Expediente|Radicaci[oó]n)\b", p, re.I) and not ficha["referencia"]:
            ficha["referencia"] = p
        elif re.match(r"^(?:Asunto|Temas?|Demandantes?|Accionantes?|Accionad[oa]s?|Actor(?:es)?)\s*:", p, re.I):
            ficha["otros"].append(p)
        elif re.match(r"^(?:La Sala|La Corte|El Pleno)\b.*(?:profer|dict)", p):
            continue
        elif not ficha["referencia"]:
            descriptores.append(p)  # antes de la referencia: descriptores de la relatoría
        else:
            ficha["otros"].append(p)
    if ficha["fecha"] is None:  # "SENTENCIA DE JUNIO 5 DE 1992" (relatoría antigua)
        ficha["fecha"] = next((p.strip(" .") for p in encabezado if len(p) < 120 and re.search(
            r"\b(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|"
            r"noviembre|diciembre)\b.*\b(?:19|20)\d\d\b", p, re.I)), None)
    return {"ficha": ficha, "descriptores": descriptores}


def _es_nombre(p: str) -> bool:
    """Línea con el nombre de un magistrado (no un título ni una frase)."""
    palabras = re.sub(r"^Dr[a]?\.\s*", "", p).split()
    return (2 <= len(palabras) <= 12 and not p.endswith((":", "?")) and seccion_de(p) is None
            and all(w[:1].isupper() or w.lower() in ("de", "del", "la", "y", "e", "(e)")
                    for w in palabras))


def parsear_documento(carpeta: Path, paginas: list[str]) -> dict[str, Any]:
    ps = parrafos(decodificar((carpeta / paginas[0]).read_bytes()))
    i_sent = next((i for i, p in enumerate(ps[:400]) if re.fullmatch(r"SENTENCIA\.?", p.strip())), None)
    if i_sent is None:
        # Sin marcador: el cuerpo empieza en el primer título numerado de sección (los
        # descriptores iniciales también van en mayúsculas, pero sin numeral), o tras la fecha.
        i_sent = next((i for i, p in enumerate(ps) if seccion_de(p) not in (None, "sintesis")
                       and re.match(r"^(?:[IVXL]+|\d{1,2})\s*[.\-–)]", p)), None)
        if i_sent is None:
            i_sent = next((i + 1 for i, p in enumerate(ps[:400])
                           if re.match(r"^(?:Santa ?Fe de )?Bogot[aá]\b.*\d{4}", p) and len(p) < 160), 0)
        cuerpo_desde = i_sent
    else:
        cuerpo_desde = i_sent + 1
    # En algunas sentencias recientes la "Síntesis de la decisión" va antes de "SENTENCIA".
    k = next((i for i, p in enumerate(ps[:i_sent]) if seccion_de(p) == "sintesis"), i_sent)
    enc = _ficha(ps[:k])
    if enc["ficha"]["fecha"] is None and k < i_sent:
        enc["ficha"]["fecha"] = _ficha(ps[k:i_sent])["ficha"]["fecha"]

    secciones: list[dict[str, Any]] = []
    if k < i_sent:
        secciones.append({"seccion": "sintesis", "titulo": ps[k],
                          "parrafos": [{"texto": p, "sub": None} for p in ps[k:i_sent]]})
    actual: dict[str, Any] = {"seccion": "cuerpo", "titulo": None, "parrafos": []}
    sub: str | None = None
    omitiendo = False  # firmas tras "Notifíquese", constancias de secretaría
    cerrada = False    # tras cerrar la decisión solo siguen votos particulares y anexos
    for p in ps[cuerpo_desde:]:
        sec = seccion_de(p)
        if sec and (actual["seccion"] in _TERMINALES or cerrada) and sec not in _TERMINALES:
            sec = None
        if sec and sec not in _TERMINALES and ORDEN[sec] <= ORDEN[actual["seccion"]]:
            sec = None  # "RESUELVE" tras "DECISIÓN"; títulos que retroceden son subtítulos
        if sec == "anexo" and not cerrada and ORDEN[actual["seccion"]] < ORDEN["decision"]:
            sec = None  # "ANEXO I 73" en el índice de la síntesis
        if sec:
            if actual["parrafos"]:
                secciones.append(actual)
            actual = {"seccion": sec, "titulo": p, "parrafos": []}
            sub, omitiendo = None, False
            actual["parrafos"].append({"texto": p, "sub": None})
            continue
        if _CONSTANCIA.match(p):
            omitiendo = True
            continue
        if omitiendo:
            continue
        if actual["seccion"] == "decision" and _CIERRE.match(p):
            actual["parrafos"].append({"texto": p, "sub": sub})
            omitiendo = cerrada = True
            continue
        if es_subtitulo(p) and actual["seccion"] not in ("decision",):
            sub = p.rstrip(" .:")
        actual["parrafos"].append({"texto": p, "sub": sub})
    if actual["parrafos"]:
        secciones.append(actual)

    resuelve = []
    for s in secciones:
        if s["seccion"] == "decision":
            resuelve += [x["texto"] for x in s["parrafos"][1:]]
    chars: dict[str, int] = {}
    for s in secciones:
        chars[s["seccion"]] = chars.get(s["seccion"], 0) + sum(len(x["texto"]) for x in s["parrafos"])
    return {
        "ficha": {**enc["ficha"], "resuelve": resuelve},
        "descriptores": enc["descriptores"],
        "secciones": secciones,
        "qa": {
            "n_parrafos": len(ps),
            "marcador_sentencia": i_sent is not None and cuerpo_desde == i_sent + 1,
            "caracteres_por_seccion": chars,
            "sin_decision": "decision" not in chars,
            "ponentes": enc["ficha"]["ponentes"],
            "fecha": enc["ficha"]["fecha"],
        },
    }
