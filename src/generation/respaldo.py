"""Textos deterministas armados con los pasajes, sin LLM.

Tres usos:
- respuesta de respaldo cuando el LLM falla dos veces (LLMError): nunca se
  escribe una línea inválida;
- relleno de un campo obligatorio que el verificador dejó vacío al quitar
  citas sin respaldo;
- completar el fundamento de la respuesta con las normas de los pasajes.

Toda cita que producen sale de un pasaje de los 10 (su `norma`, o una norma
citada en su texto): por construcción queda respaldada.
"""
from __future__ import annotations

import re
from typing import Optional

from src.common.texto import acotar
from src.common.types import Answer, Passage, Question
from src.index.tokenizar import tokenizar

JURISPRUDENCIA_VACIA = ("No se identifica jurisprudencia específica sobre el punto; "
                        "la solución se funda en las normas citadas.")

_ENCABEZADO_ARTICULO = re.compile(r"ART[IÍ]CULO\s+[\w.\-]+\s*\.?\s*(?:<[^>]*>\.?\s*)?", re.IGNORECASE)


def cita(p: Passage) -> str:
    """Cita completa del pasaje: "Ley 472 de 1998, artículo 3" o "Sentencia C-355 de 2006"."""
    if p.articulo:
        return f"{p.norma}, artículo {p.articulo}"
    return p.norma


def citas_de_pasajes(passages: list[Passage]) -> list[str]:
    """Una cita por norma, en orden de relevancia, con sus artículos agrupados.

    ["Estatuto del Consumidor, artículos 42 y 43", "Sentencia C-145 de 2018", ...].
    Los fragmentos sin artículo (encabezado, secciones de sentencia) aportan solo la norma.
    """
    articulos: dict[str, list[str]] = {}
    for p in passages:
        arts = articulos.setdefault(p.norma, [])
        if p.articulo and p.articulo not in arts:
            arts.append(p.articulo)
    out = []
    for norma, arts in articulos.items():
        if not arts:
            out.append(norma)
        elif len(arts) == 1:
            out.append(f"{norma}, artículo {arts[0]}")
        else:
            out.append(f"{norma}, artículos {', '.join(arts[:-1])} y {arts[-1]}")
    return out


_TIPOS_NORMA = {"ley": "Ley", "decreto": "Decreto", "acto_legislativo": "Acto Legislativo",
                "resolucion": "Resolución", "circular": "Circular", "acuerdo": "Acuerdo"}

# Campo donde cada formato declara su fundamento (el que lee evaluate.answer_text).
CAMPO_REFERENCIA = {"semi_open": "referencia_legal", "multiple_choice": "justificacion",
                    "open_ended": "marco_normativo"}


def nombre_cuerpo(cuerpo: tuple) -> Optional[str]:
    """Nombre citable de un cuerpo del evaluador (tipo, número, año), o None.

    Solo se devuelve si el extractor oficial lo lee de vuelta como ese mismo cuerpo.
    """
    from src.common.alias_normas import nombre_citable
    from src.verification.citations import bodies, extract

    tipo, numero, anio = cuerpo
    if tipo == "jurisprudencia":
        nombre = f"Sentencia {numero} de {anio}"
    elif tipo in _TIPOS_NORMA:
        nombre = f"{_TIPOS_NORMA[tipo]} {numero} de {anio}"
    else:
        nombre = nombre_citable(tipo)
    return nombre if nombre and bodies(extract(nombre)) == {cuerpo} else None


def cuerpos_mencionados(passages: list[Passage]) -> list[tuple]:
    """Cuerpos citados dentro del texto de los pasajes, del más al menos frecuente.

    Una sentencia discute otras normas: la más mencionada en la evidencia suele ser
    la que funda la respuesta. Empates: primero el que aparece en un pasaje mejor.
    """
    from src.verification.citations import bodies, extract

    conteo: dict[tuple, int] = {}
    primero: dict[tuple, int] = {}
    for i, p in enumerate(passages):
        for c in bodies(extract(p.texto)):
            conteo[c] = conteo.get(c, 0) + 1
            primero.setdefault(c, i)
    return sorted(conteo, key=lambda c: (-conteo[c], primero[c], c))


def completar_referencia(a: Answer, passages: list[Passage], fuentes: int = 10, menciones: int = 0) -> list[str]:
    """Agrega al fundamento de la respuesta normas de los pasajes entregados que el LLM no citó.

    Hasta `fuentes` normas de las que son los pasajes (en orden de relevancia) y
    hasta `menciones` normas citadas dentro de su texto (por frecuencia). Todas
    están en los pasajes, así que quedan respaldadas; una norma respaldada fuera
    de la referencia vale 0 en el evaluador (no resta). Campo por formato:
    referencia_legal (no entra a RAGAS), justificacion como "Fundamento
    normativo: …" (las cerradas no pasan por RAGAS) y marco_normativo (sí entra
    a RAGAS). Devuelve las citas agregadas.
    """
    from src.verification.citations import MAX_PASAJES_EVIDENCIA, bodies, extract

    campo = CAMPO_REFERENCIA.get(a.formato)
    if campo is None or a.abstencion or not passages or (fuentes <= 0 and menciones <= 0):
        return []
    evidencia = passages[:MAX_PASAJES_EVIDENCIA]
    actual = getattr(a, campo) or ""
    ya = extract(actual)

    def citada(c: str) -> bool:
        propias = extract(c)
        return propias <= ya if propias else c.lower() in actual.lower()

    nuevas = [c for c in citas_de_pasajes(evidencia) if not citada(c)][:max(fuentes, 0)]
    vistos = bodies(ya.union(*(extract(c) for c in nuevas)))
    mencionadas: list[str] = []
    for c in cuerpos_mencionados(evidencia):
        if len(mencionadas) >= menciones:
            break
        nombre = nombre_cuerpo(c) if c not in vistos else None
        if nombre:
            mencionadas.append(nombre)
            vistos.add(c)
    nuevas += mencionadas
    if not nuevas:
        return []
    base = actual.rstrip(" .;")
    if a.formato == "multiple_choice":
        setattr(a, campo, (f"{base}. " if base else "") + f"Fundamento normativo: {'; '.join(nuevas)}.")
    else:
        valor = "; ".join([base, *nuevas] if base else nuevas)
        setattr(a, campo, valor + "." if a.formato == "open_ended" else valor)
    return nuevas


def cuerpo(p: Passage) -> str:
    """Texto dispositivo del pasaje, sin el prefijo de norma y ruta."""
    texto = p.texto
    m = _ENCABEZADO_ARTICULO.search(texto)
    if m:
        return texto[m.end():].strip()
    if texto.startswith(p.norma):
        texto = texto[len(p.norma):].lstrip(" .,")
    return texto.strip()


def _raices(texto: str) -> set[str]:
    return set(tokenizar(texto))


def solapamiento(texto: str, raices_evidencia: set[str]) -> tuple[float, int]:
    """(fracción, conteo) de raíces del texto presentes en la evidencia."""
    r = _raices(texto)
    if not r:
        return 0.0, 0
    n = len(r & raices_evidencia)
    return n / len(r), n


def mejor_pasaje(passages: list[Passage], referencia: Optional[str] = None) -> Passage:
    """El primero (el más relevante del lookup/reranker) o el de mayor solapamiento con `referencia`."""
    if not referencia:
        return passages[0]
    ref = _raices(referencia)
    return max(passages, key=lambda p: (len(ref & _raices(p.texto)), -passages.index(p)))


def palabras_clave(question: Question, n: int = 5) -> list[str]:
    """Primeras palabras de contenido de la pregunta (≥ 5 letras, sin repetir raíz)."""
    out: list[str] = []
    vistas: set[str] = set()
    for w in re.findall(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{5,}", question.pregunta):
        raiz = tokenizar(w)
        if not raiz or raiz[0] in vistas:
            continue
        vistas.add(raiz[0])
        out.append(w.lower())
        if len(out) >= n:
            break
    return out or ["norma aplicable"]


def texto_de_pasaje(p: Passage, max_oraciones: int = 3, max_palabras: int = 110) -> str:
    """"Conforme a lo dispuesto en <cita>: <primeras oraciones del artículo>"."""
    base = acotar(cuerpo(p), max_oraciones, max_palabras) or cuerpo(p)[:600]
    return f"Conforme a lo dispuesto en {cita(p)}: {base}"


def eleccion_cerrada(question: Question, passages: list[Passage]) -> str:
    """Letra con mayor solapamiento léxico con los pasajes; desempate por conteo y luego por letra."""
    evidencia = set().union(*(_raices(p.texto) for p in passages)) if passages else set()
    opciones = question.opciones or {}
    letras = sorted(opciones) or ["A"]
    return max(letras, key=lambda l: (*solapamiento(opciones.get(l, ""), evidencia), -ord(l)))


def justificacion_cerrada(letra: str, question: Question, passages: list[Passage]) -> str:
    p = mejor_pasaje(passages, (question.opciones or {}).get(letra) or question.pregunta)
    return f"La opción {letra} se ajusta a lo dispuesto en {cita(p)}."


def respuesta_respaldo(question: Question, passages: list[Passage]) -> Answer:
    """Respuesta completa y válida sin LLM (se marca en el Trace como fallback)."""
    a = Answer(id=question.id, formato=question.formato, pasajes_recuperados=list(passages))
    if question.formato == "multiple_choice":
        letra = eleccion_cerrada(question, passages)
        a.respuesta_correcta = letra
        a.justificacion = justificacion_cerrada(letra, question, passages) if passages else \
            f"La opción {letra} es la que mejor corresponde a la pregunta."
        a.descarte_opciones = {l: "No corresponde a la regla aplicable." for l in "ABCD" if l != letra}
        return a
    if not passages:
        return a  # sin pasajes: el verificador decide EVIDENCIA_INSUFICIENTE
    rellenar(a, question, passages)
    return a


def rellenar(a: Answer, question: Question, passages: list[Passage]) -> list[str]:
    """Rellena de forma determinista los campos obligatorios vacíos. Devuelve cuáles rellenó."""
    if not passages:
        return []
    p = mejor_pasaje(passages)
    rellenados: list[str] = []

    def poner(campo: str, valor) -> None:
        if not getattr(a, campo):
            setattr(a, campo, valor)
            rellenados.append(campo)

    if a.formato == "multiple_choice":
        if a.respuesta_correcta not in ("A", "B", "C", "D"):
            a.respuesta_correcta = eleccion_cerrada(question, passages)
            rellenados.append("respuesta_correcta")
        poner("justificacion", justificacion_cerrada(a.respuesta_correcta, question, passages))
        for l in "ABCD":
            if l != a.respuesta_correcta and not a.descarte_opciones.get(l):
                a.descarte_opciones[l] = "No corresponde a la regla aplicable."
        return rellenados
    if a.formato == "semi_open":
        poner("respuesta", texto_de_pasaje(p))
        poner("referencia_legal", cita(p))
        poner("palabras_clave", palabras_clave(question))
        return rellenados
    # open_ended
    normas: list[str] = []
    for q in passages:
        c = cita(q)
        if q.norma not in {n.split(",")[0] for n in normas}:
            normas.append(c)
        if len(normas) >= 3:
            break
    sentencias = [q.norma for q in passages if q.norma.lower().startswith("sentencia")]
    poner("marco_normativo", "; ".join(normas) + ".")
    poner("analisis", texto_de_pasaje(p, max_oraciones=5, max_palabras=160))
    poner("jurisprudencia", (f"{sentencias[0]}." if sentencias else JURISPRUDENCIA_VACIA))
    poner("conclusion", f"La solución del caso se rige por {cita(p)}.")
    return rellenados
