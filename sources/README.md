# sources/

Qué descargar. Un YAML por área más `transversales.yaml`: las 186 normas de
`data/seed_targets.json`, los 6 códigos que `scripts/citations.py` reconoce y el seed
omite, 4 normas de los `legal_basis` de `data/sample_50.jsonl` y 123 documentos más
del inventario del equipo (`docs/inventario_fuentes_corpus.xlsx`, importado con
`python -m src.ingest.importar_inventario`). **Esta carpeta es la fuente de verdad**;
el xlsx es la vista de planeación y se reimporta sin duplicar (empate por cuerpo
canónico). Cada entrada termina como un documento en `corpus_manifest.json`.

| Archivo | Documentos |
|---|---:|
| `administrativo.yaml` | 35 |
| `civil.yaml` | 26 |
| `comercial.yaml` | 25 |
| `constitucional.yaml` | 48 |
| `familia.yaml` | 40 |
| `laboral.yaml` | 46 |
| `mercados.yaml` | 25 |
| `penal.yaml` | 31 |
| `procesal.yaml` | 12 |
| `transversales.yaml` | 2 |
| `tributario.yaml` | 29 |
| **Total** | **319** |

## Campos

| Campo | Uso |
|---|---|
| `doc_id` | snake_case; nombre de `corpus/processed/<doc_id>.txt` y clave en el manifiesto |
| `nombre_citable` | prefijo obligatorio de cada pasaje. Verificado: `citations.extract("<nombre_citable>. ARTICULO 5.")` devuelve exactamente `canonico` |
| `tipo`, `numero`, `anio`, `organo_emisor` | metadatos exigidos por el paso 1 |
| `fuente`, `donde_buscar` | origen declarado (`donde_buscar` es la búsqueda que da el kit) |
| `url` | **override manual**: si no está vacío, el resolvedor usa esta URL (y la valida) en vez de sus patrones. La URL efectiva queda en `urls.lock.json` |
| `alias_citables` | nombres adicionales del mismo texto que el extractor lee como otro cuerpo; van entre paréntesis en el prefijo del pasaje (Ley 2452 de 2025 = Código Procesal del Trabajo y de la Seguridad Social) |
| `items_del_banco`, `areas` | peso en el banco según el seed (null = no está en el seed) |
| `canonico` | tupla que usa el evaluador para comparar citas |
| `origen` | `seed_targets`, `citations.CODES`, `sample_50.legal_basis` o `inventario_xlsx` |
| `prioridad` | `alta` / `media` / `baja` (del xlsx; si no, por `items_del_banco`) |
| `ola` | 0 piloto (Constitución, CGP, Ley 472) · 1 los 15 cuerpos de `CODES` + Ley 80, Ley 2220, Decreto 2153, Ley 1116 · 2 resto del seed, muestra y altas · 3 resto |
| `estado` | `pendiente` (se procesa) · `por_verificar` (número, año o identidad dudosos: solo con `--ids`) · `excluido` (con `motivo_exclusion`, va a "descartados" de CORPUS.md) |
| `justificacion` | por qué está: área, sub-tareas, ítems del banco (del xlsx) |

## `urls.lock.json`

Lo escribe `python -m src.ingest.resolver`: por `doc_id`, `estado` (`ok`,
`no_encontrado`, `manual`), `url`, `parser` (`senado`, `corte_constitucional`,
`pdf`), fecha y las URL probadas con el motivo del rechazo. Se versiona: es la
declaración de "corpus reconstruible a partir de las URL". Para resolver a mano un
`no_encontrado` o `manual`, poner la URL en el campo `url` del YAML y volver a
correr el resolvedor con `--ids`.

## Agrupación

Cada documento aparece en un solo archivo para no descargarlo dos veces; `areas`
conserva todas sus áreas. Regla: Constitución y CGP → transversales; si no, el
área de menor peso en el banco entre las suyas (la más específica), salvo
excepciones explícitas (Ley 80 de 1993 → administrativo).

Las sentencias SL/SC/SP son de la Corte Suprema aunque el `donde_buscar` del kit
apunte a la relatoría de la Corte Constitucional.
