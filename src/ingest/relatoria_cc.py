"""Cosecha por número de sentencias de la relatoría de la Corte Constitucional.

La relatoría no publica un índice navegable (relatoria/AAAA/ responde 403) y el
buscador devuelve listados parciales, así que se enumeran los números del año.
Hechos verificados (2026-10-01):

- URL: relatoria/2025/T-256-25.htm, relatoria/2021/C-094-21.htm; las SU van sin
  guion (relatoria/2022/SU355-22.htm, también en 1999: SU047-99.htm). Número con
  al menos 3 dígitos (T-1185 de 2001 lleva 4).
- T y SU comparten la numeración del año (T-276, SU-277, T-278...); C lleva la suya.
- Un número inexistente responde 200 con una página de error de ~8,6 KB: la
  existencia se decide por el tamaño total (Range de 1 byte, sin bajar el archivo)
  y el documento descargado se valida por contenido con `resolver.validar`.
- La publicación tiene huecos (fallos aún sin publicar: T-056-25, T-248-25): el
  recorrido de un año se detiene tras `--huecos` números seguidos sin sentencia.

Por cada sentencia nueva:
1. corpus/raw/<doc_id>/ + _descarga.json (mismo formato que descargar.py);
2. una entrada en sources/relatoria_cc.yaml (origen "relatoria_cc", ola 3) y su
   URL en sources/urls.lock.json, para que extraer/segmentar/manifest la traten
   como cualquier otro documento;
3. con --procesar, extraer + segmentar, consolidar fragmentos.jsonl e informe de
   calidad (ponente, fecha, decisión, fragmentos por sentencia).

Lo ya inventariado en otro YAML (seed, muestra) no se duplica: cuenta como
existente para el recorrido y se deja a su flujo normal. El sondeo (qué números no
existen a la fecha) queda en corpus/raw/_relatoria_cc.json para reanudar sin
repetir peticiones; --reintentar vuelve a probar los que faltaban.

    python -m src.ingest.relatoria_cc --anios 2025 2026 --salas T SU C --procesar
    python -m src.ingest.relatoria_cc --anios 2015-2026 --salas C SU
    python -m src.ingest.relatoria_cc --anios 2025 --salas T --desde 240 --hasta 270
    python -m src.ingest.relatoria_cc --informe          # calidad de lo ya cosechado
    python -m src.ingest.relatoria_cc --anios 1992-2026 --hilos 4 --listar   # todo + listado
"""
from __future__ import annotations

import argparse
import json
import statistics
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from typing import Any, Iterator

from src.common import rutas
from src.ingest import descargar, extraer, fuentes, segmentar
from src.ingest.fuentes import Doc
from src.ingest.red import Cliente
from src.ingest.resolver import CORTE_CONST, MIN_BYTES, cargar_lock, guardar_lock, validar

ARCHIVO = rutas.SOURCES / "relatoria_cc.yaml"
ESTADO = rutas.RAW / "_relatoria_cc.json"
LISTADO = rutas.SOURCES / "relatoria_cc_urls.md"
ENCABEZADO = """\
# Sentencias de la Corte Constitucional cosechadas por número de la relatoría
# (src/ingest/relatoria_cc.py). Las entradas existentes se conservan tal cual al
# volver a cosechar: para sacar una del corpus, estado "excluido" + motivo_exclusion.
area: constitucional
"""
ORIGEN = "relatoria_cc"
# Numeraciones del año: T y SU comparten contador; C tiene el suyo.
FAMILIAS = {"C": ("C",), "T": ("T", "SU")}
SALAS = ("C", "T", "SU")
ESPERA_BLOQUEO = 600  # segundos de espera cuando el sitio deja de responder


def url_de(sala: str, num: int, anio: int) -> str:
    sep = "" if sala == "SU" else "-"
    return f"{CORTE_CONST}{anio}/{sala}{sep}{num:03d}-{anio % 100:02d}.htm"


def doc_de(sala: str, num: int, anio: int) -> Doc:
    """Entrada de sources/ con las convenciones del seed (número sin ceros: "SU-11")."""
    numero = f"{sala}-{num}"
    return {
        "doc_id": f"sentencia_{sala.lower()}_{num}_{anio}",
        "nombre_citable": f"Sentencia {numero} de {anio}",
        "tipo": "sentencia",
        "numero": numero,
        "anio": str(anio),
        "organo_emisor": "Corte Constitucional",
        "fuente": "Relatoría de la Corte Constitucional",
        "donde_buscar": f"{CORTE_CONST}?q=Sentencia%20{numero}%20de%20{anio}",
        "url": url_de(sala, num, anio),
        "items_del_banco": 0,
        "areas": ["constitucional"],
        "canonico": ["jurisprudencia", numero, str(anio)],
        "origen": ORIGEN,
        "prioridad": "baja",
        "ola": 3,
        "estado": "pendiente",
        "justificacion": "Cosecha por número de la relatoría de la Corte Constitucional.",
    }


def _orden(d: Doc) -> tuple:
    sala, num = d["numero"].split("-")
    return int(d["anio"]), SALAS.index(sala), int(num)


class Cosecha:
    """Inventario propio (sources/relatoria_cc.yaml), lock y estado del sondeo.

    Compartida entre hilos: las peticiones van fuera del candado, los cambios de
    estado y la escritura a disco dentro.
    """

    GUARDAR_CADA = 60.0  # segundos entre escrituras a disco durante la cosecha

    def __init__(self) -> None:
        if ARCHIVO.exists():
            _, _, docs = fuentes.cargar_archivo(ARCHIVO)
        else:
            docs = []
        self.propios: dict[str, Doc] = {d["doc_id"]: d for d in docs}
        # Cuerpos inventariados en los demás YAML: existen, pero no se duplican aquí.
        self.ajenos = {tuple(d["canonico"]) for d in fuentes.cargar().values()
                       if d["_archivo"] != ARCHIVO.stem and d.get("canonico")}
        self.lock = cargar_lock()
        self.sondeo: dict[str, str] = (json.loads(ESTADO.read_text(encoding="utf-8"))
                                       if ESTADO.exists() else {})
        # Errores de red marcados como inválidos por versiones anteriores: vuelven a probarse.
        for clave, valor in self.sondeo.items():
            if valor.startswith("invalida HTTP 0"):
                self.sondeo[clave] = "si"
        self.nuevos: list[str] = []
        self._candado = threading.Lock()
        self._guardado = time.monotonic()

    def guardar(self, si_toca: bool = False) -> None:
        with self._candado:
            if si_toca and time.monotonic() - self._guardado < self.GUARDAR_CADA:
                return
            try:
                fuentes.guardar_archivo(ARCHIVO, ENCABEZADO, sorted(self.propios.values(), key=_orden))
                guardar_lock(self.lock)
                ESTADO.parent.mkdir(parents=True, exist_ok=True)
                ESTADO.write_text(json.dumps(dict(sorted(self.sondeo.items())), indent=0) + "\n",
                                  encoding="utf-8")
            except OSError as e:
                # Windows niega la escritura si otro programa (editor, git, antivirus) tiene
                # el archivo abierto (2026-10-02, Errno 22): el guardado periódico se
                # reintenta en el próximo ciclo; el final sí debe fallar.
                if not si_toca:
                    raise
                print(f"-- guardado aplazado: {e}", flush=True)
            self._guardado = time.monotonic()

    def existe(self, cli: Cliente, sala: str, num: int, anio: int, reintentar: bool) -> bool:
        clave = f"{anio}/{sala}-{num}"
        with self._candado:
            if ("jurisprudencia", f"{sala}-{num}", str(anio)) in self.ajenos \
                    or doc_de(sala, num, anio)["doc_id"] in self.propios:
                self.sondeo.setdefault(clave, "si")
                return True
            previo = self.sondeo.get(clave)
            if previo == "si" or previo and not reintentar:
                return previo == "si"
        tam = cli.tamano(url_de(sala, num, anio))
        if tam is None:
            return False  # error de red: sin registrar, se reintenta en la próxima corrida
        with self._candado:
            self.sondeo[clave] = "si" if tam >= MIN_BYTES else f"no {date.today().isoformat()}"
        return tam >= MIN_BYTES

    def _registrar(self, d: Doc, info: dict[str, Any]) -> None:
        with self._candado:
            self.propios.setdefault(d["doc_id"], d)
            self.lock[d["doc_id"]] = {"estado": "ok", "url": d["url"], "parser": "corte_constitucional",
                                      "origen_url": "patron", "fecha": info["fecha_consulta"],
                                      "probadas": [{"url": d["url"], "motivo": "ok"}]}
            self.nuevos.append(d["doc_id"])

    def cosechar(self, cli: Cliente, sala: str, num: int, anio: int) -> str:
        d = doc_de(sala, num, anio)
        if tuple(d["canonico"]) in self.ajenos:
            return "inventariada"
        registro = rutas.RAW / d["doc_id"] / "_descarga.json"
        if registro.exists():
            if d["doc_id"] in self.propios:
                return "ya"
            self._registrar(d, json.loads(registro.read_text(encoding="utf-8")))
            return "registrada"  # descargada en una corrida interrumpida antes de guardar
        resp = cli.get(d["url"])
        if resp.status == 0 or resp.status >= 500:
            return f"error de red ({resp.content_type or resp.status})"  # sin marcar: se reintenta
        motivo = validar(resp, d, "corte_constitucional")
        if motivo:
            with self._candado:
                self.sondeo[f"{anio}/{sala}-{num}"] = f"invalida {motivo}"
            return f"invalida ({motivo})"
        carpeta = registro.parent
        carpeta.mkdir(parents=True, exist_ok=True)
        archivos: list[dict] = []
        nombre = descargar._nombre(d["url"])
        descargar._guardar(carpeta, nombre, resp, archivos)
        info = {"doc_id": d["doc_id"], "url": d["url"], "parser": "corte_constitucional",
                "fecha_consulta": date.today().isoformat(), "paginas": [nombre],
                "archivos": archivos, "completo": True}
        registro.write_text(json.dumps(info, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        self._registrar(d, info)
        return f"ok ({len(resp.contenido) // 1024} KB)"


def recorrer(cos: Cosecha, cli: Cliente, anio: int, familia: str, desde: int, hasta: int | None,
             huecos: int, reintentar: bool) -> Iterator[tuple[str, int]]:
    """(sala, número) existentes de una numeración, en orden; para tras `huecos` vacíos."""
    ultimo, n = desde - 1, desde
    while (n <= hasta) if hasta is not None else (n - ultimo <= huecos):
        for sala in FAMILIAS[familia]:
            if cos.existe(cli, sala, n, anio, reintentar):
                ultimo = n
                yield sala, n
                break
        n += 1


def procesar(ids: list[str]) -> list[dict[str, Any]]:
    """extraer + segmentar de cada sentencia; una fila de calidad por documento."""
    docs = fuentes.cargar()
    filas = []
    for doc_id in ids:
        d = docs[doc_id]
        fila: dict[str, Any] = {"doc_id": doc_id}
        try:
            est = extraer.extraer_doc(d)
            info = segmentar.segmentar_doc(d)
        except Exception as e:  # una sentencia rara no detiene el lote
            fila["error"] = f"{type(e).__name__}: {e}"
            filas.append(fila)
            print(f"error          {doc_id:40s} {fila['error']}", flush=True)
            continue
        qa = est["qa"]
        chars = qa["caracteres_por_seccion"]
        fila.update(n_fragmentos=info["n_fragmentos"], caracteres=sum(chars.values()),
                    ponente=bool(qa["ponentes"]), fecha=bool(qa["fecha"]),
                    decision=not qa["sin_decision"], consideraciones="consideraciones" in chars,
                    votos=chars.get("salvamento_voto", 0) + chars.get("aclaracion_voto", 0))
        filas.append(fila)
        alerta = "" if fila["decision"] else " · SIN DECISIÓN"
        print(f"procesada      {doc_id:40s} {info['n_fragmentos']:4d} frag · "
              f"{'/'.join(qa['ponentes']) or 'sin ponente'}{alerta}", flush=True)
    return filas


def informe(filas: list[dict[str, Any]]) -> None:
    ok = [f for f in filas if "error" not in f]
    if not filas:
        print("sin sentencias que informar")
        return
    print(f"\n== Informe: {len(ok)}/{len(filas)} procesadas sin error ==")
    if not ok:
        return
    frs = [f["n_fragmentos"] for f in ok]
    pct = lambda k: f"{100 * sum(bool(f[k]) for f in ok) / len(ok):.0f} %"  # noqa: E731
    print(f"fragmentos: total {sum(frs)} · mediana {statistics.median(frs):.0f} · máx {max(frs)}")
    print(f"caracteres: mediana {statistics.median(f['caracteres'] for f in ok):,.0f}")
    print(f"con ponente {pct('ponente')} · con fecha {pct('fecha')} · con decisión {pct('decision')}"
          f" · con consideraciones {pct('consideraciones')}")
    votos = sum(f["votos"] for f in ok) / max(1, sum(f["caracteres"] for f in ok))
    print(f"peso de salvamentos/aclaraciones: {100 * votos:.0f} % de los caracteres")
    for f in filas:
        if "error" in f or not (f["decision"] and f["ponente"] and f["consideraciones"]):
            print(f"  revisar {f['doc_id']}: {f.get('error') or 'sin decisión, ponente o consideraciones'}")


def _anios(valores: list[str]) -> list[int]:
    out: list[int] = []
    for v in valores:
        a, _, b = v.partition("-")
        out += list(range(int(a), int(b or a) + 1))
    return out


def listar(destino: Path) -> int:
    """Escribe en Markdown todas las URL que existen según el sondeo, por año y sala."""
    por_anio: dict[int, list[tuple[int, int, str]]] = {}
    for clave, valor in json.loads(ESTADO.read_text(encoding="utf-8")).items() if ESTADO.exists() else []:
        if valor != "si":
            continue
        anio, ref = clave.split("/")
        sala, num = ref.split("-")
        por_anio.setdefault(int(anio), []).append((SALAS.index(sala), int(num), sala))
    total = sum(len(v) for v in por_anio.values())
    lineas = [
        "# Sentencias de la Corte Constitucional en la relatoría (URL directas)",
        "",
        f"Generado por `python -m src.ingest.relatoria_cc --listar` el {date.today().isoformat()}, "
        "a partir del sondeo por número (`corpus/raw/_relatoria_cc.json`). Una URL figura si el "
        f"archivo pesa al menos {MIN_BYTES:,} bytes (la página de error de la relatoría pesa ~8,6 KB). "
        "Los años en curso tienen huecos de fallos aún no publicados.",
        "",
        f"**Total: {total:,} sentencias.**",
        "",
        "| Año | C | T | SU | Total |",
        "|---|---:|---:|---:|---:|",
    ]
    for anio in sorted(por_anio, reverse=True):
        cuenta = {s: sum(1 for x in por_anio[anio] if x[2] == s) for s in SALAS}
        lineas.append(f"| {anio} | {cuenta['C']} | {cuenta['T']} | {cuenta['SU']} | {len(por_anio[anio])} |")
    for anio in sorted(por_anio, reverse=True):
        lineas += ["", f"## {anio}", ""]
        lineas += [f"- {url_de(sala, num, anio)}" for _, num, sala in sorted(por_anio[anio])]
    destino.write_text("\n".join(lineas) + "\n", encoding="utf-8", newline="\n")
    return total


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--anios", nargs="*", default=[], help="años o rangos: 2025 2015-2020")
    ap.add_argument("--salas", nargs="+", default=list(SALAS), choices=SALAS)
    ap.add_argument("--desde", type=int, default=1)
    ap.add_argument("--hasta", type=int, help="último número a probar (sin él, para por huecos)")
    ap.add_argument("--huecos", type=int, default=100, help="números seguidos sin sentencia para parar")
    ap.add_argument("--max", type=int, help="tope de sentencias nuevas en esta corrida")
    ap.add_argument("--solo-sondear", action="store_true", help="solo existencia (para --listar), sin descargar")
    ap.add_argument("--reintentar", action="store_true", help="volver a probar los que no existían")
    ap.add_argument("--hilos", type=int, default=1, help="numeraciones (año, sala) en paralelo")
    ap.add_argument("--procesar", action="store_true", help="extraer + segmentar lo cosechado")
    ap.add_argument("--informe", action="store_true", help="procesar e informar todo lo cosechado")
    ap.add_argument("--listar", nargs="?", const=str(LISTADO),
                    help=f"escribir las URL en Markdown (por defecto {LISTADO.relative_to(rutas.RAIZ)})")
    ap.add_argument("--pausa", type=float, default=0.3, help="segundos entre peticiones de cada hilo")
    args = ap.parse_args()

    cos = Cosecha()
    parar = threading.Event()
    familias = [f for f in FAMILIAS if set(FAMILIAS[f]) & set(args.salas)]
    # Primero lo reciente: es lo que más preguntan y lo que menos tiene el seed.
    tareas = [(a, f) for a in sorted(_anios(args.anios), reverse=True) for f in familias]

    fallos, fallos_lock = [0], threading.Lock()  # errores de red seguidos, entre todos los hilos

    def una(anio: int, familia: str) -> None:
        cli = Cliente(pausa=args.pausa)
        hallados = 0
        for sala, num in recorrer(cos, cli, anio, familia, args.desde, args.hasta,
                                  args.huecos, args.reintentar):
            if parar.is_set():
                return
            hallados += 1
            if sala not in args.salas or args.solo_sondear:
                continue
            res = cos.cosechar(cli, sala, num, anio)
            if res not in ("ya", "inventariada"):
                print(f"{res:24s} {sala}-{num} de {anio}", flush=True)
            # El sitio bloquea la IP unos minutos ante ráfagas (2026-10-01, con 6 hilos y
            # 0,3 s): tras varios errores de red seguidos, todos los hilos esperan.
            with fallos_lock:
                fallos[0] = fallos[0] + 1 if res.startswith("error de red") else 0
                bloqueo = fallos[0] >= 5
                if bloqueo:
                    fallos[0] = 0
                    print(f"-- {ESPERA_BLOQUEO // 60} min de espera: el sitio no responde", flush=True)
            if bloqueo:
                time.sleep(ESPERA_BLOQUEO)
            cos.guardar(si_toca=True)  # una interrupción no pierde lo cosechado
            if args.max and len(cos.nuevos) >= args.max:
                parar.set()
        print(f"-- {anio} {'/'.join(FAMILIAS[familia])}: {hallados} existentes", flush=True)

    with ThreadPoolExecutor(max_workers=max(1, args.hilos)) as ex:
        futuros = [ex.submit(una, a, f) for a, f in tareas]
        try:
            for fut in futuros:
                fut.result()
        except BaseException:
            parar.set()  # los demás hilos terminan en su próximo hallazgo
            print("-- corrida detenida", flush=True)
            raise
        finally:
            cos.guardar()
    print(f"nuevas: {len(cos.nuevos)} · inventario propio: {len(cos.propios)}")
    if args.listar:
        destino = Path(args.listar)
        print(f"listado: {listar(destino)} URL en {destino}")

    if args.informe:
        ids = sorted(k for k in cos.propios if (rutas.RAW / k / "_descarga.json").exists())
    elif args.procesar:
        ids = cos.nuevos
    else:
        return
    filas = procesar(ids)
    print(f"fragmentos.jsonl: {segmentar.consolidar()} filas")
    informe(filas)


if __name__ == "__main__":
    main()
