"""Parser de la base documental de la Secretaría del Senado (basedoc).

Estructura de cada página (verificada en Constitución, CGP, Código Civil, Ley 472):

- El texto normativo va entre `<!--Inicio documento-->` y `<!--Fin documento-->`;
  antes hay menús, un índice de artículos y scripts (incluso inyectados por proxies).
- Cada artículo abre con `<p><a class="bookmarkaj" name="31">ARTÍCULO 31. ...</a>`.
  Un "ARTÍCULO 50." citado entre comillas dentro de una ley de reforma no lleva
  ancla, así que no abre un artículo nuevo.
- Títulos, capítulos, libros: `<p class="centrado">` (etiqueta y nombre en dos <p>).
- Notas: `<div><a class="caja_vja_encabezado" href="javascript:insRowN()">Notas de
  Vigencia</a></div><table id="TableN" class="caja_vja_v">`, con el contenido en el
  JS compañero (`js/<página>.js`, función insRowN). "Legislación Anterior" (texto
  viejo del artículo) vive solo ahí y no entra al texto.
- Apartes declarados inexequibles o derogados van tachados (`<s>`) y se quitan: el
  texto indexado es el vigente; el marcador "<Aparte tachado INEXEQUIBLE>" se queda.
- Tras las firmas de algunas leyes estatutarias va transcrita la sentencia de control
  previo (Ley 1581: C-748-11; Ley 1712: C-274-13). Se corta ahí (`qa.anexo_descartado`):
  la sentencia se ingiere como documento propio desde la relatoría.

Salida: dict serializable (ver `parsear_documento`) que consume segmentar.py.
"""
from __future__ import annotations

import html as html_lib
import re
from pathlib import Path
from typing import Any

import lxml.html

from src.ingest.red import decodificar, sin_scripts

INICIO, FIN = "<!--Inicio documento-->", "<!--Fin documento-->"

# Notas que entran al fragmento (línea compacta de vigencia); el resto se ignora.
NOTAS_VIGENCIA = ("notas de vigencia", "jurisprudencia vigencia", "resumen de notas de vigencia")

_ARTICULO = re.compile(
    r"^(?P<pal>ART[IÍ]CULO|Art[ií]culo)\s+"
    r"(?P<trans>(?:TRANSITORIO|Transitorio)\b\s*)?"
    r"(?P<num>\d+(?:\s*-\s*(?:\d+|[A-Z](?![a-záéíóúñ])))?[A-Z]?"
    r"(?:\s+(?:BIS|TER|QUATER|bis|ter|quater)\b)?)?"
    r"\s*(?:[oº°](?![A-Za-zÁÉÍÓÚÑáéíóúñ]))?")
# Fin del articulado: firmas y fórmula de promulgación, que no son parte del último artículo.
_FIRMAS = re.compile(
    r"^(?:(?:El|La|EL|LA) (?:Presidente|Presidenta|PRESIDENTE|PRESIDENTA|Secretario|Secretaria|"
    r"SECRETARIO|SECRETARIA)\b.{0,80}(?:Senado|SENADO|C[aá]mara|C[AÁ]MARA|Rep[uú]blica|REP[UÚ]BLICA)"
    r"|PUBL[IÍ]QUESE|Publ[ií]quese|COMUN[IÍ]QUESE|Dad[ao] en .{0,60} a los|CONSTANCIA$)")
# Sentencia de control previo que el Senado transcribe tras las firmas de una ley estatutaria
# (Ley 1581: C-748-11; Ley 1712: C-274-13). Sus "TÍTULO I" reabrían el articulado y la
# sentencia entera quedaba en el último artículo: desde aquí no entra nada más del documento.
_ANEXO = re.compile(r"^(?:SENTENCIA\s+(?:N[ÚU]MERO\s+)?(?:C|SU|T)\s*-\s*\d+|CORTE CONSTITUCIONAL\.?$)", re.I)
# Un "ARTÍCULO N" sin ancla solo abre artículo si sigue la numeración (hasta este salto).
MAX_SALTO = 10
_NIVELES = {"PARTE": 0, "LIBRO": 1, "TITULO": 2, "TÍTULO": 2, "CAPITULO": 3, "CAPÍTULO": 3,
            "SECCION": 4, "SECCIÓN": 4, "SUBSECCION": 5, "SUBSECCIÓN": 5}
_ENCABEZADO = re.compile(r"^(PARTE|LIBRO|T[IÍ]TULO|CAP[IÍ]TULO|SUBSECCI[OÓ]N|SECCI[OÓ]N)\b", re.I)
_JS_FUNC = re.compile(
    r"function\s+\w+\(\)\s*\{.*?description\[0\]\s*=\s*\"((?:[^\"\\]|\\.)*)\";"
    r".*?getElementById\('(\w+)'\)", re.S)


def _limpio(s: str) -> str:
    s = s.replace("\xa0", " ").replace("​", "")
    return re.sub(r"\s+", " ", s).strip()


def notas_js(js: str) -> dict[str, str]:
    """TableN -> texto de la nota, desde el JS compañero de la página."""
    out = {}
    for contenido, tabla in _JS_FUNC.findall(js or ""):
        frag = contenido.replace('\\"', '"').replace("\\'", "'")
        texto = lxml.html.fromstring(f"<div>{frag}</div>").text_content() if frag.strip() else ""
        out[tabla] = _limpio(html_lib.unescape(texto))
    return out


def _texto_bloque(el) -> str:
    for s in el.xpath(".//s|.//strike|.//del"):
        s.drop_tree()  # conserva el texto que sigue al tachado
    return _limpio(el.text_content())


def numero_articulo(texto: str) -> str | None:
    """'ARTÍCULO 1o. ...' -> '1'; 'ARTÍCULO 240-1.' -> '240-1'; 'ARTICULO TRANSITORIO 5.' -> 'TRANSITORIO 5'."""
    m = _ARTICULO.match(texto)
    if not m or not (m.group("num") or m.group("trans")):
        return None
    num = re.sub(r"\s+", " ", (m.group("num") or "").replace(" - ", "-").replace(" -", "-")
                 .replace("- ", "-")).strip().upper()
    return ("TRANSITORIO " + num).strip() if m.group("trans") else num


def _serie(num: str) -> tuple[str, int | None]:
    """('N', 240) para '240-1'; ('T', 5) para 'TRANSITORIO 5'; ('T', None) sin número."""
    serie = "T" if num.startswith("TRANSITORIO") else "N"
    m = re.search(r"\d+", num)
    return serie, int(m.group()) if m else None


class _Estado:
    def __init__(self) -> None:
        self.ruta: list[tuple[int, str]] = []
        self.rango_seccion: float | None = None
        self.pendiente_nombre = False
        self.preambulo: dict[str, Any] = {"parrafos": [], "notas": {}}
        self.articulos: list[dict[str, Any]] = []
        self.actual: dict[str, Any] = self.preambulo
        self.sin_ancla: list[str] = []
        self.etiqueta_nota: str | None = None
        self.ultimo: dict[str, int] = {}
        self.firmas: list[str] = []
        self.en_firmas = False
        self.anexo: str | None = None  # primer párrafo de la sentencia transcrita tras las firmas

    def es_articulo_sin_ancla(self, texto: str, num: str) -> bool:
        """Encabezado real al que el Senado no le puso ancla, o artículo citado.

        Los citados (dentro de leyes de reforma) suelen ir en minúscula ("Artículo
        199."), tras un párrafo que termina en "quedará así:", o fuera de secuencia.
        """
        if not texto.startswith(("ARTÍCULO", "ARTICULO")):
            return False
        previo = self.actual["parrafos"][-1] if self.actual["parrafos"] else ""
        if previo.rstrip(" >\"'”").endswith(":"):
            return False
        serie, n = _serie(num)
        if n is None:
            return serie == "T"  # "ARTÍCULO TRANSITORIO." sin número
        ultimo = self.ultimo.get(serie)
        return (n <= 3) if ultimo is None else (ultimo <= n <= ultimo + MAX_SALTO)

    def encabezado(self, texto: str) -> None:
        m = _ENCABEZADO.match(texto)
        clave = m.group(1).upper()
        rango: float = _NIVELES.get(clave, 4)
        if clave.startswith("SECCI"):
            # En unos códigos la sección está sobre el título (CGP), en otros bajo el
            # capítulo: se fija su rango la primera vez que aparece.
            if self.rango_seccion is None:
                self.rango_seccion = (self.ruta[-1][0] + 0.5) if self.ruta else 1.5
            rango = self.rango_seccion
        self.ruta = [x for x in self.ruta if x[0] < rango] + [(rango, texto.rstrip(". "))]
        self.pendiente_nombre = True

    def nombre_encabezado(self, texto: str) -> None:
        rango, etiqueta = self.ruta[-1]
        self.ruta[-1] = (rango, f"{etiqueta}. {texto.rstrip('. ')}")
        self.pendiente_nombre = False


def parsear_pagina(html: str, js: str, pagina: str, est: _Estado) -> None:
    html = sin_scripts(html)
    a, b = html.find(INICIO), html.find(FIN)
    if a >= 0:
        cuerpo = html[a + len(INICIO): b if b > a else None]
        raiz = lxml.html.fragment_fromstring(cuerpo, create_parent="div")
    else:
        # Mismo formato (Avance Jurídico) en otros normogramas, p. ej. el de la Cancillería:
        # sin marcadores, el documento va en div.panel-documento.
        doc = lxml.html.document_fromstring(html)
        panel = doc.xpath("//div[contains(concat(' ', @class, ' '), ' panel-documento ')]")
        raiz = panel[0] if panel else doc.body
    notas = notas_js(js)
    _recorrer(raiz, est, notas, pagina)


def _recorrer(raiz, est: _Estado, notas: dict[str, str], pagina: str) -> None:
    for el in raiz:
        if est.anexo is not None:
            return
        tag = el.tag if isinstance(el.tag, str) else ""
        clase = el.get("class") or ""
        if tag in ("script", "style", "img", "br", "hr"):
            continue
        if tag == "div":
            etiqueta = el.xpath(".//a[starts-with(@class,'caja_vja_encabezado')]")
            if etiqueta:
                est.etiqueta_nota = _limpio(etiqueta[0].text_content())
            else:
                _recorrer(el, est, notas, pagina)
            continue
        if tag == "table":
            if clase.startswith("caja_vja"):
                tipo = (est.etiqueta_nota or "nota").lower()
                texto = notas.get(el.get("id") or "", "")
                if texto:
                    est.actual["notas"].setdefault(tipo, []).append(texto)
                est.etiqueta_nota = None
            else:  # tabla real del articulado (tarifas, cuadros)
                filas = [" | ".join(_limpio(c.text_content()) for c in tr.xpath("./td|./th"))
                         for tr in el.xpath(".//tr")]
                texto = "\n".join(f for f in filas if f.strip(" |"))
                if texto:
                    est.actual["parrafos"].append(texto)
            continue
        if tag == "a" and not el.xpath("self::a[@class='bookmarkaj']"):
            continue  # "ir al inicio", Anterior/Siguiente sueltos
        if tag not in ("p", "a", "blockquote", "li", "ul", "ol", "center", "span", "font"):
            _recorrer(el, est, notas, pagina)
            continue
        if el.xpath(".//a[@class='antsig']"):
            continue  # navegación Anterior | Siguiente
        ancla = el.xpath("self::a[@class='bookmarkaj']|.//a[@class='bookmarkaj']")
        texto = _texto_bloque(el)
        if not texto:
            continue
        if est.en_firmas and _ANEXO.match(texto):
            est.anexo = texto
            return
        num = numero_articulo(texto)
        centrado = "centrado" in clase
        if centrado and not num and _ENCABEZADO.match(texto):
            est.encabezado(texto)
            est.en_firmas = False
            continue
        if centrado and not num and est.pendiente_nombre and est.ruta:
            est.nombre_encabezado(texto)
            continue
        if num and (ancla or est.es_articulo_sin_ancla(texto, num)):
            if not ancla:
                est.sin_ancla.append(num)
            serie, n = _serie(num)
            if n is not None:
                est.ultimo[serie] = n
            est.pendiente_nombre = False
            est.en_firmas = False
            est.actual = {"articulo": num, "ruta": [r[1] for r in est.ruta],
                          "parrafos": [texto], "notas": {}, "pagina": pagina,
                          "ancla": bool(ancla)}
            est.articulos.append(est.actual)
            continue
        if est.articulos and (est.en_firmas or _FIRMAS.match(texto)):
            est.en_firmas = True
            est.firmas.append(texto)
            continue
        est.pendiente_nombre = False
        est.actual["parrafos"].append(texto)


def _epigrafe(parrafos: list[str]) -> str | None:
    for p in parrafos:
        if re.match(r"^Por (?:la|el|medio de la|medio del) cual", p, re.I):
            return p
    return None


def parsear_documento(carpeta: Path, paginas: list[str]) -> dict[str, Any]:
    """Une las páginas de un documento del Senado en una sola estructura.

    Devuelve {"preambulo": {parrafos, notas}, "epigrafe", "articulos": [{articulo,
    ruta, parrafos, notas, pagina}], "qa": {...}}.
    """
    est = _Estado()
    for nombre in paginas:
        raw = (carpeta / nombre).read_bytes()
        js_path = carpeta / "js" / (nombre.rsplit(".", 1)[0] + ".js")
        js = decodificar(js_path.read_bytes(), "text/javascript; charset=iso-8859-1") \
            if js_path.exists() else ""
        parsear_pagina(decodificar(raw), js, nombre, est)

    nums = [a["articulo"] for a in est.articulos]
    vistos: dict[str, int] = {}
    for n in nums:
        vistos[n] = vistos.get(n, 0) + 1
    enteros = [int(m.group()) for n in nums if (m := re.match(r"\d+", n)) and not n.startswith("TRANS")]
    saltos = [(x, y) for x, y in zip(enteros, enteros[1:]) if y > x + 1]
    return {
        "preambulo": est.preambulo,
        "epigrafe": _epigrafe(est.preambulo["parrafos"]),
        "articulos": est.articulos,
        "qa": {
            "n_articulos": len(nums),
            "duplicados": sorted(n for n, c in vistos.items() if c > 1),
            "saltos": saltos[:50],
            "n_saltos": len(saltos),
            "retrocesos": sum(1 for x, y in zip(enteros, enteros[1:]) if y < x),
            "sin_ancla_aceptados": est.sin_ancla,
            "n_parrafos_firma": len(est.firmas),
            "anexo_descartado": est.anexo,
            "ultimo": nums[-1] if nums else None,
        },
    }
