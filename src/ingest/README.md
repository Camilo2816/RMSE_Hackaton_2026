# src/ingest

**Responsabilidad:** descarga, extracción, segmentación y metadatos del corpus jurídico.
**Entradas:** `sources/*.yaml` (qué) + `sources/urls.lock.json` (dónde).
**Salidas:** `corpus/raw/`, `corpus/interim/`, `corpus/processed/<doc_id>.txt`,
`corpus/processed/fragmentos.jsonl`, `corpus_manifest.json`.

## Flujo

```bash
python -m src.ingest.importar_inventario        # xlsx de docs/ -> sources/*.yaml (idempotente)
python -m src.ingest.resolver   --ola 0 1       # URL directa validada -> sources/urls.lock.json
python -m src.ingest.descargar  --ola 0 1       # originales -> corpus/raw/<doc_id>/ (+ _descarga.json)
python -m src.ingest.extraer    --ola 0 1       # estructura -> corpus/interim/<doc_id>.json (+ qa)
python -m src.ingest.segmentar  --ola 0 1       # fragmentos -> corpus/processed/ (+ fragmentos.jsonl)
python -m src.ingest.manifest                   # corpus_manifest.json desde lo procesado
pytest tests/test_fuentes.py tests/test_fragmentos.py tests/test_sin_fuga.py tests/test_parser_senado.py
```

Todos aceptan `--ids doc_a doc_b` en lugar de `--ola`. Por defecto procesan solo
documentos `pendiente`; los `por_verificar` solo si se piden por id; los
`excluido` nunca. Descarga y resolución no repiten trabajo hecho (`--forzar`).

## Módulos

| Módulo | Qué hace |
|---|---|
| `fuentes.py` | Carga y escribe `sources/*.yaml` (conserva comentarios, orden de claves fijo); `norma_de()` arma el prefijo de los pasajes |
| `importar_inventario.py` | Empata el xlsx con `sources/` por cuerpo canónico (no por doc_id), crea faltantes, asigna prioridad/ola/estado |
| `red.py` | Cliente HTTP cortés (pausa por host, reintentos), decodificación cp1252/utf-8, quita `<script>` (incluidos los inyectados por proxies) |
| `resolver.py` | Patrones por fuente + validación por contenido (la Corte responde 200 con una página de error de 8 KB) |
| `descargar.py` | Senado: sigue "Siguiente" por las páginas `_prNNN` y baja el JS de notas de cada una |
| `parsers/senado.py` | Artículos, ruta Libro/Título/Capítulo, notas de vigencia, tachados fuera, firmas fuera |
| `parsers/corte_constitucional.py` | Relatoría (HTML de Word): ficha (ponente, fecha, referencia, resuelve), descriptores, secciones con subtítulos; sin notas al pie, índices ni firmas |
| `parsers/pdf.py` | Normas con articulado en PDF (Decisiones Andinas de la CAN): misma estructura que el Senado |
| `parsers/funcion_publica.py` | Gestor Normativo de Función Pública (HTML, no PDF): decretos únicos con numeración `2.2.1.1.1.1` y leyes que el Senado no tiene; notas "NOTA:" a vigencia; repara el doble encoding de la fuente |
| `metadatos.py` | Vigencia (`vigente/modificado/derogado/inexequible/desconocida`) y línea compacta de notas |
| `segmentar.py` | Leyes: un fragmento por artículo (partes con "(continuación)" si pasa de ~2000 caracteres). Sentencias: ficha + descriptores + bloques por sección. Texto literal con offsets exactos |
| `reporte.py` | Tablero: avance por ola, cobertura ponderada del seed y techo de la muestra |
| `manifest.py` | `corpus_manifest.json` con sha256 del `.txt` procesado |
| `relatoria_cc.py` | Cosecha por número de toda la relatoría de la Corte Constitucional (C, T, SU desde 1992): sondeo por tamaño (Range de 1 byte), descarga validada, inventario en `sources/relatoria_cc.yaml` y listado en `sources/relatoria_cc_urls.md`. Descarga completa: `python -m src.ingest.relatoria_cc --anios 1992-2026 --hilos 3 --pausa 1.0` |

## Decisiones que conviene conocer

- **Encabezado:** todo fragmento empieza con `fuentes.norma_de(doc)` + `". "`. Sin
  eso el evaluador no reconoce el respaldo. Lo verifica `segmentar.verificar_encabezados`
  y `tests/test_fragmentos.py`.
- **Números con ceros:** el extractor oficial compara números como texto
  (`Decreto 046 de 2024` ≠ `Decreto 46 de 2024`). El `nombre_citable` conserva la
  forma del seed/banco.
- **Artículos sin ancla:** el Senado omite a veces el ancla de un artículo real
  (CGP 531, Constitución 290). Se acepta un "ARTÍCULO N" sin ancla solo en
  mayúsculas, si el párrafo anterior no termina en ":" ("quedará así:") y si N sigue
  la numeración; así los artículos citados dentro de leyes de reforma no se parten.
- **Notas de vigencia dentro del pasaje:** las "Notas de vigencia" y "Jurisprudencia
  vigencia" van al final del fragmento (≤ 600 caracteres). La "Legislación anterior"
  (texto viejo) solo queda en `corpus/interim/`.
- **Sentencias:** cada fragmento empieza con "Sentencia C-355 de 2006, Corte
  Constitucional. <Sección> > <subtítulo>." La `ficha` resume ponente, fecha y lo
  resuelto (preguntas de "sentido del fallo"). Se indexan todas las secciones con
  `seccion` como metadato (`antecedentes`, `demanda`, `intervenciones`,
  `concepto_procurador`, `consideraciones`, `decision`, `salvamento_voto`,
  `aclaracion_voto`, `anexo`...): intervenciones y votos particulares pesan mucho en
  volumen y no son la posición de la Corte, así que conviene que la recuperación los
  penalice o filtre (decisión de A/B, no de la ingesta).
- **Pendiente:** Corte Suprema (SL/SC/SP) — URL manuales y parser de sentencias en PDF.
- **Relatoría CC completa:** T y SU comparten la numeración del año, C lleva la suya;
  la relatoría solo publica en HTML una parte de las C (~25-35 % de los números).
  Con ráfagas (6 hilos, 0,3 s) el sitio bloquea la IP unos minutos: usar ≤3 hilos y
  1 s de pausa. Las sentencias cosechadas van en ola 3: `extraer`/`segmentar --ola 3`
  las procesaría todas (~108 fragmentos por sentencia); decidir antes qué entra al índice.
