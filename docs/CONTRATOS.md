# Contratos de datos

Formatos que se pasan entre módulos. Si un módulo cambia uno, se actualiza aquí.
Reglas de fondo en `CLAUDE.md`; formato de entrega oficial en `schema/submission.schema.json`.

## 1. `sources/*.yaml` → `src/ingest/`

Ver `sources/README.md`. Clave: `doc_id`, `nombre_citable`, `canonico`, `estado`, `ola`.
Las URL efectivas viven en `sources/urls.lock.json` (lo escribe `src/ingest/resolver.py`).

## 2. `corpus/raw/<doc_id>/` y `corpus/interim/<doc_id>.json`

`raw/` guarda los bytes originales y `_descarga.json` (URL, fecha de consulta,
sha256 por archivo). `interim/` guarda la estructura extraída: preámbulo, artículos
(`articulo`, `ruta`, `parrafos`, `notas` por tipo, `pagina`) y `qa` (conteo, saltos,
duplicados). Ninguno de los dos entra al índice.

## 3. `corpus/processed/<doc_id>.txt` y `fragmentos.jsonl`

`<doc_id>.txt` es la concatenación de los textos de sus fragmentos separados por
una línea en blanco (`"\n\n"`). Por eso el `texto` de un pasaje es **literal**: `txt[inicio:fin] == texto`,
encabezado incluido (así lo pide el schema y lo usa el ejemplo oficial).

`fragmentos/<doc_id>.jsonl` por documento y `fragmentos.jsonl` con todos, en orden
`(doc_id, posición)`. `fragmentos.jsonl` es la única entrada de `src/index/construir.py`.

```json
{"chunk_id": 1463,
 "frag_id": "ley_472_1998:art_3:0",
 "doc_id": "ley_472_1998",
 "norma": "Ley 472 de 1998",
 "tipo": "ley", "numero": "472", "anio": "1998",
 "articulo": "3",
 "seccion": null,
 "ruta": ["TITULO I. OBJETO, DEFINICIONES, ...", "CAPITULO II. DEFINICIONES"],
 "organo_emisor": "Congreso de la República",
 "vigencia": "vigente",
 "parte": 0, "n_partes": 1,
 "inicio": 1834, "fin": 2410,
 "texto": "Ley 472 de 1998. TITULO I. ... > CAPITULO II. DEFINICIONES. ARTICULO 3o. ...",
 "cuerpos": [["ley", "472", "1998"], ["jurisprudencia", "C-569", "2004"]],
 "url": "http://www.secretariasenado.gov.co/senado/basedoc/ley_0472_1998.html"}
```

- `texto` = `norma` (+ alias entre paréntesis) + `". "` + ruta + cuerpo del artículo
  (+ línea `Notas de vigencia: …`). El prefijo es obligatorio: el evaluador extrae
  las citas de respaldo del texto de los pasajes.
- `chunk_id` = fila en `fragmentos.jsonl` (y en el índice); cambia si cambia el
  corpus. `frag_id` es estable entre builds: `<doc_id>:art_<n>[~k]:<parte>` o
  `<doc_id>:encabezado:<parte>`.
- Artículos de más de ~2000 caracteres se parten en `parte`/`n_partes`; las partes
  siguientes repiten el prefijo con `ARTÍCULO N (continuación).`
- `seccion`: `encabezado` en el preámbulo de una ley; en sentencias, `ficha`,
  `descriptores`, `sintesis`, `antecedentes`, `norma_demandada`, `demanda`,
  `intervenciones`, `concepto_procurador`, `pruebas`, `consideraciones`, `decision`,
  `salvamento_voto`, `aclaracion_voto`, `anexo` o `cuerpo`. `articulo` null en
  ambos casos; en sentencias `ruta` = [subtítulo vigente] y `frag_id` =
  `<doc_id>:<seccion>[~k]:<parte>`.
- `vigencia`: `vigente` | `modificado` | `derogado` | `inexequible` | `desconocida`.
- `cuerpos`: `citations.bodies(citations.extract(texto))` precalculado; es el
  respaldo que este pasaje aporta ante el evaluador.

## 4. `corpus/index/`

| Archivo | Contenido |
|---|---|
| `embeddings.npy` o `index.faiss` | vectores normalizados, fila *i* = `chunk_id` *i* |
| `bm25/` | índice serializado de bm25s |
| `metadata.jsonl` | copia de `fragmentos.jsonl` en el mismo orden (fila *i* ↔ vector *i*) |
| `config.json` | encoder, dimensión, prefijos (`query:`/`passage:` si es E5), fecha, sha256 de `fragmentos.jsonl` |

## 5. Tipos entre etapas — `src/common/types.py`

| Tipo | Campos | Produce → consume |
|---|---|---|
| `Question` | `id`, `formato`, `pregunta`, `opciones`, `area` | `main`/`api` → planner |
| `Passage` | `doc_id`, `chunk_id`, `norma`, `articulo`, `texto`, `inicio`, `fin`, `score`, `fuente_query` | retrieval → generation → submission |
| `Answer` | claves oficiales del formato + `abstencion` + `pasajes_recuperados` (+ `latencia_ms`) | generation → verification → submission |
| `Verdict` | `OK`, `CITA_SIN_RESPALDO`, `EVIDENCIA_INSUFICIENTE` | verification → pipeline |
| `Trace` | `question_id`, `subqueries`, `passages_by_query`, `fused_passages`, `verdicts`, `iterations`, `timings`, `llm_calls`, `fallback`, `dropped_citations`, `filled_fields`, `abstention_reason` | pipeline → `traces.jsonl`, api |

`Answer.to_submission()` emite solo lo que pide el schema: de cada `Passage`,
`doc_id`, `inicio`, `fin`, `texto`, `score`. `chunk_id`, `norma`, `articulo` y
`fuente_query` quedan en el `Trace`. `fuente_query` es la subconsulta que trajo
el pasaje, o `"lookup"`.

Máximo 10 pasajes (`fusion.max_passages`): el LLM ve exactamente los que se entregan.

## 6. Salida del decoder por formato (enunciado, paso 3)

| Formato | Claves | Límites |
|---|---|---|
| `multiple_choice` | `respuesta_correcta` (A–D), `justificacion`, `descarte_opciones` | `justificacion` debe citar la norma |
| `semi_open` | `respuesta`, `palabras_clave`, `referencia_legal` | 3–5 oraciones, ≤150 palabras |
| `open_ended` | `marco_normativo`, `analisis`, `jurisprudencia`, `conclusion` | `analisis` 5–8 oraciones |

Abstención: `abstencion: true`, campos de texto `""`, `respuesta_correcta: null`;
los pasajes se conservan si los hubo. Sin abstención, `pasajes_recuperados` no
puede ir vacío.

## 7. `submissions.jsonl` (raíz del repo)

Una línea por ítem, esquema oficial. `latencia_ms` opcional. Se valida con
`src/submission/validate.py` y con `scripts/evaluate.py` antes de entregar.

## 8. API — `POST /preguntar`

```json
// request
{"pregunta": "...", "formato": "semi_open", "opciones": null, "config": "configs/baseline.yaml"}
// response
{"answer": { /* Answer: claves del formato, abstencion, pasajes_recuperados */ },
 "trace":  { /* Trace: subqueries, fused_passages (con norma y articulo), verdicts, iterations, timings */ },
 "normas_citadas": [{"cita": "Ley 472 de 1998, art. 3", "respaldada": true}]}
```

El pipeline se construye una vez al arrancar con `registry.build_pipeline(cfg)`.
La interfaz muestra `trace.fused_passages` y `normas_citadas` (3 de los 10 puntos
de interfaz); `trace.timings` sirve para mostrar latencia por etapa.

## 9. Corridas — `eval/runs/<AAAA-MM-DD_HHMM>_<pipeline>/`

| Archivo | Contenido |
|---|---|
| `submission.jsonl` | sección 7 |
| `report.json` | salida de `scripts/evaluate.py` |
| `traces.jsonl` | un `Trace.to_json()` por pregunta |
| `config.yaml` | config fusionada usada |
| `corrida.json` | config, split, ids, commit, inicio/fin y `terminada` |
| `validacion.json` | problemas de `src/submission/validate.py` (deben ser 0) |
| `errores.jsonl` | solo si un ítem lanzó una excepción; se reintenta al reanudar |

`src/main.py` escribe cada ítem al terminarlo: relanzar con el mismo `--out`
(o `--reanudar`) sigue donde quedó; la config debe ser idéntica.

La entrega final (`submissions.jsonl` en la raíz) es la `submission.jsonl` de la
corrida elegida; su `traces.jsonl` se conserva para la verificación en vivo.

## 10. Paquete publicado — `corpus/dist/corpus_<equipo>.zip`

Estructura exigida por `docs/kit/entregables/sabado/README.md`:

```
corpus_<equipo>.zip
├── LICENSE                 # CC-BY-4.0
├── corpus_manifest.json    # copia del de la raíz
├── corpus/                 # ← corpus/processed/<doc_id>.txt
└── indice/                 # ← corpus/index/*
    ├── index.faiss (o embeddings.npy), bm25/, config.json
    └── chunks.jsonl        # ← corpus/processed/fragmentos.jsonl (renombrado)
```

## 11. `corpus_manifest.json`

Campos por documento (plantilla oficial): `doc_id`, `titulo`, `fuente`, `url`,
`fecha_consulta`, `areas`, `n_articulos`, `n_fragmentos`, `metodo_ingesta`,
`sha256` (del `.txt` procesado). Lo genera `src/ingest/manifest.py`; debe coincidir
con el inventario de `CORPUS.md`.
