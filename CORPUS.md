# Bitácora del corpus — RMSE

Corpus de normas y jurisprudencia colombianas para el sistema de recuperación del reto.
Corte de esta bitácora: **2026-10-03** (índice congelado con la entrega). Todas las cifras
salen de `corpus_manifest.json`, `sources/` y de las corridas versionadas en `eval/runs/`.

| | |
|---|---|
| Documentos | **29.137**: 473 normas y sentencias seleccionadas una a una, más las 28.664 sentencias de la relatoría de la Corte Constitucional (C, T y SU, 1992-2026) |
| Fragmentos indexados | **1.543.025** |
| Huella del corpus (`sha256` de `fragmentos.jsonl`) | `288d593ab0750427c3550b9dd9d71b881a96c42266952fc371c0a186214f55fe` |
| Citas del banco cubiertas (según `data/seed_targets.json`) | **544 de 559 (97 %)** recuperables; 546 con texto en el corpus (dos sentencias de la Corte Suprema están en una compilación que quedó fuera de la recuperación, §3) |
| Citas de la muestra respaldables con el corpus | **49 de 49 cuerpos (100 %)** |
| Licencia | CC-BY-4.0 |

---

## 1. Inventario

Un registro por documento incorporado; coincide fila a fila con `corpus_manifest.json`
(mismo `doc_id`, URL y fecha de consulta). Los 473 documentos seleccionados uno a uno están al
final de este archivo ([Anexo — Inventario de la selección manual](#anexo--inventario-de-la-selección-manual));
el inventario completo, con las 28.664 sentencias de la relatoría cosechadas por número, está en
[`docs/INVENTARIO_COMPLETO.md`](docs/INVENTARIO_COMPLETO.md). Ambos los genera
`tools/inventario_corpus.py` desde el manifiesto.

**Totales**

| Métrica | Valor |
|---|---:|
| Documentos incorporados | 29.137 |
| Artículos indexados (normas) | 39.493 |
| Fragmentos en el índice | 1.543.025 |
| Tamaño del corpus procesado | 2,31 GB de texto (2.312.071.077 bytes) |

**Composición por tipo:** 28.943 sentencias (28.792 de la Corte Constitucional, 137 del
Consejo de Estado y 14 documentos de la Corte Suprema de Justicia: 13 sentencias y una
compilación de reseñas de su relatoría), 134 leyes, 38 decretos, 13 códigos, la Constitución
Política, 3 Decisiones de la Comunidad Andina, la Circular Básica Jurídica de la
Superintendencia Financiera, 2 resoluciones, 1 acuerdo (Reglamento de la Corte Constitucional)
y 1 boletín de jurisprudencia de la Superintendencia de Sociedades.

**Composición por fuente:** relatoría de la Corte Constitucional (28.792), Secretaría del
Senado (145), SAMAI del Consejo de Estado (137), Gestor Normativo de Función Pública (25),
relatoría de la Corte Suprema de Justicia (14), SUIN-Juriscol (12), normograma de la Cancillería
(4), Comunidad Andina (3), SISJUR de la Alcaldía de Bogotá (1), Superintendencia Financiera (1),
normograma de la DIAN (1), Ministerio de Ambiente y Desarrollo Sostenible (1) y
Superintendencia de Sociedades (1).

## 2. Criterio de selección

### Punto de partida: lo que el banco cita

La selección parte de las normas que el propio banco usa como fundamento, no de una lista
genérica de "normas importantes":

1. **Las 186 normas de `data/seed_targets.json`**, con el número de ítems del banco que
   cita cada una. Son el núcleo del corpus y fijan su prioridad.
2. **Los 6 códigos que el extractor oficial (`scripts/citations.py`) reconoce por nombre**
   y que el seed no lista; sin ellos, una cita como "artículo 1502 del Código Civil" no
   tendría respaldo posible.
3. **Las normas de los `legal_basis` de `data/sample_50.jsonl`** que no estaban en el seed (4).
4. **El inventario del equipo** (`docs/inventario_fuentes_corpus.xlsx`, 123 documentos más),
   priorizado por área y sub-tarea.
5. **Huecos detectados al medir** (30-09 y 01-10): normas que la evaluación de la muestra
   mostró ausentes (sentencias de la Corte Suprema citadas por el banco, salario mínimo
   vigente, reforma del CPACA, sentencias de unificación del Consejo de Estado, Circular
   Básica Jurídica de la Superintendencia Financiera, leyes que el propio corpus cita).
6. **La relatoría completa de la Corte Constitucional** (01 y 02-10), por la razón que se
   explica abajo.
7. **Normas que nombra el conjunto de evaluación** (03-10). Las 992 preguntas del sábado
   llegan sin respuestas; antes de la entrega se cruzaron las normas y sentencias que **nombran**
   con el corpus y se incorporaron las ausentes que tienen texto oficial: la Resolución 368 de
   2014 de MinAmbiente (23 preguntas la piden leer; ya estaba en el inventario por la pregunta
   748 de la muestra, sin fuente), las leyes 99 de 1993, 45 de 1990, 1210 de 2008, 1934 de 2018
   y 2274 de 2022, los decretos 1382 de 2000, 4302 de 2008 y 678 de 2020, la SL3871-2021, la
   SU-040 de 2018 (la cosecha la había saltado) y el Boletín de Jurisprudencia n.º 5 de 2016 de
   la Superintendencia de Sociedades; además, la compilación "Contratos civiles y comerciales",
   tomo 3, de la relatoría de la Sala de Casación Civil, que trae dos sentencias que el seed
   cita y faltaban (SC1121-2018 y SC3674-2021); en la recuperación general sus 1.241 reseñas
   desplazaban a las normas (RAGAS medio de la muestra 14,42 frente a 15,20 sin ella), así que quedó en
   el corpus pero fuera de la recuperación (§3). Solo entran textos normativos y judiciales de
   fuentes oficiales: ninguna pregunta ni respuesta (`tests/test_sin_fuga.py`). Las normas que
   las preguntas solo ofrecen como opción incorrecta, las leyes ficticias de un caso hipotético
   y los alias de códigos que ya están (Decreto 410 de 1971 = Código de Comercio) no se
   agregaron.

`sources/*.yaml` es la fuente de verdad de esta selección: cada documento declarado lleva su
cita canónica, áreas, peso en el banco, prioridad, ola de ingesta y justificación.

### La relatoría completa de la Corte Constitucional

En la muestra, 11 de las 30 preguntas semiabiertas giran sobre una sentencia concreta ("¿cuál
es el problema jurídico de la T-256 de 2025?"). Todas las que nombra la muestra se habían
agregado a mano después de verla; extrapolando al banco, del orden de 60 a 100 preguntas del
test dependen de sentencias que una selección manual no anticipa. Por eso se cosechó **toda
la relatoría** por número (`src/ingest/relatoria_cc.py`): 28.795 URL publicadas, 28.663
sentencias incorporadas (las demás ya estaban en el inventario o, en tres casos, la página
publicada está rota).

Incorporarla tiene un costo medido. Con la relatoría en la recuperación general, el ~97 %
de los fragmentos son sentencias y desplazan a la norma aplicable: el total sobre la muestra
bajó a 52,40 (/80), frente a 58,02 con la misma configuración sobre el corpus anterior. La relatoría cosechada se dejó entonces **fuera de la
recuperación general y accesible solo por número** (el lookup trae la sentencia cuando la
pregunta la nombra): el total volvió a 58,62 y las 60 sentencias de una sonda de preguntas
"¿qué decidió la Corte en la sentencia X?" llegaron todas a la evidencia
(`eval/barrido_topes.py`; filas del 02-10 en `eval/runs/README.md`).

### Cobertura por área

Cobertura medida como la fracción de citas del banco (según el seed, ponderadas por número
de ítems) cuyo cuerpo normativo está en el corpus. Un documento puede servir a varias áreas;
las sentencias de la relatoría cosechada cuentan en el área constitucional (no se
clasificaron una a una).

| Área | Ítems en el banco | Documentos incorporados | Cobertura estimada |
|---|---:|---:|---|
| Derecho constitucional | 134 | 28.733 | 195/197 citas del seed (99 %) |
| Derecho administrativo | 124 | 181 | 128/131 citas del seed (98 %) |
| Derecho penal | 123 | 34 | 184/185 citas del seed (99 %) |
| Derecho procesal | 111 | 21 | 182/184 citas del seed (99 %) |
| Derecho comercial y sociedades | 104 | 33 | 202/204 citas del seed (99 %) |
| Derecho civil | 102 | 34 | 150/151 citas del seed (99 %) |
| Derecho de familia | 93 | 45 | 197/197 citas del seed (100 %) |
| Derecho tributario | 92 | 56 | 211/212 citas del seed (100 %) |
| Derecho laboral | 87 | 56 | 178/180 citas del seed (99 %) |
| Derecho de los mercados | 72 | 30 | 219/220 citas del seed (100 %) |

### Frente a las sub-tareas del banco

Las sub-tareas del enunciado (§4.2) piden cosas distintas al corpus, y eso decidió *cómo*
se incorporó cada fuente, no solo *cuál*:

- **Reproducción literal, existencia normativa, jerarquía, vigencia temporal.** Exigen el
  texto exacto y vigente del artículo. Por eso las leyes se toman del Senado, de Función
  Pública y de SUIN-Juriscol **con sus notas de vigencia** (derogaciones, modificaciones,
  exequibilidad), el texto tachado se descarta y cada fragmento es un artículo completo.
- **Sentido del fallo, precedente jurisprudencial, fundamento central (ratio decidendi),
  problema jurídico, supuestos fácticos.** Exigen la sentencia y no un resumen. Cada sentencia
  se segmenta por sección (antecedentes, demanda, consideraciones, decisión, salvamentos) y
  tiene un fragmento **ficha** con ponente, fecha, referencia y lo que resolvió, que es lo
  que responde "qué decidió la Corte". La relatoría completa cubre las sentencias que el
  banco nombre y la selección manual no anticipó.
- **Autoridad competente, juez que decide, postura procesal.** Exigen los códigos
  procesales completos (CGP, CPACA y su reforma por la Ley 2080 de 2021, Código Procesal del
  Trabajo, Código de Procedimiento Penal) y el Reglamento de la Corte Constitucional.
- **Requisitos y excepciones legales, cálculos de cuantía.** Exigen las cifras de 2026: se
  incorporaron el decreto del salario mínimo (Decreto 159 de 2026), la resolución de la UVT
  (Resolución 238 de 2025) y el auxilio de transporte (Decreto 1470 de 2025).

El banco no cubre derecho ambiental ni internacional (enunciado §4.2), por lo que no se
incorporaron fuentes de esas áreas.

### Documentos descartados y motivo

**Excluidos por decisión de diseño.** Su texto no es citable por el extractor oficial, así
que no pueden sumar en citación, y su volumen compite con las normas en la recuperación:

| Documento | Motivo |
|---|---|
| Doctrina oficial de la DIAN | Doctrina administrativa: no es norma citable por el extractor oficial y su volumen es alto frente a su aporte |
| Decisiones de la SIC (competencia, consumidor, datos) | Decisiones administrativas masivas sin cita extraíble |
| Auto 2025-01-730337 de la Superintendencia de Sociedades | Auto de superintendencia: el extractor oficial no lo reconoce como cita |
| Salvamentos, aclaraciones y autos del Consejo de Estado | Solo se importan las sentencias de unificación: lo demás pesaría en la recuperación sin ser la regla |

**Erratas del banco.** El seed cita normas que no existen con ese número y año. Agregar la
norma correcta no produce acierto (el evaluador compara la cita literal), pero la norma
real sí está en el corpus cuando era identificable:

| Cita del banco | Norma real | ¿En el corpus? |
|---|---|---|
| Ley 1692 de 2017 | Ley 1692 de 2013 (convenio con Portugal) | Sí |
| Decreto 1563 de 2012 | Ley 1563 de 2012 (Estatuto de Arbitraje) | Sí |
| Ley 1150 de 2005 / Ley 11500 de 2007 | Ley 1150 de 2007 (contratación estatal) | Sí |
| Ley 964 de 2006 | Ley 964 de 2005 (mercado de valores) | Sí |
| Ley 116 de 2006 | Ley 1116 de 2006 (insolvencia) | Sí |
| Ley 2737 de 1989 | Decreto 2737 de 1989 (Código del Menor, derogado) | No |
| Ley 23 de 1961 | Sin identificar con certeza | No |

**No obtenidos.** Declarados en `sources/` pero sin una versión con texto utilizable en una
fuente admitida al corte de esta bitácora:

| Documento | Ítems del banco | Situación |
|---|---:|---|
| Sentencias SC-1121/2018, SC-3674/2021 y SL-1972/2025 (Corte Suprema) | 1 c/u | Sin ruta predecible por número en la relatoría de la Corte Suprema. Las dos primeras solo aparecen reseñadas en la compilación "Contratos civiles y comerciales", tomo 3, que está en el corpus pero fuera de la recuperación (§3) |
| Sentencia SU-488 de 2011 | 1 | No existe en la relatoría con ese número (sí la SU-448 de 2011, en el corpus) |
| Sentencia SU-279 de 2019 (nombrada en una pregunta del test) | — | No existe en la relatoría con ese número (sí la T-279 de 2019, en el corpus) |
| Sentencia T-248 de 2025 | 1 | La relatoría devuelve su página de error (probada el 02 y el 03-10; sí está la T-248 de 2024) |
| Sentencia SU-6 de 1991 | 1 | La Corte Constitucional empezó a fallar en 1992; número y año por verificar |
| Sentencia de unificación 2020CE-SUJ-4-005 (Consejo de Estado) | — | Sin URL estable ni exportación en SAMAI; además, el extractor oficial no reconoce sentencias del Consejo de Estado por radicado |
| Sentencias hito de las salas Laboral y Penal de la CSJ, dos sentencias civiles de la CSJ citadas por fecha | — | Sin identificación precisa (número y año) para resolverlas |

## 3. Método de ingesta y limpieza

Un pipeline reproducible en `src/ingest/`, un paso por módulo, cada uno idempotente y
ejecutable por documento (`--ids`) o por ola (`--ola`). Reconstrucción completa desde las URL
declaradas:

```bash
python -m src.ingest.resolver && python -m src.ingest.descargar && python -m src.ingest.extraer
python -m src.ingest.relatoria_cc --anios 1992-2026 --hilos 3 --pausa 1.0   # relatoría por número
python -m src.ingest.segmentar && python -m src.ingest.manifest
python -m src.index.construir --partes bm25 denso
```

1. **Descarga.** `resolver` fija la URL directa de cada documento en
   `sources/urls.lock.json`, probando patrones conocidos por fuente (Senado
   `basedoc/ley_0472_1998.html`; relatoría de la Corte Constitucional `relatoria/2006/C-355-06.htm`)
   y **validando el contenido, no el código HTTP**: número y año visibles en el documento,
   marcador de documento del Senado, firma `%PDF-`. `descargar` guarda los originales en
   `corpus/raw/<doc_id>/` con un `_descarga.json` que registra URL, fecha de consulta, tamaño y
   `sha256` de cada archivo. Las páginas encadenadas del Senado (`_prNNN`) y el JavaScript de
   sus notas de vigencia se descargan completos. Tres fuentes sin enlace por documento tienen
   importador propio: **SAMAI** (Consejo de Estado: zip por providencia con su ficha oficial;
   solo sentencias de unificación), la **Circular Básica Jurídica de la SFC** (zip oficial
   por capítulos) y los textos consolidados de **SUIN-Juriscol** vía `legalize-co`.
2. **Relatoría de la Corte Constitucional por número.** La relatoría no tiene índice
   navegable, así que `relatoria_cc` enumera los números de cada año: T y SU comparten la
   numeración y C lleva la suya; la existencia se prueba por tamaño (petición `Range` de un
   byte: la página de error pesa 8,6 KB) y cada sentencia descargada se valida por contenido.
   Listado completo de URL en `sources/relatoria_cc_urls.md` (28.795); inventario en
   `sources/relatoria_cc.yaml`.
3. **Extracción de texto.** Un parser por fuente (`src/ingest/parsers/`): HTML del Senado y de
   los normogramas con el mismo formato (artículos, ruta, notas, sin tachados ni scripts), HTML
   de la relatoría de la Corte Constitucional (ficha, descriptores y secciones), HTML del
   Gestor Normativo de Función Pública, Markdown de SUIN-Juriscol, PDF con articulado
   (Decisiones Andinas), **PDF de sentencias de la Corte Suprema** (y compilaciones de su
   relatoría), DOC/DOCX/PDF de SAMAI y de la SFC. **OCR** con EasyOCR (abierto, Apache 2.0)
   para los PDF escaneados o con capa de texto ilegible (SC-18392/2017, SP-1945/2019 y la
   Resolución 368 de 2014, publicada por MinAmbiente como imagen). La
   estructura intermedia queda en `corpus/interim/<doc_id>.json` con un bloque `qa`.
4. **Normalización.** Codificación (la fuente declara un charset y sirve otro; caracteres de
   control y doble codificación de Función Pública; símbolos del área privada de Word en los PDF),
   eliminación de navegación, firmas, constancias, notas al pie y texto tachado.
5. **Segmentación.** Leyes y códigos: **un fragmento por artículo**; si supera 2.000
   caracteres se parte en `parte`/`n_partes` repitiendo el encabezado "(continuación)".
   Sentencias: un fragmento `ficha` y una serie por sección con el subtítulo vigente. Cada
   fragmento **empieza con el nombre citable de su norma** ("Ley 472 de 1998. TÍTULO I. … >
   ARTÍCULO 3o."); una prueba verifica que el extractor oficial lea en esos primeros caracteres
   la norma propia del fragmento. El texto es literal: `txt[inicio:fin] == texto`.
6. **Extracción de metadatos.** Por fragmento: tipo de norma, número, año, artículo, sección,
   ruta jerárquica (Libro > Título > Capítulo), órgano emisor, vigencia
   (`vigente`/`modificado`/`derogado`/`inexequible`, a partir de las notas) y los cuerpos
   normativos que cita su texto, precalculados con el extractor oficial.
7. **Indexación.** Encoder denso `BAAI/bge-m3` (1.024 dimensiones, vectores normalizados,
   búsqueda exacta por producto interno sobre `embeddings.npy`) más índice léxico BM25 (`bm25s`,
   variante Lucene, k1 = 1,5, b = 0,75, tokenizador propio que conserva "C-355", "240-1" y
   "2.2.1.1.1" como un solo término). El índice registra el `sha256` de `fragmentos.jsonl` y
   se niega a cargar si el corpus no coincide. La relatoría cosechada está en el índice
   completo, pero la recuperación general la excluye por máscara y la trae solo por número
   (§2); lo mismo la Resolución 368 de 2014 (`retrieval.solo_lookup`), que nombrada ocupaba
   los 10 pasajes de su bloque y desplazaba el CPACA de referencia, y la compilación de la
   Sala de Casación Civil, cuyas reseñas desplazaban a las normas en preguntas civiles y
   comerciales (como su nombre no es una cita, el lookup no la alcanza: en la práctica queda
   fuera de la recuperación). Al agregar documentos,
   `python -m src.index.construir --reusar` reutiliza el vector de cada fragmento cuyo texto ya
   estaba indexado y codifica solo los nuevos (1.404 el 03-10, en lugar de 1,5 M).

**Garantía de no fuga:** el corpus solo contiene documentos del inventario y de fuentes
públicas, y ningún fragmento contiene una pregunta de `data/`, incluidas las 992 del test
(`tests/test_sin_fuga.py`, verificado sobre los 1.543.025 fragmentos del corpus final el 03-10).

### Problemas encontrados y cómo se resolvieron

| Problema | Solución |
|---|---|
| La relatoría de la Corte Constitucional responde HTTP 200 con una página de error cuando el archivo no existe | Validación por contenido (tamaño mínimo, número y año presentes) en lugar del código HTTP |
| La relatoría no publica un índice por año (403) y su buscador devuelve listados parciales | Enumeración por número, con existencia probada por tamaño (`Range` de un byte) sin descargar el archivo |
| T y SU comparten la numeración del año; la publicación tiene huecos (fallos aún sin publicar) y 1992 salta de la T-015 a la T-420 | El recorrido prueba T y luego SU por número y se detiene tras 100 números vacíos; 1992 se recorrió hasta el 700 |
| Con 6 hilos el sitio de la Corte bloqueó la IP unos minutos | Descarga con 3 hilos y 1 s de pausa; ante errores de red seguidos, espera de 10 minutos; un error de red no marca la sentencia como inválida |
| El Senado no publica todo: decretos únicos (1072, 1074, 1082, 1625, 2555) y leyes antiguas | Parser del Gestor Normativo de Función Pública y de SUIN-Juriscol |
| Función Pública no envía su certificado intermedio | Validación TLS con las autoridades del sistema (`truststore`) |
| Artículos que el Senado deja sin ancla, y leyes de reforma que reproducen el artículo que modifican ("… quedará así: Artículo 23.") | El parser abre artículo solo si la numeración avanza y el párrafo previo no anuncia una reproducción |
| El parser del Senado copiaba la sentencia de control previo dentro del último artículo de dos leyes estatutarias | El art. 30 de la Ley 1581 de 2012 pasa de 453 fragmentos a 1 y el art. 33 de la Ley 1712 de 2014 de 84 a 1; la C-274 de 2013 queda como documento propio |
| Erratas de la fuente en sentencias ("ANTECENDENTES", "R E S U E L V E" espaciado, índices con número de página) | Reglas tolerantes en el parser de la relatoría; las secciones solo avanzan en el orden natural de una sentencia |
| "Constitución de la sociedad" o "constitución en mora" leídas como la Constitución Política | Salvaguarda en el lookup y en el verificador de citas |
| Sentencias de la Corte Suprema solo disponibles en PDF, sin ruta predecible, algunas escaneadas | URL localizada documento por documento y verificada por contenido; parser de PDF de sentencias; OCR abierto para las escaneadas |
| SAMAI y la SFC no dan un enlace estable por documento | Importadores desde la exportación oficial, con `sha256` de cada archivo en `_descarga.json` |
| La Resolución 368 de 2014 solo se publica como PDF escaneado (sin capa de texto) | OCR abierto; la segmentación por bloques tolera que el OCR lea "1°" como "10" en los ordinales |
| El resolver rechazaba los Markdown cortos de `legalize-co` (decretos de 6-10 KB) por el tamaño mínimo pensado para la página de error de la Corte | Tamaño mínimo propio para esa fuente (2 KB), que no trae plantilla HTML |
| La cosecha por número salta las sentencias declaradas en el inventario manual, aunque estas no tuvieran URL (SU-040 de 2018) | Agregada por número el 03-10; el inventario manual se revisó contra la relatoría publicada |

## 4. Evolución del puntaje

### Construcción del corpus

El corpus se construyó por olas de prioridad. En esta etapa se midió la **cobertura de
citas del banco** (fracción de las citas del seed, ponderadas por ítems, cuyo cuerpo está
en el corpus); el puntaje sobre la muestra exige el sistema completo, disponible desde el 29-09.

| Fecha | Ola | Documentos | Fragmentos | Cobertura del seed | Qué entró |
|---|---|---:|---:|---:|---|
| 2026-09-28 | 0 y 1 | 19 | 12.063 | 51 % | Constitución, CGP, Ley 472 y los 15 cuerpos que el extractor reconoce por nombre, más Ley 80, Ley 2220, Decreto 2153 y Ley 1116 |
| 2026-09-28 | 2 y 3 | 253 | 45.460 | 91 % | Resto del seed y del inventario desde el Senado y la Corte Constitucional; Decisiones Andinas en PDF |
| 2026-09-28 | Función Pública | 275 | 63.162 | 94 % | 22 normas que el Senado no publica (decretos únicos 1072, 1074, 1082, 1625, 2555, 780; leyes antiguas) |
| 2026-09-28 | Confirmadas | 282 | 64.101 | 94 % | 5 sentencias confirmadas por el equipo; Ley 1692 de 2013; Decreto 875 de 2008 |
| 2026-09-30 | Huecos medidos | 298 | 66.291 | 97 % | 9 sentencias de la CSJ, Decreto 1572 de 2024 (smlmv), Decreto 1833 de 2016, leyes 2080/2021, 2191/2022, 1361/2009, 964/2005, Acuerdo 02 de 2015 |
| 2026-10-01 | Limpieza | 299 | 66.281 | 97 % | Sentencia C-274 de 2013 como documento propio; leyes 1581 y 1712 sin la sentencia pegada |
| 2026-10-01 | Huecos medidos | 487 | 94.590 | 97 % | 137 sentencias de unificación del Consejo de Estado (SAMAI), Circular Básica Jurídica de la SFC, cifras de 2026, normas autónomas que el corpus cita, primeras sentencias de la relatoría |
| 2026-10-02 | Relatoría completa | 29.124 | 1.541.204 | 97 % | 28.663 sentencias C, T y SU de 1992 a 2026 cosechadas por número |
| 2026-10-03 | Normas que nombra el test | 29.137 | 1.543.025 | **97 %** | Resolución 368 de 2014 (OCR), 5 leyes, 3 decretos, SL3871-2021, SU-040 de 2018 y boletín de la Superintendencia de Sociedades; compilación de la Sala de Casación Civil (en el corpus, fuera de la recuperación) |

### Puntaje sobre las 50 preguntas de muestra

Evaluador oficial (`scripts/evaluate.py`); la columna /80 incluye la corrección juzgada por
RAGAS. Cada corrida está versionada en `eval/runs/` con su `submission.jsonl`, sus trazas y
su reporte; `eval/runs/README.md` registra todas las variantes probadas.

| Fecha | Documentos | Fragmentos | Cerradas /20 | Citación /20 | Abstención /10 | Total /50 | Total /80 | Qué cambió |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| 2026-09-29 | 282 | 64.101 | 13,33 | 10,83 | 6,67 | 30,83 | 42,08 | Primer sistema completo (49 de 50 ítems: uno degeneró) |
| 2026-09-29 | 282 | 64.101 | 12,00 | 8,37 | 6,19 | 26,56 | 37,63 | Variante de generación sobre el mismo sistema (49 de 50 ítems: uno degeneró) |
| 2026-09-29 | 282 | 64.101 | 14,67 | 13,47 | 7,67 | 35,81 | 49,31 | Ajustes de generación (corrida reportada; sus artefactos no se versionaron) |
| 2026-09-30 | 282 | 64.101 | 14,67 | 15,51 | 8,37 | 38,55 | 51,62 | Contexto del LLM ampliado, campos obligatorios garantizados, referencia legal desde los pasajes |
| 2026-09-30 | 282 | 64.101 | 14,67 | 17,55 | 8,60 | 40,82 | 54,12 | El fundamento de cerradas y semiabiertas cita las normas de los pasajes |
| 2026-09-30 | 282 | 64.101 | 14,67 | 17,14 | 8,37 | 40,18 | 53,22 | Tope de 2 fragmentos por documento (descartado: bajó el puntaje) |
| 2026-09-30 | 298 | 66.291 | 14,67 | 17,96 | 8,60 | 41,23 | 55,41 | 16 documentos nuevos (configuración del sistema sin cambios) |
| 2026-10-01 | 299 | 66.281 | 17,33 | 18,37 | 9,53 | 45,23 | 59,03 | Decoder Llama-3.1-8B-Instruct (benchmark de cinco decoders) |
| 2026-10-02 | 487 | 94.590 | 16,00 | 17,96 | 9,30 | 43,26 | 59,22 | 188 documentos nuevos; fundamento con todas las normas de los 10 pasajes |
| 2026-10-02 | 29.124 | 1.541.204 | 13,33 | 16,33 | 8,14 | 37,80 | 52,40 | Relatoría completa en la recuperación general |
| 2026-10-02 | 29.124 | 1.541.204 | 16,00 | 18,37 | 9,30 | 43,67 | 58,62 | Relatoría fuera de la recuperación general, solo por número (media de cuatro juicios de RAGAS) |
| 2026-10-02 | 29.124 | 1.541.204 | 16,00 | 18,37 | 9,30 | 43,67 | 57,49 | Extensión mínima del enunciado en todas las respuestas (media de dos juicios) |
| 2026-10-03 | 29.137 | 1.543.025 | 16,00 | 17,96 | 9,30 | 43,26 | 57,68 | Sin la extensión mínima (el jurado aclaró que solo rige el máximo de palabras); 13 documentos nuevos, todos en la recuperación general (media de dos juicios) |
| **2026-10-03** | **29.137** | **1.543.025** | **16,00** | **18,37** | **9,30** | **43,67** | **58,87** | **Resolución 368 y compilación de la CSJ solo por número (media de dos juicios, sin ítems fallidos): configuración de entrega** |

### Lectura de la curva

- **El corpus casi no limita ya al sistema en la muestra.** Desde el 29-09, 48 de los 49
  cuerpos normativos de referencia de la muestra estaban en el corpus; las subidas de los
  días siguientes vienen de cambios del sistema, y así se reportan.
- **Más documentos no es mejor por sí solo.** Cada fragmento nuevo compite por los 10 cupos
  de evidencia. La relatoría completa es el caso extremo: en la recuperación general bajó el
  total de la muestra de 58,02 (misma configuración, corpus anterior) a 52,40, porque las
  sentencias desplazaban a la norma aplicable incluso cuando la norma estaba entre los
  pasajes (ítems 308 y 247). Sacarla de la recuperación general y dejarla accesible por
  número devolvió el total a 58,62, igual a la mejor entrega con el corpus de 487 documentos
  dentro del ruido del juez; su ganancia está en las preguntas del test que nombren
  sentencias ausentes del corpus manual, que la muestra no mide.
- **La extensión mínima costaba en RAGAS.** El modelo respondía con menos oraciones de las
  que pide el enunciado (25 de 50 respuestas); completarlas con oraciones literales de la
  evidencia costaba ~1,1 puntos de RAGAS. El 03-10 el jurado aclaró que solo rige el máximo de
  palabras y se apagó.
- **Los documentos nuevos se miden también por desplazamiento.** De los 13 que entraron el
  03-10, dos cambiaron respuestas que no los necesitaban: la Resolución 368 ocupaba los 10
  pasajes de su bloque (la 748 perdió la cita del CPACA) y las 1.241 reseñas de la compilación
  de la Corte Suprema entraron en 7 de 35 respuestas de texto libre (RAGAS medio 14,42 frente a
  15,20 sin ella). Ambos quedaron fuera de la recuperación general y la muestra volvió a 43,67
  deterministas, con 58,87 en total.
- **El juez de RAGAS varía.** Sobre la misma entrada, la corrección cambió hasta 0,9 puntos y
  en cada juicio quedó al menos un ítem sin calificar (cuenta como cero). Las decisiones se
  tomaron sobre los componentes deterministas y sobre la media de varios juicios.

## 5. Licencia

El corpus se publica bajo **CC-BY-4.0**. Los textos normativos y judiciales colombianos
son de dominio público; la licencia cubre el trabajo de procesamiento, segmentación y
extracción de metadatos realizado por el equipo.

---

## Anexo — Inventario de la selección manual

Generado por `tools/inventario_corpus.py` desde `corpus_manifest.json` (mismo `doc_id`, URL
y fecha de consulta). Lista los 473 documentos seleccionados uno a uno. El inventario
completo, con las 28664 sentencias de la relatoría de la Corte Constitucional cosechadas por número
(área constitucional por defecto: no se clasificaron una a una), está en
[`docs/INVENTARIO_COMPLETO.md`](docs/INVENTARIO_COMPLETO.md): 29137 filas, una por documento del manifiesto.

Columnas: identificador, título (nombre citable), fuente, URL de la que se tomó el texto, fecha
de consulta, número de artículos (en sentencias, que se segmentan por sección, el número de
fragmentos) y áreas del banco a las que responde.

| doc_id | Título | Fuente | URL | Fecha de consulta | Artículos | Áreas |
|---|---|---|---|---|---:|---|
| `acuerdo_02_2015` | Acuerdo 02 de 2015 | Alcaldía de Bogotá (SISJUR) | https://www.alcaldiabogota.gov.co/sisjur/normas/Norma1.jsp?i=154021 | 2026-09-30 | 113 | Constitucional |
| `boletin_jurisprudencia_supersociedades_5_2016` | Boletín de Jurisprudencia n.º 5 de 2016 de la Superintendencia de Sociedades | Superintendencia de Sociedades | https://www.supersociedades.gov.co/documents/guest/Prensa/Noticias/Historial%20de%20Noticias/2016/Bolet%C3%ADn%20n5%20%282016%29.pdf | 2026-10-03 | — (23 fragm.) | Comercial y sociedades |
| `circular_externa_029_2014` | Circular Externa 029 de 2014 | Superintendencia Financiera de Colombia | https://www.superfinanciera.gov.co/publicaciones/10083443/normativanormativa-generalcircular-basica-juridica-ce-10083443/ | 2026-10-01 | 2545 | Mercados, Comercial y sociedades |
| `codigo_civil` | Código Civil | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/codigo_civil.html | 2026-09-28 | 2684 | Civil |
| `codigo_comercio` | Código de Comercio. Por el cual se expide el Código de Comercio | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/codigo_comercio.html | 2026-09-28 | 2044 | Comercial y sociedades |
| `codigo_disciplinario` | Código General Disciplinario. Por medio de la cual se expide el Código General Disciplinario, se derogan la Ley 734 de 2002 y algunas disposiciones de la Ley 1474 de 2011, relacionadas con el derecho disciplinario. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_1952_2019.html | 2026-09-28 | 281 | Administrativo |
| `codigo_general_proceso` | Código General del Proceso. Por medio de la cual se expide el Código General del Proceso y se dictan otras disposiciones. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_1564_2012.html | 2026-09-28 | 634 | Civil, Comercial y sociedades, De familia, Mercados, Penal, Procesal, Tributario |
| `codigo_infancia` | Código de la Infancia y la Adolescencia. Por la cual se expide el Código de la Infancia y la Adolescencia. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_1098_2006.html | 2026-09-28 | 217 | De familia |
| `codigo_nacional_policia` | Código Nacional de Seguridad y Convivencia Ciudadana. Por la cual se expide el Código Nacional de Seguridad y Convivencia Ciudadana. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_1801_2016.html | 2026-09-28 | 249 | Procesal |
| `codigo_penal` | Código Penal. Por la cual se expide el Código Penal | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_0599_2000.html | 2026-09-28 | 605 | Penal |
| `codigo_procedimiento_penal` | Código de Procedimiento Penal. Por la cual se expide el Código de Procedimiento Penal. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_0906_2004.html | 2026-09-28 | 590 | Penal |
| `codigo_procesal_trabajo` | Código Procesal del Trabajo y de la Seguridad Social | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/codigo_procedimental_laboral.html | 2026-09-28 | 164 | Laboral |
| `codigo_sustantivo_trabajo` | Código Sustantivo del Trabajo | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/codigo_sustantivo_trabajo.html | 2026-09-28 | 493 | Laboral |
| `compilacion_csj_contratos_civiles_comerciales_3` | Contratos civiles y comerciales, tomo 3 (Relatoría de la Sala de Casación Civil de la Corte Suprema de Justicia) | Relatoría de la Corte Suprema de Justicia | https://www.cortesuprema.gov.co/corte/wp-content/uploads/relatorias/ci/contratoscivilesycomerciales3.pdf | 2026-10-03 | — (1241 fragm.) | Civil, Comercial y sociedades |
| `constitucion` | Constitución Política de Colombia | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/constitucion_politica_1991.html | 2026-09-28 | 471 | Administrativo, Comercial y sociedades, Constitucional, De familia, Mercados, Laboral, Penal, Procesal, Tributario |
| `cpaca` | Código de Procedimiento Administrativo y de lo Contencioso Administrativo. Por la cual se expide el Código de Procedimiento Administrativo y de lo Contencioso Administrativo. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_1437_2011.html | 2026-09-28 | 320 | Administrativo |
| `decision_345_1993` | Decisión Andina 345 de 1993. Régimen Común de Protección a los derechos de los Obtentores de Variedades Vegetales | Comunidad Andina | https://www.comunidadandina.org/StaticFiles/DocOf/DEC345.pdf | 2026-09-28 | 42 | Mercados |
| `decision_351_1993` | Decisión Andina 351 de 1993. Régimen Común sobre Derecho de Autor y Derechos Conexos | Comunidad Andina | https://www.comunidadandina.org/StaticFiles/DocOf/DEC351.pdf | 2026-09-28 | 61 | Mercados |
| `decision_andina_486` | Decisión 486 de la Comisión de la Comunidad Andina. REGIMEN COMUN SOBRE PROPIEDAD INDUSTRIAL | Comunidad Andina | https://www.comunidadandina.org/StaticFiles/DocOf/DEC486.pdf | 2026-09-28 | 283 | Comercial y sociedades, Mercados |
| `decreto_046_2024` | Decreto 046 de 2024 | Función Pública (Gestor Normativo) | https://www.funcionpublica.gov.co/eva/gestornormativo/norma.php?i=228530 | 2026-09-28 | 2 | Comercial y sociedades |
| `decreto_1072_2015` | Decreto 1072 de 2015. Por medio del cual se expide el Decreto Único Reglamentario del Sector Trabajo | Función Pública (Gestor Normativo) | https://www.funcionpublica.gov.co/eva/gestornormativo/norma.php?i=72173 | 2026-09-28 | 1373 | Laboral |
| `decreto_1074_2015` | Decreto 1074 de 2015 | Función Pública (Gestor Normativo) | https://www.funcionpublica.gov.co/eva/gestornormativo/norma.php?i=76608 | 2026-09-28 | 2068 | Comercial y sociedades, Mercados |
| `decreto_1082_2015` | Decreto 1082 de 2015 | Función Pública (Gestor Normativo) | https://www.funcionpublica.gov.co/eva/gestornormativo/norma.php?i=77653 | 2026-09-28 | 1039 | Administrativo |
| `decreto_1083_2015` | Decreto 1083 de 2015. Por medio del cual se expide el Decreto Único Reglamentario del Sector de Función Pública. | Función Pública (Gestor Normativo) | https://www.funcionpublica.gov.co/eva/gestornormativo/norma.php?i=62866 | 2026-09-28 | 870 | Administrativo |
| `decreto_111_1996` | Decreto 111 de 1996. Por el cual se compilan la Ley 38 de 1989, la Ley 179 de 1994 y la Ley 225 de 1995 que conforman el Estatuto Orgánico del Presupuesto. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/decreto_0111_1996.html | 2026-10-01 | 128 | Administrativo |
| `decreto_1260_1970` | Decreto 1260 de 1970. Por el cual se expide el Estatuto del Registro del Estado Civil de las personas. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/decreto_1260_1970.html | 2026-10-01 | 124 | De familia, Civil |
| `decreto_1295_1994` | Decreto 1295 de 1994. Por el cual se determina la organización y administración del Sistema General de Riesgos Profesionales<1>. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/decreto_1295_1994.html | 2026-09-28 | 98 | Laboral |
| `decreto_1333_1986` | Decreto 1333 de 1986. Por el cual se expide el Código de Régimen Municipal | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/decreto_1333_1986.html | 2026-09-28 | 386 | Tributario |
| `decreto_1377_2013` | Decreto 1377 de 2013. Por el cual se reglamenta parcialmente la Ley 1581 de 2012, Derogado Parcialmente por el Decreto 1081 de 2015. | Función Pública (Gestor Normativo) | https://www.funcionpublica.gov.co/eva/gestornormativo/norma.php?i=53646 | 2026-09-28 | 26 | Mercados |
| `decreto_1382_2000` | Decreto 1382 de 2000. por el cual establecen reglas para el reparto de la acción de tutela | SUIN-Juriscol (vía legalize-co) | https://www.suin-juriscol.gov.co/viewDocument.asp?id=1276834 | 2026-10-03 | 6 | Constitucional |
| `decreto_1469_2025` | Decreto 1469 de 2025. Por el cual se fija el salario mínimo mensual legal | Cancillería (normograma) | https://www.cancilleria.gov.co/normograma/compilacion/docs/decreto_1469_2025.htm | 2026-10-01 | 2 | Laboral, Procesal, Tributario |
| `decreto_1470_2025` | Decreto 1470 de 2025. Por el cual se fija el auxilio de transporte | Cancillería (normograma) | https://www.cancilleria.gov.co/normograma/compilacion/docs/decreto_1470_2025.htm | 2026-10-01 | 2 | Laboral |
| `decreto_1572_2024` | Decreto 1572 de 2024. Por el cual se fija el salario mínimo mensual legal | Función Pública (Gestor Normativo) | https://www.funcionpublica.gov.co/eva/gestornormativo/norma.php?i=257156 | 2026-09-30 | 2 | Laboral, Procesal, Tributario |
| `decreto_159_2026` | Decreto 159 de 2026. Por el cual se fija transitoriamente el salario mínimo mensual legal del año 2026. | Cancillería (normograma) | https://www.cancilleria.gov.co/normograma/compilacion/docs/decreto_0159_2026.htm | 2026-10-01 | 2 | Laboral, Procesal, Tributario |
| `decreto_1625_2016` | Decreto 1625 de 2016 | Función Pública (Gestor Normativo) | https://www.funcionpublica.gov.co/eva/gestornormativo/norma.php?i=83233 | 2026-09-28 | 2118 | Tributario |
| `decreto_1742_2020` | Decreto 1742 de 2020. Por el cual se modifica la estructura de la Unidad Administrativa Especial Dirección de Impuestos y Aduanas Nacionales. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/decreto_1742_2020.html | 2026-09-28 | 83 | Tributario |
| `decreto_175_2025` | Decreto 175 de 2025. Por el cual se adoptan medidas tributarias destinadas a atender los gastos del Presupuesto General de la Nación necesarios para hacer frente al estado de conmoción interior decretado en la región del Catatumbo, el área metropolitana de Cúcuta y los municipios de Río de Oro y González del departamento del Cesar. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/decreto_0175_2025.html | 2026-09-28 | 10 | Tributario |
| `decreto_1833_2016` | Decreto 1833 de 2016. Por medio del cual se compilan las normas del Sistema General de Pensiones | Función Pública (Gestor Normativo) | https://www.funcionpublica.gov.co/eva/gestornormativo/norma.php?i=85319 | 2026-09-30 | 967 | Laboral |
| `decreto_19_2012` | Decreto 19 de 2012. Por el cual se dictan normas para suprimir o reformar regulaciones, procedimientos y trámites innecesarios existentes en la Administración Pública. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/decreto_0019_2012.html | 2026-09-28 | 238 | Administrativo |
| `decreto_2067_1991` | Decreto 2067 de 1991. Por el cual se dicta el régimen procedimental de los juicios y actuaciones que deban surtirse ante la Corte Constitucional. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/decreto_2067_1991.html | 2026-09-28 | 55 | Constitucional |
| `decreto_2153_1992` | Decreto 2153 de 1992. por el cual se reestructura la Superintendencia de Industria y Comercio y se dictan otras disposiciones | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/decreto_2153_1992.html | 2026-09-28 | 59 | Mercados |
| `decreto_24_2016` | Decreto 24 de 2016 | Función Pública (Gestor Normativo) | https://www.funcionpublica.gov.co/eva/gestornormativo/norma.php?i=67536 | 2026-09-28 | 3 | Comercial y sociedades |
| `decreto_2555_2010` | Decreto 2555 de 2010. Por el cual se recogen y reexpiden las normas en materia del sector financiero, asegurador y del mercado de valores y se dictan otras disposiciones. | Función Pública (Gestor Normativo) | https://www.funcionpublica.gov.co/eva/gestornormativo/norma.php?i=40032 | 2026-09-28 | 2600 | Comercial y sociedades |
| `decreto_2591_1991` | Decreto 2591 de 1991. Por el cual se reglamenta la acción de tutela consagrada en el artículo 86 de la Constitución Política. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/decreto_2591_1991.html | 2026-09-28 | 55 | Constitucional |
| `decreto_306_1992` | Decreto 306 de 1992 | Función Pública (Gestor Normativo) | https://www.funcionpublica.gov.co/eva/gestornormativo/norma.php?i=6061 | 2026-09-28 | 8 | Constitucional |
| `decreto_333_2021` | Decreto 333 de 2021 | Función Pública (Gestor Normativo) | https://www.funcionpublica.gov.co/eva/gestornormativo/norma.php?i=161266 | 2026-09-28 | 4 | Constitucional |
| `decreto_405_2025` | Decreto 405 de 2025. Por el cual se adiciona el capítulo 7 al Título 9 de la Parte 2 del Libro 2 del Decreto Único Reglamentario del Sector Trabajo 1072 de 2015 | Función Pública (Gestor Normativo) | https://www.funcionpublica.gov.co/eva/gestornormativo/norma.php?i=259517 | 2026-09-28 | 2 | Laboral |
| `decreto_4302_2008` | Decreto 4302 de 2008. por el cual se fija el procedimiento para la declaratoria de existencia de razones de interés público de acuerdo con lo dispuesto en el artículo 65 de la Decisión 486 de la Comisión de la Comunidad Andina | SUIN-Juriscol (vía legalize-co) | https://www.suin-juriscol.gov.co/viewDocument.asp?id=1544491 | 2026-10-03 | 9 | Mercados |
| `decreto_4334_2008` | Decreto 4334 de 2008. Por el cual se expide un procedimiento de intervención en desarrollo del Decreto 4333 del 17 de noviembre de 2008. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/decreto_4334_2008.html | 2026-09-28 | 16 | Comercial y sociedades |
| `decreto_4436_2005` | Decreto 4436 de 2005. por el cual se reglamenta el artículo 34 de la Ley 962 de 2005, y se señalan los derechos notariales correspondientes. | Función Pública (Gestor Normativo) | https://www.funcionpublica.gov.co/eva/gestornormativo/norma.php?i=18346 | 2026-09-28 | 7 | De familia |
| `decreto_4886_2011` | Decreto 4886 de 2011. Por medio del cual se modifica la estructura de la Superintendencia de Industria y Comercio, se determinan las funciones de sus dependencias y se dictan otras disposiciones. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/decreto_4886_2011.html | 2026-09-28 | 30 | Mercados |
| `decreto_663_1993` | Decreto 663 de 1993 | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/estatuto_organico_sistema_financiero.html | 2026-09-28 | 342 | Comercial y sociedades |
| `decreto_678_2020` | Decreto 678 de 2020. Por medio del cual se establecen medidas para la gestión tributaria, financiera y presupuestal de las entidades territoriales, en el marco de la Emergencia Económica, Social y Ecológica declarada mediante el Decreto 637 de 2020 | Función Pública (Gestor Normativo) | https://www.funcionpublica.gov.co/eva/gestornormativo/norma.php?i=124662 | 2026-10-03 | 10 | Tributario |
| `decreto_780_2016` | Decreto 780 de 2016. Por medio del cual se expide el Decreto Único Reglamentario del Sector Salud y Protección Social | Función Pública (Gestor Normativo) | https://www.funcionpublica.gov.co/eva/gestornormativo/norma.php?i=77813 | 2026-09-28 | 2252 | Penal |
| `decreto_806_2020` | Decreto 806 de 2020. Por el cual se adoptan medidas para implementar las tecnologías de la información y las comunicaciones en las actuaciones judiciales, agilizar los procesos judiciales y flexibilizar la atención a los usuarios del servicio de justicia, en el marco del Estado de Emergencia Económica, Social y Ecológica. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/decreto_0806_2020.html | 2026-09-28 | 16 | Procesal |
| `decreto_875_2008` | Decreto 875 de 2008. Por el cual se modifica el Decreto 841 de 1990. | Cancillería (normograma) | https://www.cancilleria.gov.co/normograma/compilacion/docs/decreto_0875_2008.htm | 2026-09-28 | 2 | Laboral |
| `decreto_960_1970` | Decreto 960 de 1970. Por el cual se expide el Estatuto del Notariado. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/decreto_0960_1970.html | 2026-09-28 | 233 | Civil |
| `estatuto_consumidor` | Estatuto del Consumidor. Por medio de la cual se expide el Estatuto del Consumidor y se dictan otras disposiciones. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_1480_2011.html | 2026-09-28 | 84 | Civil, Mercados |
| `estatuto_tributario` | Estatuto Tributario | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/estatuto_tributario.html | 2026-09-28 | 1299 | Civil, Constitucional, Tributario |
| `ley_100_1993` | Ley 100 de 1993. Por la cual se crea el sistema de seguridad social integral y se dictan otras disposiciones. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_0100_1993.html | 2026-09-28 | 296 | Laboral |
| `ley_1010_2006` | Ley 1010 de 2006. Por medio de la cual se adoptan medidas para prevenir, corregir y sancionar el acoso laboral y otros hostigamientos en el marco de las relaciones de trabajo. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_1010_2006.html | 2026-09-28 | 19 | Laboral |
| `ley_1060_2006` | Ley 1060 de 2006. Por la cual se modifican las normas que regulan la impugnación de la paternidad y la maternidad. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_1060_2006.html | 2026-09-28 | 14 | De familia |
| `ley_1066_2006` | Ley 1066 de 2006. por la cual se dictan normas para la normalización de la cartera pública y se dictan otras disposiciones | SUIN-Juriscol (vía legalize-co) | https://www.suin-juriscol.gov.co/viewDocument.asp?id=1673244 | 2026-10-01 | 21 | Tributario, Administrativo |
| `ley_1095_2006` | Ley 1095 de 2006. Por la cual se reglamenta el artículo 30 de la Constitución Política. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_1095_2006.html | 2026-09-28 | 10 | Constitucional, Penal |
| `ley_1116_2006` | Ley 1116 de 2006. Por la cual se establece el Régimen de Insolvencia Empresarial en la República de Colombia y se dictan otras disposiciones. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_1116_2006.html | 2026-09-28 | 126 | Comercial y sociedades, Procesal |
| `ley_1121_2006` | Ley 1121 de 2006. Por la cual se dictan normas para la prevención, detección, investigación y sanción de la financiación del terrorismo y otras disposiciones. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_1121_2006.html | 2026-09-28 | 28 | Penal |
| `ley_1150_2007` | Ley 1150 de 2007. Por medio de la cual se introducen medidas para la eficiencia y la transparencia en la Ley 80 de 1993 y se dictan otras disposiciones generales sobre la contratación con Recursos Públicos. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_1150_2007.html | 2026-09-28 | 33 | Administrativo |
| `ley_1151_2007` | Ley 1151 de 2007. Por la cual se expide el Plan Nacional de Desarrollo 2006-2010. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_1151_2007.html | 2026-09-28 | 160 | Administrativo |
| `ley_1210_2008` | Ley 1210 de 2008. por la cual se modifican parcialmente los artículos 448 numeral 4 y 451 del Código Sustantivo del Trabajo y 2 del Código Procesal del Trabajo y de la Seguridad Social y se crea el artículo 129A del Código Procesal del Trabajo y de la Seguridad Social y se dictan otras disposiciones | SUIN-Juriscol (vía legalize-co) | https://www.suin-juriscol.gov.co/viewDocument.asp?id=1675597 | 2026-10-03 | 6 | Laboral |
| `ley_1221_2008` | Ley 1221 de 2008. Por la cual se establecen normas para promover y regular el Teletrabajo y se dictan otras disposiciones. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_1221_2008.html | 2026-09-28 | 10 | Laboral |
| `ley_1231_2008` | Ley 1231 de 2008. Por la cual se unifica la factura como título valor como mecanismo de financiación para el micro, pequeño y mediano empresario, y se dictan otras disposiciones. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_1231_2008.html | 2026-09-28 | 10 | Comercial y sociedades |
| `ley_1257_2008` | Ley 1257 de 2008. Por la cual se dictan normas de sensibilización, prevención y sanción de formas de violencia y discriminación contra las mujeres, se reforman los Códigos Penal, de Procedimiento Penal, la Ley 294 de 1996 y se dictan otras disposiciones. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_1257_2008.html | 2026-09-28 | 39 | De familia, Penal |
| `ley_1258_2008` | Ley 1258 de 2008. Por medio de la cual se crea la sociedad por acciones simplificada. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_1258_2008.html | 2026-09-28 | 46 | Comercial y sociedades |
| `ley_1266_2008` | Ley 1266 de 2008. Por la cual se dictan las disposiciones generales del hábeas data y se regula el manejo de la información contenida en bases de datos personales, en especial la financiera, crediticia, comercial, de servicios y la proveniente de terceros países y se dictan otras disposiciones. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_1266_2008.html | 2026-09-28 | 24 | Mercados |
| `ley_1273_2009` | Ley 1273 de 2009. Por medio de la cual se modifica el Código Penal, se crea un nuevo bien jurídico tutelado - denominado “de la protección de la información y de los datos”- y se preservan integralmente los sistemas que utilicen las tecnologías de la información y las comunicaciones, entre otras disposiciones. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_1273_2009.html | 2026-09-28 | 4 | Penal |
| `ley_1285_2009` | Ley 1285 de 2009. Por medio de la cual se reforma la Ley 270 de 1996 Estatutaria de la Administración de Justicia. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_1285_2009.html | 2026-09-28 | 27 | Procesal |
| `ley_1328_2009` | Ley 1328 de 2009. Por la cual se dictan normas en materia financiera, de seguros, del mercado de valores y otras disposiciones. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_1328_2009.html | 2026-09-28 | 103 | Comercial y sociedades, Mercados |
| `ley_1340_2009` | Ley 1340 de 2009. Por medio de la cual se dictan normas en materia de protección de la competencia. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_1340_2009.html | 2026-09-28 | 34 | Mercados |
| `ley_134_1994` | Ley 134 de 1994. por la cual se dictan normas sobre mecanismos de participación ciudadana. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_0134_1994.html | 2026-09-28 | 109 | Constitucional |
| `ley_1361_2009` | Ley 1361 de 2009. Por medio de la cual se crea la Ley de Protección Integral a la Familia. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_1361_2009.html | 2026-09-30 | 17 | De familia |
| `ley_136_1994` | Ley 136 de 1994. Por la cual se dictan normas tendientes a modernizar la organización y el funcionamiento de los municipios. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_0136_1994.html | 2026-09-28 | 203 | Administrativo |
| `ley_137_1994` | Ley 137 de 1994. Por la cual se reglamentan los Estados de Excepción en Colombia | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_0137_1994.html | 2026-09-28 | 59 | Tributario |
| `ley_1429_2010` | Ley 1429 de 2010. Por la cual se expide la Ley de Formalización y Generación de Empleo. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_1429_2010.html | 2026-09-28 | 65 | Comercial y sociedades |
| `ley_142_1994` | Ley 142 de 1994. por la cual se establece el régimen de los servicios públicos domiciliarios y se dictan otras disposiciones. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_0142_1994.html | 2026-10-01 | 189 | Administrativo |
| `ley_1448_2011` | Ley 1448 de 2011. por la cual se dictan medidas de atención, asistencia y reparación integral a las víctimas del conflicto armado interno y se dictan otras disposiciones | SUIN-Juriscol (vía legalize-co) | https://www.suin-juriscol.gov.co/viewDocument.asp?id=1680697 | 2026-10-01 | 217 | Constitucional |
| `ley_1453_2011` | Ley 1453 de 2011. Por medio de la cual se reforma el Código Penal, el Código de Procedimiento Penal, el Código de Infancia y Adolescencia, las reglas sobre extinción de dominio y se dictan otras disposiciones en materia de seguridad. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_1453_2011.html | 2026-09-28 | 111 | Penal |
| `ley_1473_2011` | Ley 1473 de 2011. Por medio de la cual se establece una regla fiscal y se dictan otras disposiciones. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_1473_2011.html | 2026-09-28 | 17 | Tributario |
| `ley_1474_2011` | Ley 1474 de 2011. Por la cual se dictan normas orientadas a fortalecer los mecanismos de prevención, investigación y sanción de actos de corrupción y la efectividad del control de la gestión pública. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_1474_2011.html | 2026-09-28 | 142 | Administrativo |
| `ley_14_1983` | Ley 14 de 1983 | Función Pública (Gestor Normativo) | https://www.funcionpublica.gov.co/eva/gestornormativo/norma.php?i=267 | 2026-09-28 | 89 | Tributario |
| `ley_1508_2012` | Ley 1508 de 2012. por la cual se establece el régimen jurídico de las Asociaciones Público Privadas, se dictan normas orgánicas de presupuesto y se dictan otras disposiciones | SUIN-Juriscol (vía legalize-co) | https://www.suin-juriscol.gov.co/viewDocument.asp?id=1682473 | 2026-10-01 | 39 | Administrativo |
| `ley_152_1994` | Ley 152 de 1994. por la cual se establece la Ley Orgánica del Plan de Desarrollo | SUIN-Juriscol (vía legalize-co) | https://www.suin-juriscol.gov.co/viewDocument.asp?id=1651907 | 2026-10-01 | 52 | Administrativo |
| `ley_153_1887` | Ley 153 de 1887. Por la cual se adiciona y reforma los códigos nacionales, la ley 61 de 1886 y la 57 de 1887. | Función Pública (Gestor Normativo) | https://www.funcionpublica.gov.co/eva/gestornormativo/norma.php?i=15805 | 2026-09-28 | 329 | Civil, Tributario |
| `ley_1551_2012` | Ley 1551 de 2012. Por la cual se dictan normas para modernizar la organización y el funcionamiento de los municipios. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_1551_2012.html | 2026-09-28 | 50 | Administrativo |
| `ley_155_1959` | Ley 155 de 1959 | Función Pública (Gestor Normativo) | https://www.funcionpublica.gov.co/eva/gestornormativo/norma.php?i=38169 | 2026-09-28 | 19 | Mercados |
| `ley_1561_2012` | Ley 1561 de 2012. Por la cual se establece un proceso verbal especial para otorgar títulos de propiedad al poseedor material de bienes inmuebles urbanos y rurales de pequeña entidad económica, sanear la falsa tradición y se dictan otras disposiciones. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_1561_2012.html | 2026-09-28 | 27 | Civil |
| `ley_1562_2012` | Ley 1562 de 2012. Por la cual se modifica el Sistema de Riesgos Laborales y se dictan otras disposiciones en materia de Salud Ocupacional. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_1562_2012.html | 2026-09-28 | 33 | Laboral |
| `ley_1563_2012` | Ley 1563 de 2012. Por medio de la cual se expide el Estatuto de Arbitraje Nacional e Internacional y se dictan otras disposiciones. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_1563_2012.html | 2026-09-28 | 119 | Procesal |
| `ley_1579_2012` | Ley 1579 de 2012. Por la cual se expide el estatuto de registro de instrumentos públicos y se dictan otras disposiciones. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_1579_2012.html | 2026-09-28 | 104 | Civil |
| `ley_1581_2012` | Ley 1581 de 2012. Por la cual se dictan disposiciones generales para la protección de datos personales. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_1581_2012.html | 2026-09-28 | 30 | Administrativo, Constitucional, Mercados |
| `ley_1607_2012` | Ley 1607 de 2012. Por la cual se expiden normas en materia tributaria y se dictan otras disposiciones. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_1607_2012.html | 2026-09-28 | 217 | Tributario |
| `ley_160_1994` | Ley 160 de 1994. Por la cual se crea el Sistema Nacional de Reforma Agraria y Desarrollo Rural Campesino, se establece un subsidio para la adquisición de tierras, se reforma el Instituto Colombiano de la Reforma Agraria<1> y se dictan otras disposiciones. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_0160_1994.html | 2026-09-28 | 115 | Civil |
| `ley_1618_2013` | Ley 1618 de 2013. por medio de la cual se establecen las disposiciones para garantizar el pleno ejercicio de los derechos de las personas con discapacidad | SUIN-Juriscol (vía legalize-co) | https://www.suin-juriscol.gov.co/viewDocument.asp?id=1685302 | 2026-10-01 | 32 | Constitucional |
| `ley_1676_2013` | Ley 1676 de 2013. Por la cual se promueve el acceso al crédito y se dictan normas sobre garantías mobiliarias. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_1676_2013.html | 2026-09-28 | 91 | Civil, Comercial y sociedades |
| `ley_1692_2013` | Ley 1692 de 2013. Por medio de la cual se aprueba el “Convenio entre la República Portuguesa y la República de Colombia para evitar la doble imposición y para prevenir la evasión fiscal en relación con el Impuesto sobre la Renta” y su “Protocolo”, suscritos en Bogotá, D.C., República de Colombia, el 30 de agosto de 2010 y el canje de notas entre la República Portuguesa y la República de Colombia por medio de la cual se corrigen imprecisiones en la traducción en las versiones en español, inglés y portugués del “convenio entre la República Portuguesa y la República de Colombia para evitar la doble imposición y para prevenir la evasión fiscal en relación con el Impuesto sobre la Renta”. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_1692_2013.html | 2026-09-28 | 36 | Tributario |
| `ley_1700_2013` | Ley 1700 de 2013. Por medio de la cual se reglamentan las actividades de comercialización en red o mercadeo multinivel en Colombia. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_1700_2013.html | 2026-09-28 | 13 | Comercial y sociedades |
| `ley_1708_2014` | Ley 1708 de 2014. Por medio de la cual se expide el Código de Extinción de Dominio. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_1708_2014.html | 2026-10-01 | 225 | Penal |
| `ley_1709_2014` | Ley 1709 de 2014. Por medio de la cual se reforman algunos artículos de la Ley 65 de 1993, de la Ley 599 de 2000, de la Ley 55 de 1985 y se dictan otras disposiciones. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_1709_2014.html | 2026-09-28 | 107 | Penal |
| `ley_1712_2014` | Ley 1712 de 2014. Por medio de la cual se crea la Ley de Transparencia y del Derecho de Acceso a la Información Pública Nacional y se dictan otras disposiciones. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_1712_2014.html | 2026-09-28 | 35 | Constitucional |
| `ley_1739_2014` | Ley 1739 de 2014. Por medio de la cual se modifica el Estatuto Tributario, la Ley 1607 de 2012, se crean mecanismos de lucha contra la evasión y se dictan otras disposiciones. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_1739_2014.html | 2026-09-28 | 77 | Tributario |
| `ley_1751_2015` | Ley 1751 de 2015. Por medio de la cual se regula el derecho fundamental a la salud y se dictan otras disposiciones. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_1751_2015.html | 2026-09-28 | 26 | Constitucional |
| `ley_1755_2015` | Ley 1755 de 2015. Por medio de la cual se regula el Derecho Fundamental de Petición y se sustituye un título del Código de Procedimiento Administrativo y de lo Contencioso Administrativo. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_1755_2015.html | 2026-09-28 | 2 | Administrativo |
| `ley_1757_2015` | Ley 1757 de 2015. Por la cual se dictan disposiciones en materia de promoción y protección del derecho a la participación democrática. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_1757_2015.html | 2026-09-28 | 113 | Constitucional |
| `ley_1761_2015` | Ley 1761 de 2015. Por la cual se crea el tipo penal de feminicidio como delito autónomo y se dictan otras disposiciones.(Rosa Elvira Cely) | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_1761_2015.html | 2026-09-28 | 13 | Penal |
| `ley_1774_2016` | Ley 1774 de 2016. Por medio de la cual se modifican el Código Civil, la Ley 84 de 1989, el Código Penal, el Código de Procedimiento Penal y se dictan otras disposiciones. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_1774_2016.html | 2026-10-01 | 11 | Civil, Penal |
| `ley_1819_2016` | Ley 1819 de 2016. Por medio de la cual se adopta una reforma tributaria estructural, se fortalecen los mecanismos para la lucha contra la evasión y la elusión fiscal, y se dictan otras disposiciones. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_1819_2016.html | 2026-09-28 | 376 | Tributario |
| `ley_1822_2017` | Ley 1822 de 2017. Por medio de la cual se incentiva la adecuada atención y cuidado de la primera infancia, se modifican los artículos 236 y 239 del Código Sustantivo del Trabajo y se dictan otras disposiciones. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_1822_2017.html | 2026-09-28 | 3 | Laboral |
| `ley_1826_2017` | Ley 1826 de 2017. Por medio de la cual se establece un procedimiento penal especial abreviado y se regula la figura del acusador privado. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_1826_2017.html | 2026-09-28 | 44 | Penal |
| `ley_1878_2018` | Ley 1878 de 2018. Por medio de la cual se modifican algunos artículos de la Ley 1098 de 2006, por la cual se expide el Código de la Infancia y la Adolescencia, y se dictan otras disposiciones. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_1878_2018.html | 2026-09-28 | 13 | De familia |
| `ley_1882_2018` | Ley 1882 de 2018. Por la cual se adicionan, modifican y dictan disposiciones orientadas a fortalecer la Contratación Pública en Colombia, la ley de infraestructura y se dictan otras disposiciones. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_1882_2018.html | 2026-09-28 | 21 | Administrativo |
| `ley_1909_2018` | Ley 1909 de 2018. Por medio de la cual se adoptan el Estatuto de la Oposición Política y algunos derechos a las organizaciones políticas independientes. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_1909_2018.html | 2026-09-28 | 32 | Constitucional |
| `ley_1915_2018` | Ley 1915 de 2018. Por la cual se modifica la Ley 23 de 1982 y se establecen otras disposiciones en materia de derecho de autor y derechos conexos. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_1915_2018.html | 2026-09-28 | 36 | Mercados |
| `ley_1934_2018` | Ley 1934 de 2018. Por medio de la cual se reforma y adiciona el Código Civil. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_1934_2018.html | 2026-10-03 | 22 | De familia |
| `ley_1943_2018` | Ley 1943 de 2018. Por la cual se expiden normas de financiamiento para el restablecimiento del equilibrio del presupuesto general y se dictan otras disposiciones. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_1943_2018.html | 2026-09-28 | 122 | Tributario |
| `ley_1996_2019` | Ley 1996 de 2019. Por medio de la cual se establece el régimen para el ejercicio de la capacidad legal de las personas con discapacidad mayores de edad. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_1996_2019.html | 2026-09-28 | 63 | Civil, De familia |
| `ley_2010_2019` | Ley 2010 de 2019. Por medio de la cual se adoptan normas para la promoción del crecimiento económico, el empleo, la inversión, el fortalecimiento de las finanzas públicas y la progresividad, equidad y eficiencia del sistema tributario, de acuerdo con los objetivos que sobre la materia impulsaron la Ley 1943 de 2018 y se dictan otras disposiciones. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_2010_2019.html | 2026-09-28 | 157 | Tributario |
| `ley_2069_2020` | Ley 2069 de 2020. Por medio de la cual se impulsa el emprendimiento en Colombia. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_2069_2020.html | 2026-09-28 | 85 | Comercial y sociedades |
| `ley_2080_2021` | Ley 2080 de 2021. Por medio de la cual se Reforma el Código de Procedimiento Administrativo y de lo Contencioso Administrativo –Ley 1437 de 2011– y se dictan otras disposiciones en materia de descongestión en los procesos que se tramitan ante la jurisdicción. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_2080_2021.html | 2026-09-30 | 87 | Administrativo, Procesal |
| `ley_2088_2021` | Ley 2088 de 2021. Por la cual se regula el trabajo en casa y se dictan otras disposiciones. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_2088_2021.html | 2026-09-28 | 16 | Laboral |
| `ley_2097_2021` | Ley 2097 de 2021. Por medio de la cual se crea el Registro de Deudores Alimentarios Morosos (Redam) y se dictan otras disposiciones. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_2097_2021.html | 2026-09-28 | 11 | De familia |
| `ley_2098_2021` | Ley 2098 de 2021. Por medio de la cual se reforma el Código Penal (Ley 599 de 2000), el Código de Procedimiento Penal (Ley 906 de 2004), el Código Penitenciario y Carcelario (Ley 65 de 1993) y se dictan otras disposiciones, Ley Gilma Jiménez. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_2098_2021.html | 2026-09-28 | 28 | Penal |
| `ley_2101_2021` | Ley 2101 de 2021. Por medio de la cual se reduce la jornada laboral semanal de manera gradual, sin disminuir el salario de los trabajadores y se dictan otras disposiciones. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_2101_2021.html | 2026-09-28 | 8 | Laboral |
| `ley_2114_2021` | Ley 2114 de 2021. Por medio de la cual se amplía la licencia de paternidad, se crea la licencia parental compartida, la licencia parental flexible de tiempo parcial, se modifica el artículo 236 y se adiciona el artículo 241A del Código Sustantivo del Trabajo, y se dictan otras disposiciones | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_2114_2021.html | 2026-09-28 | 6 | Laboral |
| `ley_2121_2021` | Ley 2121 de 2021. Por medio de la cual se crea el régimen de trabajo remoto y se establecen normas para promoverlo, regularlo y se dictan otras disposiciones. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_2121_2021.html | 2026-09-28 | 27 | Laboral |
| `ley_2126_2021` | Ley 2126 de 2021. Por la cual se regula la creación, conformación y funcionamiento de las Comisarías de Familia, se establece el órgano rector y se dictan otras disposiciones. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_2126_2021.html | 2026-09-28 | 48 | De familia |
| `ley_2141_2021` | Ley 2141 de 2021. Por medio de la cual se modifican los artículos 239 y 240 del CST, con el fin de establecer el fuero de paternidad. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_2141_2021.html | 2026-09-28 | 3 | Constitucional, Laboral |
| `ley_2155_2021` | Ley 2155 de 2021. Por medio de la cual se expide la Ley de Inversión Social y se dictan otras disposiciones. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_2155_2021.html | 2026-09-28 | 65 | Tributario |
| `ley_2157_2021` | Ley 2157 de 2021. Por medio de la cual se modifica y adiciona la Ley Estatutaria 1266 de 2008, y se dictan disposiciones generales del Hábeas Data con relación a la información financiera, crediticia, comercial, de servicios y la proveniente de terceros países y se dictan otras disposiciones. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_2157_2021.html | 2026-09-28 | 15 | Mercados |
| `ley_2160_2021` | Ley 2160 de 2021. Por medio de la cual se modifica la Ley 80 de 1993 y la Ley 1150 de 2007. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_2160_2021.html | 2026-09-28 | 5 | Administrativo |
| `ley_2191_2022` | Ley 2191 de 2022. Por medio de la cual se Regula la desconexión laboral - Ley de Desconexión Laboral. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_2191_2022.html | 2026-09-30 | 8 | Laboral |
| `ley_2195_2022` | Ley 2195 de 2022. Por medio de la cual se adoptan medidas en materia de transparencia, prevención y lucha contra la corrupción y se dictan otras disposiciones. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_2195_2022.html | 2026-09-28 | 69 | Administrativo |
| `ley_2197_2022` | Ley 2197 de 2022. Por medio de la cual se dictan normas tendientes al fortalecimiento de la seguridad ciudadana y se dictan otras disposiciones. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_2197_2022.html | 2026-09-28 | 69 | Penal |
| `ley_2213_2022` | Ley 2213 de 2022. Por medio de la cual se establece la vigencia permanente del Decreto Legislativo 806 de 2020 y se adoptan medidas para implementar las tecnologías de la información y las comunicaciones en las actuaciones judiciales, agilizar los procesos judiciales y flexibilizar la atención a los usuarios del servicio de justicia y se dictan otras disposiciones. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_2213_2022.html | 2026-09-28 | 15 | Procesal |
| `ley_2220_2022` | Ley 2220 de 2022. Por medio de la cual se expide el estatuto de conciliación y se dictan otras disposiciones. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_2220_2022.html | 2026-09-28 | 146 | Civil, Procesal |
| `ley_222_1995` | Ley 222 de 1995. Por la cual se modifica el Libro II del Código de Comercio, se expide un nuevo régimen de procesos concursales y se dictan otras disposiciones. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_0222_1995.html | 2026-09-28 | 242 | Comercial y sociedades |
| `ley_2251_2022` | Ley 2251 de 2022. Por la cual se dictan normas para el diseño e implementación de la política de seguridad vial con enfoque de sistema seguro y se dictan otras disposiciones Ley Julián Esteban. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_2251_2022.html | 2026-09-28 | 24 | Civil |
| `ley_2274_2022` | Ley 2274 de 2022. Por medio de la cual se aprueba el “Convenio Marco de Cooperación entre la República de Colombia y el Reino de España”, suscrito en Madrid, Reino de España, el 3 de marzo de 2015 | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_2274_2022.html | 2026-10-03 | 26 | Constitucional |
| `ley_2277_2022` | Ley 2277 de 2022. Por medio de la cual se adopta una reforma tributaria para la igualdad y la justicia social y se dictan otras disposiciones. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_2277_2022.html | 2026-09-28 | 96 | Tributario |
| `ley_2294_2023` | Ley 2294 de 2023. Por el cual se expide el Plan Nacional de Desarrollo 2022-2026 "Colombia Potencia Mundial de la Vida". | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_2294_2023.html | 2026-10-01 | 372 | Administrativo |
| `ley_2300_2023` | Ley 2300 de 2023. Por medio de la cual se establecen medidas que protejan el derecho a la intimidad de los consumidores. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_2300_2023.html | 2026-10-01 | 10 | Mercados |
| `ley_2381_2024` | Ley 2381 de 2024. Por medio de la cual se establece el Sistema de Protección Social Integral para la Vejez, Invalidez y Muerte de origen común, y se dictan otras disposiciones. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_2381_2024.html | 2026-09-28 | 94 | Laboral |
| `ley_23_1982` | Ley 23 de 1982 | Función Pública (Gestor Normativo) | https://www.funcionpublica.gov.co/eva/gestornormativo/norma.php?i=3431 | 2026-09-28 | 263 | Mercados |
| `ley_2437_2024` | Ley 2437 de 2024. Por medio del cual se establece la legislación permanente de los Decretos Legislativos 560 y 772 de 2020, Decretos reglamentarios 842 y 1332 de 2020 en materia de insolvencia empresarial y se dictan otras disposiciones | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_2437_2024.html | 2026-09-28 | 21 | Civil, Procesal |
| `ley_2452_2025` | Ley 2452 de 2025. Por la cual se expide el Código Procesal del Trabajo y de la Seguridad Social. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_2452_2025.html | 2026-09-28 | 331 | Laboral |
| `ley_2466_2025` | Ley 2466 de 2025. Por medio de la cual se modifica parcialmente normas laborales y se adopta una Reforma Laboral para el trabajo decente y digno en Colombia. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_2466_2025.html | 2026-09-28 | 70 | Laboral |
| `ley_256_1996` | Ley 256 de 1996. Por la cual se dictan normas sobre competencia desleal. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_0256_1996.html | 2026-09-28 | 33 | Mercados |
| `ley_258_1996` | Ley 258 de 1996. Por la cual se establece la afectación a vivienda familiar y se dictan otras disposiciones. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_0258_1996.html | 2026-09-28 | 13 | Civil, De familia |
| `ley_25_1992` | Ley 25 de 1992. Por la cual se desarrollan los incisos 9, 10, 11, 12 y 13 del artículo 42 de la Constitución Política. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_0025_1992.html | 2026-09-28 | 15 | De familia |
| `ley_270_1996` | Ley 270 de 1996 | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_0270_1996.html | 2026-09-28 | 233 | Constitucional, Procesal |
| `ley_294_1996` | Ley 294 de 1996. Por la cual se desarrolla el artículo 42 de la Constitución Política y se dictan normas para prevenir, remediar y sancionar la violencia intrafamiliar. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_0294_1996.html | 2026-09-28 | 30 | De familia |
| `ley_29_1982` | Ley 29 de 1982 | Función Pública (Gestor Normativo) | https://www.funcionpublica.gov.co/eva/gestornormativo/norma.php?i=256 | 2026-09-28 | 10 | De familia |
| `ley_361_1997` | Ley 361 de 1997. Por la cual se establecen mecanismos de integración social de las personas <en situación de discapacidad> y se dictan otras disposiciones. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_0361_1997.html | 2026-09-28 | 73 | Laboral |
| `ley_388_1997` | Ley 388 de 1997. Por la cual se modifica la Ley 9ª de 1989, y la Ley 3ª de 1991 y se dictan otras disposiciones. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_0388_1997.html | 2026-10-01 | 139 | Administrativo |
| `ley_393_1997` | Ley 393 de 1997. Por la cual se desarrolla el artículo 87 de la Constitución Política. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_0393_1997.html | 2026-09-28 | 32 | Constitucional |
| `ley_42_1993` | Ley 42 de 1993 | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_0042_1993.html | 2026-09-28 | 110 | Administrativo |
| `ley_44_1993` | Ley 44 de 1993. Por la cual se modifica y adiciona la Ley 23 de 1982 y se modifica la Ley 29 de 1944 | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_0044_1993.html | 2026-09-28 | 70 | Mercados |
| `ley_45_1990` | Ley 45 de 1990. Por la cual se expiden normas en materia de intermediación financiera, se regula la actividad aseguradora, se conceden unas facultades y se dictan otras disposiciones | SUIN-Juriscol (vía legalize-co) | https://www.suin-juriscol.gov.co/viewDocument.asp?id=1600083 | 2026-10-03 | 99 | Comercial y sociedades |
| `ley_472_1998` | Ley 472 de 1998. Por la cual se desarrolla el artículo 88 de la Constitución Política de Colombia en relación con el ejercicio de las acciones populares y de grupo y se dictan otras disposiciones. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_0472_1998.html | 2026-09-28 | 87 | Administrativo, Constitucional |
| `ley_489_1998` | Ley 489 de 1998. Por la cual se dictan normas sobre la organización y funcionamiento de las entidades del orden nacional, se expiden las disposiciones, principios y reglas generales para el ejercicio de las atribuciones previstas en los numerales 15 y 16 del artículo 189 de la Constitución Política y se dictan otras disposiciones. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_0489_1998.html | 2026-09-28 | 121 | Administrativo |
| `ley_50_1990` | Ley 50 de 1990 | Función Pública (Gestor Normativo) | https://www.funcionpublica.gov.co/eva/gestornormativo/norma.php?i=281 | 2026-09-28 | 116 | Laboral |
| `ley_527_1999` | Ley 527 de 1999. Por medio de la cual se define y reglamenta el acceso y uso de los mensajes de datos, del comercio electrónico y de las firmas digitales, y se establecen las entidades de certificación y se dictan otras disposiciones. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_0527_1999.html | 2026-09-28 | 47 | Comercial y sociedades |
| `ley_54_1990` | Ley 54 de 1990. por la cual se definen las uniones maritales de hecho y régimen patrimonial entre compañeros permanentes. | Función Pública (Gestor Normativo) | https://www.funcionpublica.gov.co/eva/gestornormativo/norma.php?i=30896 | 2026-09-28 | 9 | De familia |
| `ley_5_1992` | Ley 5 de 1992. Por la cual se expide el Reglamento del Congreso; el Senado y la Cámara de Representantes. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_0005_1992.html | 2026-09-28 | 422 | Constitucional |
| `ley_600_2000` | Ley 600 de 2000. Por la cual se expide el Código de Procedimiento Penal. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_0600_2000.html | 2026-09-28 | 558 | Penal |
| `ley_610_2000` | Ley 610 de 2000. Por la cual se establece el trámite de los procesos de responsabilidad fiscal de competencia de las contralorías. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_0610_2000.html | 2026-09-28 | 68 | Administrativo |
| `ley_617_2000` | Ley 617 de 2000. Por la cual se reforma parcialmente la Ley 136 de 1994, el Decreto Extraordinario 1222 de 1986, se adiciona la Ley Orgánica de Presupuesto, el Decreto 1421 de 1993, se dictan otras normas tendientes a fortalecer la descentralización, y se dictan normas para la racionalización del gasto público nacional | SUIN-Juriscol (vía legalize-co) | https://www.suin-juriscol.gov.co/viewDocument.asp?id=1664753 | 2026-10-01 | 96 | Administrativo |
| `ley_640_2001` | Ley 640 de 2001. Por la cual se modifican normas relativas a la conciliación y se dictan otras disposiciones. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_0640_2001.html | 2026-09-28 | 50 | Mercados |
| `ley_65_1993` | Ley 65 de 1993. Por la cual se expide el Código Penitenciario y Carcelario. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_0065_1993.html | 2026-09-28 | 198 | Penal |
| `ley_675_2001` | Ley 675 de 2001. Por medio de la cual se expide el régimen de propiedad horizontal. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_0675_2001.html | 2026-09-28 | 87 | Civil |
| `ley_678_2001` | Ley 678 de 2001. Por medio de la cual se reglamenta la determinación de responsabilidad patrimonial de los agentes del Estado a través del ejercicio de la acción de repetición o de llamamiento en garantía con fines de repetición. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_0678_2001.html | 2026-09-28 | 32 | Procesal |
| `ley_721_2001` | Ley 721 de 2001. Por medio de la cual se modifica la Ley 75 de 1968. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_0721_2001.html | 2026-09-28 | 13 | De familia |
| `ley_75_1968` | Ley 75 de 1968 | Función Pública (Gestor Normativo) | https://www.funcionpublica.gov.co/eva/gestornormativo/norma.php?i=4828 | 2026-09-28 | 67 | De familia |
| `ley_769_2002` | Ley 769 de 2002. Por la cual se expide el Código Nacional de Tránsito Terrestre y se dictan otras disposiciones. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_0769_2002.html | 2026-09-28 | 180 | Civil |
| `ley_776_2002` | Ley 776 de 2002. Por la cual se dictan normas sobre la organización, administración y prestaciones del Sistema General de Riesgos Profesionales. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_0776_2002.html | 2026-09-28 | 23 | Laboral |
| `ley_788_2002` | Ley 788 de 2002. por la cual se expiden normas en materia tributaria y penal del orden nacional y territorial; y se dictan otras disposiciones | SUIN-Juriscol (vía legalize-co) | https://www.suin-juriscol.gov.co/viewDocument.asp?id=1668340 | 2026-10-01 | 118 | Tributario |
| `ley_789_2002` | Ley 789 de 2002. Por la cual se dictan normas para apoyar el empleo y ampliar la protección social y se modifican algunos artículos del Código Sustantivo de Trabajo. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_0789_2002.html | 2026-09-28 | 52 | Laboral |
| `ley_791_2002` | Ley 791 de 2002. Por medio de la cual se reducen los términos de prescripción en materia civil. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_0791_2002.html | 2026-09-28 | 13 | Civil |
| `ley_79_1988` | Ley 79 de 1988. Por la cual se actualiza la legislación cooperativa | SUIN-Juriscol (vía legalize-co) | https://www.suin-juriscol.gov.co/viewDocument.asp?id=1625669 | 2026-10-01 | 161 | Laboral, Comercial y sociedades |
| `ley_80_1993` | Ley 80 de 1993. Por la cual se expide el Estatuto General de Contratación de la Administración Pública | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_0080_1993.html | 2026-09-28 | 84 | Administrativo, Laboral |
| `ley_820_2003` | Ley 820 de 2003. Por la cual se expide el régimen de arrendamiento de vivienda urbana y se dictan otras disposiciones. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_0820_2003.html | 2026-09-28 | 43 | Comercial y sociedades |
| `ley_909_2004` | Ley 909 de 2004. Por la cual se expiden normas que regulan el empleo público, la carrera administrativa, gerencia pública y se dictan otras disposiciones. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_0909_2004.html | 2026-09-28 | 59 | Administrativo |
| `ley_964_2005` | Ley 964 de 2005. Por la cual se dictan normas generales y se señalan en ellas los objetivos y criterios a los cuales debe sujetarse el Gobierno Nacional para regular las actividades de manejo, aprovechamiento e inversión de recursos captados del público que se efectúen mediante valores y se dictan otras disposiciones. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_0964_2005.html | 2026-09-30 | 86 | Mercados, Comercial y sociedades |
| `ley_979_2005` | Ley 979 de 2005. Por medio de la cual se modifica parcialmente la Ley 54 de 1990 y se establecen unos mecanismos ágiles para demostrar la unión marital de hecho y sus efectos patrimoniales entre compañeros permanentes. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_0979_2005.html | 2026-09-28 | 5 | De familia |
| `ley_99_1993` | Ley 99 de 1993. Por la cual se crea el Ministerio del Medio Ambiente, se reordena el Sector Público encargado de la gestión y conservación del medio ambiente y los recursos naturales renovables, se organiza el Sistema Nacional Ambiental, SINA y se dictan otras disposiciones. | Secretaría del Senado | http://www.secretariasenado.gov.co/senado/basedoc/ley_0099_1993.html | 2026-10-03 | 120 | Administrativo |
| `resolucion_238_2025` | Resolución 238 de 2025. Por medio de la cual, en desarrollo del artículo 868 del Estatuto Tributario, se sustituye el artículo 1.2.1 del Título 2 de la Parte 1 de la Resolución Única en Materia Tributaria, Aduanera y Cambiaria de la Dirección de Impuestos y Aduanas Nacionales (DIAN), Resolución número 000227 de 2025, para fijar el valor de la Unidad de Valor Tributario (UVT) aplicable para el año 2026. | DIAN (normograma) | https://normograma.dian.gov.co/dian/compilacion/docs/resolucion_dian_0238_2025.htm | 2026-10-01 | 3 | Tributario |
| `resolucion_368_2014` | Resolución 368 de 2014 | Ministerio de Ambiente y Desarrollo Sostenible | https://www.minambiente.gov.co/documento-normativa/resolucion-0368-de-2014/ | 2026-10-03 | — (45 fragm.) | Administrativo |
| `sentencia_c_1011_2008` | Sentencia C-1011 de 2008 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2008/C-1011-08.htm | 2026-09-28 | — (647 fragm.) | Mercados |
| `sentencia_c_1033_2002` | Sentencia C-1033 de 2002 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2002/C-1033-02.htm | 2026-09-28 | — (39 fragm.) | De familia |
| `sentencia_c_106_2018` | Sentencia C-106 de 2018 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2018/C-106-18.htm | 2026-09-28 | — (107 fragm.) | Constitucional |
| `sentencia_c_1141_2000` | Sentencia C-1141 de 2000 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2000/c-1141-00.htm | 2026-09-28 | — (58 fragm.) | Mercados |
| `sentencia_c_117_2018` | Sentencia C-117 de 2018 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2018/C-117-18.htm | 2026-09-28 | — (147 fragm.) | Tributario |
| `sentencia_c_1189_2000` | Sentencia C-1189 de 2000 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2000/C-1189-00.htm | 2026-09-28 | — (88 fragm.) | Penal |
| `sentencia_c_127_2011` | Sentencia C-127 de 2011 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2011/C-127-11.htm | 2026-09-28 | — (62 fragm.) | Constitucional |
| `sentencia_c_131_2018` | Sentencia C-131 de 2018 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2018/C-131-18.htm | 2026-09-28 | — (66 fragm.) | De familia |
| `sentencia_c_134_2019` | Sentencia C-134 de 2019 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2019/C-134-19.htm | 2026-09-28 | — (43 fragm.) | Constitucional, De familia |
| `sentencia_c_141_2010` | Sentencia C-141 de 2010 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2010/C-141-10.htm | 2026-09-28 | — (987 fragm.) | Constitucional |
| `sentencia_c_145_2018` | Sentencia C-145 de 2018 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2018/C-145-18.htm | 2026-09-28 | — (88 fragm.) | Comercial y sociedades |
| `sentencia_c_145_2020` | Sentencia C-145 de 2020 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2020/C-145-20.htm | 2026-09-28 | — (277 fragm.) | Constitucional |
| `sentencia_c_149_1993` | Sentencia C-149 de 1993 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/1993/C-149-93.htm | 2026-09-28 | — (36 fragm.) | Constitucional |
| `sentencia_c_15_2018` | Sentencia C-15 de 2018 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2018/C-015-18.htm | 2026-09-28 | — (103 fragm.) | Constitucional, Penal |
| `sentencia_c_164_2022` | Sentencia C-164 de 2022 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2022/C-164-22.htm | 2026-09-28 | — (153 fragm.) | Constitucional, Penal |
| `sentencia_c_170_2004` | Sentencia C-170 de 2004 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2004/C-170-04.htm | 2026-09-28 | — (101 fragm.) | Laboral |
| `sentencia_c_183_2025` | Sentencia C-183 de 2025 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2025/C-183-25.htm | 2026-09-28 | — (149 fragm.) | Civil |
| `sentencia_c_201_2002` | Sentencia C-201 de 2002 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2002/C-201-02.htm | 2026-09-28 | — (93 fragm.) | Laboral |
| `sentencia_c_207_2019` | Sentencia C-207 de 2019 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2019/C-207-19.htm | 2026-09-28 | — (273 fragm.) | Administrativo |
| `sentencia_c_221_1994` | Sentencia C-221 de 1994 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/1994/C-221-94.htm | 2026-09-28 | — (47 fragm.) | Penal |
| `sentencia_c_225_1995` | Sentencia C-225 de 1995 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/1995/C-225-95.htm | 2026-09-28 | — (93 fragm.) | Constitucional |
| `sentencia_c_22_1996` | Sentencia C-22 de 1996 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/1996/C-022-96.htm | 2026-09-28 | — (26 fragm.) | Constitucional |
| `sentencia_c_233_2021` | Sentencia C-233 de 2021 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2021/C-233-21.htm | 2026-09-28 | — (373 fragm.) | Constitucional |
| `sentencia_c_239_1997` | Sentencia C-239 de 1997 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/1997/C-239-97.htm | 2026-09-28 | — (162 fragm.) | Constitucional |
| `sentencia_c_259_2015` | Sentencia C-259 de 2015 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2015/C-259-15.htm | 2026-09-28 | — (119 fragm.) | Administrativo, Procesal |
| `sentencia_c_264_2026` | Sentencia C-264 de 2026 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2026/C-264-26.htm | 2026-09-28 | — (337 fragm.) | Laboral |
| `sentencia_c_274_2013` | Sentencia C-274 de 2013 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2013/C-274-13.htm | 2026-10-01 | — (525 fragm.) | Constitucional, Mercados |
| `sentencia_c_276_2025` | Sentencia C-276 de 2025 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2025/C-276-25.htm | 2026-09-28 | — (126 fragm.) | Comercial y sociedades |
| `sentencia_c_294_2021` | Sentencia C-294 de 2021 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2021/C-294-21.htm | 2026-09-28 | — (406 fragm.) | Penal |
| `sentencia_c_29_2009` | Sentencia C-029 de 2009 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2009/C-029-09.htm | 2026-09-28 | — (349 fragm.) | De familia |
| `sentencia_c_332_2025` | Sentencia C-332 de 2025 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2025/C-332-25.htm | 2026-09-28 | — (105 fragm.) | Constitucional |
| `sentencia_c_335_2008` | Sentencia C-335 de 2008 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2008/C-335-08.htm | 2026-09-28 | — (94 fragm.) | Penal |
| `sentencia_c_345_2017` | Sentencia C-345 de 2017 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2017/C-345-17.htm | 2026-09-28 | — (109 fragm.) | Civil |
| `sentencia_c_355_2006` | Sentencia C-355 de 2006 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2006/C-355-06.htm | 2026-09-28 | — (838 fragm.) | Constitucional, Penal |
| `sentencia_c_35_2009` | Sentencia C-35 de 2009 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2009/C-035-09.htm | 2026-09-28 | — (80 fragm.) | Tributario |
| `sentencia_c_389_2023` | Sentencia C-389 de 2023 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2023/C-389-23.htm | 2026-09-28 | — (80 fragm.) | Tributario |
| `sentencia_c_394_2017` | Sentencia C-394 de 2017 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2017/C-394-17.htm | 2026-09-28 | — (179 fragm.) | Constitucional, De familia |
| `sentencia_c_39_2025` | Sentencia C-39 de 2025 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2025/C-039-25.htm | 2026-09-28 | — (141 fragm.) | De familia |
| `sentencia_c_413_1996` | Sentencia C-413 de 1996 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/1996/C-413-96.htm | 2026-09-28 | — (18 fragm.) | Tributario |
| `sentencia_c_420_2020` | Sentencia C-420 de 2020 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2020/C-420-20.htm | 2026-09-28 | — (327 fragm.) | Procesal |
| `sentencia_c_431_2001` | Sentencia C-431 de 2001 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2001/C-431-01.htm | 2026-09-28 | — (13 fragm.) | Constitucional, Penal |
| `sentencia_c_459_2023` | Sentencia C-459 de 2023 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2023/C-459-23.htm | 2026-09-28 | — (75 fragm.) | Constitucional |
| `sentencia_c_468_2024` | Sentencia C-468 de 2024 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2024/C-468-24.htm | 2026-09-28 | — (77 fragm.) | Constitucional |
| `sentencia_c_481_2019` | Sentencia C-481 de 2019 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2019/C-481-19.htm | 2026-09-28 | — (222 fragm.) | Tributario |
| `sentencia_c_486_1993` | Sentencia C-486 de 1993 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/1993/C-486-93.htm | 2026-09-28 | — (55 fragm.) | Comercial y sociedades |
| `sentencia_c_4_1998` | Sentencia C-4 de 1998 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/1998/C-004-98.htm | 2026-09-28 | — (25 fragm.) | De familia |
| `sentencia_c_500_2024` | Sentencia C-500 de 2024 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2024/C-500-24.htm | 2026-09-28 | — (92 fragm.) | Procesal, Tributario |
| `sentencia_c_507_2004` | Sentencia C-507 de 2004 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2004/C-507-04.htm | 2026-09-28 | — (186 fragm.) | De familia |
| `sentencia_c_533_2000` | Sentencia C-533 de 2000 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2000/C-533-00.htm | 2026-09-28 | — (26 fragm.) | De familia |
| `sentencia_c_535_2002` | Sentencia C-535 de 2002 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2002/C-535-02.htm | 2026-09-28 | — (33 fragm.) | Laboral |
| `sentencia_c_537_1995` | Sentencia C-537 de 1995 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/1995/C-537-95.htm | 2026-09-28 | — (34 fragm.) | Tributario |
| `sentencia_c_540_2023` | Sentencia C-540 de 2023 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2023/C-540-23.htm | 2026-09-28 | — (92 fragm.) | Tributario |
| `sentencia_c_543_1992` | Sentencia C-543 de 1992 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/1992/C-543-92.htm | 2026-09-28 | — (67 fragm.) | Procesal |
| `sentencia_c_551_2003` | Sentencia C-551 de 2003 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2003/C-551-03.htm | 2026-09-28 | — (572 fragm.) | Constitucional |
| `sentencia_c_55_2022` | Sentencia C-55 de 2022 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2022/C-055-22.htm | 2026-09-28 | — (881 fragm.) | Constitucional, Penal |
| `sentencia_c_577_2011` | Sentencia C-577 de 2011 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2011/C-577-11.htm | 2026-09-28 | — (554 fragm.) | De familia |
| `sentencia_c_582_1999` | Sentencia C-582 de 1999 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/1999/C-582-99.htm | 2026-09-28 | — (23 fragm.) | Constitucional |
| `sentencia_c_590_2005` | Sentencia C-590 de 2005 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2005/C-590-05.htm | 2026-09-28 | — (81 fragm.) | Constitucional, Procesal |
| `sentencia_c_591_2005` | Sentencia C-591 de 2005 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2005/c-591-05.htm | 2026-09-28 | — (291 fragm.) | Penal |
| `sentencia_c_614_2009` | Sentencia C-614 de 2009 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2009/C-614-09.htm | 2026-09-28 | — (95 fragm.) | Laboral |
| `sentencia_c_634_2011` | Sentencia C-634 de 2011 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2011/C-634-11.htm | 2026-09-28 | — (97 fragm.) | Administrativo |
| `sentencia_c_683_2015` | Sentencia C-683 de 2015 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2015/C-683-15.htm | 2026-09-28 | — (347 fragm.) | De familia |
| `sentencia_c_700_1999` | Sentencia C-700 de 1999 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/1999/C-700-99.htm | 2026-09-28 | — (122 fragm.) | Constitucional |
| `sentencia_c_71_2015` | Sentencia C-071 de 2015 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2015/c-071-15.htm | 2026-09-28 | — (340 fragm.) | De familia |
| `sentencia_c_746_2011` | Sentencia C-746 de 2011 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2011/C-746-11.htm | 2026-09-28 | — (34 fragm.) | Constitucional, De familia |
| `sentencia_c_748_2011` | Sentencia C-748 de 2011 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2011/C-748-11.htm | 2026-09-28 | — (543 fragm.) | Civil, Mercados |
| `sentencia_c_75_2007` | Sentencia C-075 de 2007 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2007/C-075-07.htm | 2026-09-28 | — (164 fragm.) | De familia |
| `sentencia_c_776_2003` | Sentencia C-776 de 2003 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2003/C-776-03.htm | 2026-09-28 | — (242 fragm.) | Tributario |
| `sentencia_c_80_2025` | Sentencia C-80 de 2025 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2025/C-080-25.htm | 2026-09-28 | — (106 fragm.) | Mercados |
| `sentencia_c_816_2011` | Sentencia C-816 de 2011 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2011/C-816-11.htm | 2026-09-28 | — (113 fragm.) | Administrativo |
| `sentencia_c_818_2011` | Sentencia C-818 de 2011 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2011/C-818-11.htm | 2026-09-28 | — (134 fragm.) | Administrativo |
| `sentencia_c_836_2001` | Sentencia C-836 de 2001 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2001/C-836-01.htm | 2026-09-28 | — (72 fragm.) | Constitucional |
| `sentencia_c_891_2012` | Sentencia C-891 de 2012 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2012/C-891-12.htm | 2026-09-28 | — (56 fragm.) | Tributario |
| `sentencia_c_93_2001` | Sentencia C-093 de 2001 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2001/c-093-01.htm | 2026-09-28 | — (79 fragm.) | Constitucional |
| `sentencia_c_94_2021` | Sentencia C-94 de 2021 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2021/C-094-21.htm | 2026-09-28 | — (100 fragm.) | Constitucional |
| `sentencia_c_951_2014` | Sentencia C-951 de 2014 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2014/C-951-14.htm | 2026-09-28 | — (149 fragm.) | Administrativo |
| `sentencia_c_964_2003` | Sentencia C-964 de 2003 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2003/C-964-03.htm | 2026-09-28 | — (69 fragm.) | De familia |
| `sentencia_c_96_2024` | Sentencia C-96 de 2024 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2024/C-096-24.htm | 2026-09-28 | — (169 fragm.) | De familia |
| `sentencia_c_985_2010` | Sentencia C-985 de 2010 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2010/C-985-10.htm | 2026-09-28 | — (80 fragm.) | De familia |
| `sentencia_ce_05001232500019990106301` | Sentencia de unificación, radicado 05001232500019990106301 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (344 fragm.) | Administrativo |
| `sentencia_ce_05001233100019960065901` | Sentencia de unificación, radicado 05001233100019960065901 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (130 fragm.) | Administrativo |
| `sentencia_ce_05001233100019970117201` | Sentencia de unificación, radicado 05001233100019970117201 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (65 fragm.) | Administrativo |
| `sentencia_ce_05001233100019990215101` | Sentencia de unificación, radicado 05001233100019990215101 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (67 fragm.) | Administrativo |
| `sentencia_ce_05001233100020010079901` | Sentencia de unificación, radicado 05001233100020010079901 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (168 fragm.) | Administrativo |
| `sentencia_ce_05001233300020120057201` | Sentencia de unificación, radicado 05001233300020120057201 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (76 fragm.) | Administrativo |
| `sentencia_ce_05001233300020120079101` | Sentencia de unificación, radicado 05001233300020120079101 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (29 fragm.) | Administrativo |
| `sentencia_ce_05001233300020130074101` | Sentencia de unificación, radicado 05001233300020130074101 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (145 fragm.) | Administrativo |
| `sentencia_ce_05001233300020130114301` | Sentencia de unificación, radicado 05001233300020130114301 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (119 fragm.) | Administrativo |
| `sentencia_ce_05001233300020140082601` | Sentencia de unificación, radicado 05001233300020140082601 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (72 fragm.) | Tributario, Administrativo |
| `sentencia_ce_05001233300020160249601` | Sentencia de unificación, radicado 05001233300020160249601 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (47 fragm.) | Tributario, Administrativo |
| `sentencia_ce_05001333100320090015701` | Sentencia de unificación, radicado 05001333100320090015701 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (184 fragm.) | Administrativo |
| `sentencia_ce_05001333100420070019101` | Sentencia de unificación, radicado 05001333100420070019101 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (254 fragm.) | Administrativo |
| `sentencia_ce_05001333100920060021001` | Sentencia de unificación, radicado 05001333100920060021001 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (255 fragm.) | Administrativo |
| `sentencia_ce_05001333300020130100901` | Sentencia de unificación, radicado 05001333300020130100901 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (92 fragm.) | Administrativo |
| `sentencia_ce_08001233100020110062801` | Sentencia de unificación, radicado 08001233100020110062801 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (57 fragm.) | Administrativo |
| `sentencia_ce_08001233300020120020002` | Sentencia de unificación, radicado 08001233300020120020002 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (55 fragm.) | Administrativo |
| `sentencia_ce_08001233300020130031001` | Sentencia de unificación, radicado 08001233300020130031001 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (51 fragm.) | Administrativo |
| `sentencia_ce_08001233300020180052901` | Sentencia de unificación, radicado 08001233300020180052901 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (94 fragm.) | Administrativo |
| `sentencia_ce_08001333100620070001001` | Sentencia de unificación, radicado 08001333100620070001001 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (116 fragm.) | Administrativo |
| `sentencia_ce_11001031500019980015301` | Sentencia de unificación, radicado 11001031500019980015301 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (62 fragm.) | Administrativo |
| `sentencia_ce_11001031500020070108100` | Sentencia de unificación, radicado 11001031500020070108100 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (69 fragm.) | Administrativo |
| `sentencia_ce_11001031500020090132801` | Sentencia de unificación, radicado 11001031500020090132801 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (120 fragm.) | Administrativo |
| `sentencia_ce_11001031500020120220101` | Sentencia de unificación, radicado 11001031500020120220101 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (96 fragm.) | Administrativo |
| `sentencia_ce_11001031500020150338601` | Sentencia de unificación, radicado 11001031500020150338601 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (49 fragm.) | Administrativo |
| `sentencia_ce_11001031500020160338501` | Sentencia de unificación, radicado 11001031500020160338501 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (267 fragm.) | Administrativo |
| `sentencia_ce_11001031500020190160401` | Sentencia de unificación, radicado 11001031500020190160401 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (126 fragm.) | Administrativo |
| `sentencia_ce_11001032400020120022000` | Sentencia de unificación, radicado 11001032400020120022000 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (113 fragm.) | Administrativo |
| `sentencia_ce_11001032500020050001201` | Sentencia de unificación, radicado 11001032500020050001201 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (352 fragm.) | Administrativo |
| `sentencia_ce_11001032500020050006800` | Sentencia de unificación, radicado 11001032500020050006800 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (159 fragm.) | Administrativo |
| `sentencia_ce_11001032500020110031600` | Sentencia de unificación, radicado 11001032500020110031600 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (216 fragm.) | Administrativo |
| `sentencia_ce_11001032500020110037100` | Sentencia de unificación, radicado 11001032500020110037100 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (132 fragm.) | Administrativo |
| `sentencia_ce_11001032500020140036000` | Sentencia de unificación, radicado 11001032500020140036000 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (230 fragm.) | Administrativo |
| `sentencia_ce_11001032500020170015100` | Sentencia de unificación, radicado 11001032500020170015100 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (72 fragm.) | Administrativo |
| `sentencia_ce_11001032500020180102400` | Sentencia de unificación, radicado 11001032500020180102400 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (20 fragm.) | Administrativo |
| `sentencia_ce_11001032600020100003601` | Sentencia de unificación, radicado 11001032600020100003601 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (355 fragm.) | Administrativo |
| `sentencia_ce_11001032600020110003900` | Sentencia de unificación, radicado 11001032600020110003900 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (154 fragm.) | Administrativo |
| `sentencia_ce_11001032700020180005000` | Sentencia de unificación 2021CE-SUJ-4-001 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (24 fragm.) | Tributario, Administrativo |
| `sentencia_ce_11001032800020100006300` | Sentencia de unificación, radicado 11001032800020100006300 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (57 fragm.) | Administrativo |
| `sentencia_ce_11001032800020100009800` | Sentencia de unificación, radicado 11001032800020100009800 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (48 fragm.) | Administrativo |
| `sentencia_ce_11001032800020110000300` | Sentencia de unificación, radicado 11001032800020110000300 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (217 fragm.) | Administrativo |
| `sentencia_ce_11001032800020120002700` | Sentencia de unificación, radicado 11001032800020120002700 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (217 fragm.) | Administrativo |
| `sentencia_ce_11001032800020130000600` | Sentencia de unificación, radicado 11001032800020130000600 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (85 fragm.) | Administrativo |
| `sentencia_ce_11001032800020130001100` | Sentencia de unificación, radicado 11001032800020130001100 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (342 fragm.) | Administrativo |
| `sentencia_ce_11001032800020130001500` | Sentencia de unificación, radicado 11001032800020130001500 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (170 fragm.) | Administrativo |
| `sentencia_ce_11001032800020140003400` | Sentencia de unificación, radicado 11001032800020140003400 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (105 fragm.) | Administrativo |
| `sentencia_ce_11001032800020150002900` | Sentencia de unificación, radicado 11001032800020150002900 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (37 fragm.) | Administrativo |
| `sentencia_ce_11001032800020150005100` | Sentencia de unificación, radicado 11001032800020150005100 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (111 fragm.) | Administrativo |
| `sentencia_ce_11001032800020160002500` | Sentencia de unificación, radicado 11001032800020160002500 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (293 fragm.) | Administrativo |
| `sentencia_ce_11001032800020160004400` | Sentencia de unificación, radicado 11001032800020160004400 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (43 fragm.) | Administrativo |
| `sentencia_ce_11001032800020180003100` | Sentencia de unificación, radicado 11001032800020180003100 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (196 fragm.) | Administrativo |
| `sentencia_ce_11001032800020200000400` | Sentencia de unificación, radicado 11001032800020200000400 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (134 fragm.) | Administrativo |
| `sentencia_ce_11001333101720080026601` | Sentencia de unificación, radicado 11001333101720080026601 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (62 fragm.) | Administrativo |
| `sentencia_ce_11001333103420090019501` | Sentencia de unificación, radicado 11001333103420090019501 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (53 fragm.) | Administrativo |
| `sentencia_ce_15001233300020160027801` | Sentencia de unificación, radicado 15001233300020160027801 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (76 fragm.) | Administrativo |
| `sentencia_ce_15001233300020160063001` | Sentencia de unificación, radicado 15001233300020160063001 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (250 fragm.) | Administrativo |
| `sentencia_ce_15001333100120040164701` | Sentencia de unificación, radicado 15001333100120040164701 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (67 fragm.) | Administrativo |
| `sentencia_ce_15001333300720170003601` | Sentencia de unificación, radicado 15001333300720170003601 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (105 fragm.) | Administrativo |
| `sentencia_ce_15001333301020130013401` | Sentencia de unificación, radicado 15001333301020130013401 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (131 fragm.) | Administrativo |
| `sentencia_ce_17001333100120090156601` | Sentencia de unificación, radicado 17001333100120090156601 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (288 fragm.) | Administrativo |
| `sentencia_ce_18001233100019990045401` | Sentencia de unificación, radicado 18001233100019990045401 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (203 fragm.) | Administrativo |
| `sentencia_ce_18001233100020060017801` | Sentencia de unificación, radicado 18001233100020060017801 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (82 fragm.) | Administrativo |
| `sentencia_ce_20001333100120070004201` | Sentencia de unificación, radicado 20001333100120070004201 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (39 fragm.) | Administrativo |
| `sentencia_ce_23001233100020010027801` | Sentencia de unificación, radicado 23001233100020010027801 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (108 fragm.) | Administrativo |
| `sentencia_ce_23001233300020130026001` | Sentencia de unificación, radicado 23001233300020130026001 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (97 fragm.) | Administrativo |
| `sentencia_ce_23001233300020140044401` | Sentencia de unificación, radicado 23001233300020140044401 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (77 fragm.) | Administrativo |
| `sentencia_ce_25000231500020020270401` | Sentencia de unificación, radicado 25000231500020020270401 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (277 fragm.) | Administrativo |
| `sentencia_ce_25000232400020110008101` | Sentencia de unificación, radicado 25000232400020110008101 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (93 fragm.) | Administrativo |
| `sentencia_ce_25000232500020100024602` | Sentencia de unificación, radicado 25000232500020100024602 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (38 fragm.) | Administrativo, Laboral |
| `sentencia_ce_25000232600019970393001` | Sentencia de unificación, radicado 25000232600019970393001 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (206 fragm.) | Administrativo |
| `sentencia_ce_25000232600019990000205` | Sentencia de unificación, radicado 25000232600019990000205 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (288 fragm.) | Administrativo |
| `sentencia_ce_25000232600020000034001` | Sentencia de unificación, radicado 25000232600020000034001 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (121 fragm.) | Administrativo |
| `sentencia_ce_25000232600020030020601` | Sentencia de unificación, radicado 25000232600020030020601 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (94 fragm.) | Administrativo |
| `sentencia_ce_25000232600020030020801` | Sentencia de unificación, radicado 25000232600020030020801 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (145 fragm.) | Administrativo |
| `sentencia_ce_25000232600020050032001` | Sentencia de unificación, radicado 25000232600020050032001 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (445 fragm.) | Administrativo |
| `sentencia_ce_25000232600020090013101` | Sentencia de unificación, radicado 25000232600020090013101 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (49 fragm.) | Administrativo |
| `sentencia_ce_25000232600020120029101` | Sentencia de unificación, radicado 25000232600020120029101 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (25 fragm.) | Administrativo |
| `sentencia_ce_25000232700019990071001` | Sentencia de unificación, radicado 25000232700019990071001 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (30 fragm.) | Tributario, Administrativo |
| `sentencia_ce_25000232700020090023501` | Sentencia de unificación, radicado 25000232700020090023501 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (169 fragm.) | Tributario, Administrativo |
| `sentencia_ce_25000232700020100254001` | Sentencia de unificación, radicado 25000232700020100254001 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (243 fragm.) | Administrativo |
| `sentencia_ce_25000233700020130044301` | Sentencia de unificación 2020CE-SUJ-4-005 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (49 fragm.) | Tributario, Administrativo |
| `sentencia_ce_25000233700020130045201` | Sentencia de unificación, radicado 25000233700020130045201 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (99 fragm.) | Tributario, Administrativo |
| `sentencia_ce_25000233700020130110701` | Sentencia de unificación 2021CE-SUJ-4-002 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (52 fragm.) | Tributario, Administrativo |
| `sentencia_ce_25000233700020140050701` | Sentencia de unificación 2022CE-SUJ-4-002 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (23 fragm.) | Tributario, Administrativo |
| `sentencia_ce_25000233700020140058501` | Sentencia de unificación 2021CE-SUJ-4-003 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (49 fragm.) | Tributario, Administrativo |
| `sentencia_ce_25000233700020140072101` | Sentencia de unificación, radicado 25000233700020140072101 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (125 fragm.) | Administrativo |
| `sentencia_ce_25000233700020150037901` | Sentencia de unificación 2020CE-SUJ-4-001 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (25 fragm.) | Tributario, Administrativo |
| `sentencia_ce_25000233700020150050001` | Sentencia de unificación, radicado 25000233700020150050001 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (30 fragm.) | Tributario, Administrativo |
| `sentencia_ce_25000233700020160140501` | Sentencia de unificación 2020CE-SUJ-4-002 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (26 fragm.) | Tributario, Administrativo |
| `sentencia_ce_25000233700020200017402` | Sentencia de unificación, radicado 25000233700020200017402 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (24 fragm.) | Tributario, Administrativo |
| `sentencia_ce_25000234100020150249101` | Sentencia de unificación, radicado 25000234100020150249101 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (94 fragm.) | Administrativo |
| `sentencia_ce_25000234200020130054501` | Sentencia de unificación, radicado 25000234200020130054501 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (120 fragm.) | Administrativo |
| `sentencia_ce_25000234200020130223501` | Sentencia de unificación, radicado 25000234200020130223501 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (115 fragm.) | Administrativo |
| `sentencia_ce_25000234200020130238001` | Sentencia de unificación, radicado 25000234200020130238001 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (84 fragm.) | Administrativo |
| `sentencia_ce_25000234200020130467601` | Sentencia de unificación, radicado 25000234200020130467601 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (45 fragm.) | Administrativo |
| `sentencia_ce_25000234200020130468301` | Sentencia de unificación, radicado 25000234200020130468301 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (85 fragm.) | Administrativo |
| `sentencia_ce_25000234200020160423501` | Sentencia de unificación, radicado 25000234200020160423501 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (73 fragm.) | Administrativo |
| `sentencia_ce_41001233100019940765401` | Sentencia de unificación, radicado 41001233100019940765401 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (280 fragm.) | Administrativo |
| `sentencia_ce_41001233300020160004102` | Sentencia de unificación, radicado 41001233300020160004102 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (110 fragm.) | Administrativo, Laboral |
| `sentencia_ce_47001233300020170019102` | Sentencia de unificación, radicado 47001233300020170019102 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (59 fragm.) | Administrativo |
| `sentencia_ce_47001233300020180017001` | Sentencia de unificación, radicado 47001233300020180017001 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (40 fragm.) | Tributario, Administrativo |
| `sentencia_ce_50001231500019990032601` | Sentencia de unificación, radicado 50001231500019990032601 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (75 fragm.) | Administrativo |
| `sentencia_ce_50001233100020003007201` | Sentencia de unificación, radicado 50001233100020003007201 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (134 fragm.) | Administrativo |
| `sentencia_ce_52001233100019960745901` | Sentencia de unificación, radicado 52001233100019960745901 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (191 fragm.) | Administrativo |
| `sentencia_ce_52001233100020090034901` | Sentencia de unificación, radicado 52001233100020090034901 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (130 fragm.) | Administrativo |
| `sentencia_ce_52001233300020120014301` | Sentencia de unificación, radicado 52001233300020120014301 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (169 fragm.) | Administrativo |
| `sentencia_ce_52001333100420110061701` | Sentencia de unificación, radicado 52001333100420110061701 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (79 fragm.) | Tributario, Administrativo |
| `sentencia_ce_52001333100820080030401` | Sentencia de unificación, radicado 52001333100820080030401 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (151 fragm.) | Administrativo |
| `sentencia_ce_54001233300020140036401` | Sentencia de unificación 2022CE-SUJ-4-001 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (75 fragm.) | Tributario, Administrativo |
| `sentencia_ce_66001233100020010073101` | Sentencia de unificación, radicado 66001233100020010073101 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (285 fragm.) | Administrativo |
| `sentencia_ce_66001233100020070000501` | Sentencia de unificación, radicado 66001233100020070000501 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (69 fragm.) | Administrativo |
| `sentencia_ce_66001233300020200037601` | Sentencia de unificación, radicado 66001233300020200037601 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (65 fragm.) | Tributario, Administrativo |
| `sentencia_ce_66001333100220070010701` | Sentencia de unificación, radicado 66001333100220070010701 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (162 fragm.) | Administrativo |
| `sentencia_ce_66001333100320080041001` | Sentencia de unificación, radicado 66001333100320080041001 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (49 fragm.) | Administrativo |
| `sentencia_ce_66001333300020150030901` | Sentencia de unificación, radicado 66001333300020150030901 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (51 fragm.) | Administrativo |
| `sentencia_ce_66001333300120120014101` | Sentencia de unificación, radicado 66001333300120120014101 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (66 fragm.) | Administrativo |
| `sentencia_ce_66001333300120220001601` | Sentencia de unificación, radicado 66001333300120220001601 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (137 fragm.) | Administrativo |
| `sentencia_ce_66001333300220130004501` | Sentencia de unificación, radicado 66001333300220130004501 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (131 fragm.) | Administrativo |
| `sentencia_ce_68001233100020020254801` | Sentencia de unificación, radicado 68001233100020020254801 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (40 fragm.) | Administrativo |
| `sentencia_ce_68001233300020150056901` | Sentencia de unificación, radicado 68001233300020150056901 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (69 fragm.) | Administrativo |
| `sentencia_ce_68001233300020150096501` | Sentencia de unificación, radicado 68001233300020150096501 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (118 fragm.) | Administrativo |
| `sentencia_ce_68001333101420130015801` | Sentencia de unificación, radicado 68001333101420130015801 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (61 fragm.) | Administrativo |
| `sentencia_ce_73001233100020000307501` | Sentencia de unificación, radicado 73001233100020000307501 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (160 fragm.) | Administrativo |
| `sentencia_ce_73001233100020010041801` | Sentencia de unificación, radicado 73001233100020010041801 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (88 fragm.) | Administrativo |
| `sentencia_ce_73001233100020090013301` | Sentencia de unificación, radicado 73001233100020090013301 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (122 fragm.) | Administrativo |
| `sentencia_ce_73001233300020140058001` | Sentencia de unificación, radicado 73001233300020140058001 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (193 fragm.) | Administrativo |
| `sentencia_ce_76001233100019960520801` | Sentencia de unificación, radicado 76001233100019960520801 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (240 fragm.) | Administrativo |
| `sentencia_ce_76001233100020020458402` | Sentencia de unificación, radicado 76001233100020020458402 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (383 fragm.) | Administrativo |
| `sentencia_ce_76001233100020060332003` | Sentencia de unificación, radicado 76001233100020060332003 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (100 fragm.) | Administrativo |
| `sentencia_ce_76001233100020080084601` | Sentencia de unificación, radicado 76001233100020080084601 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (190 fragm.) | Administrativo |
| `sentencia_ce_76001233300020140000801` | Sentencia de unificación, radicado 76001233300020140000801 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (57 fragm.) | Tributario, Administrativo |
| `sentencia_ce_76001233300020160053901` | Sentencia de unificación, radicado 76001233300020160053901 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (30 fragm.) | Tributario, Administrativo |
| `sentencia_ce_81001233300020140001201` | Sentencia de unificación, radicado 81001233300020140001201 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (153 fragm.) | Administrativo |
| `sentencia_ce_85001233100019950017401` | Sentencia de unificación, radicado 85001233100019950017401 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (128 fragm.) | Administrativo |
| `sentencia_ce_85001333300020130023701` | Sentencia de unificación, radicado 85001333300020130023701 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (219 fragm.) | Administrativo |
| `sentencia_ce_85001333300220130006001` | Sentencia de unificación, radicado 85001333300220130006001 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (85 fragm.) | Administrativo |
| `sentencia_ce_85001333300220140014401` | Sentencia de unificación, radicado 85001333300220140014401 | SAMAI (Consejo de Estado) | https://samai.consejodeestado.gov.co/ | 2026-10-01 | — (212 fragm.) | Administrativo |
| `sentencia_sc_18392_2017` | Sentencia SC-18392 de 2017 | Relatoría de la Corte Suprema de Justicia | https://cortesuprema.gov.co/corte/wp-content/uploads/2019/02/SC18392-2017-2011-00081-01-1-47.pdf | 2026-10-01 | — (50 fragm.) | Comercial y sociedades |
| `sentencia_sc_3085_2024` | Sentencia SC-3085 de 2024 | Relatoría de la Corte Suprema de Justicia | https://archivodigitalapi.cortesuprema.gov.co/share/2024/12/Sentencias/SC3085-2024.pdf | 2026-09-30 | — (113 fragm.) | De familia |
| `sentencia_sc_425_2024` | Sentencia SC-425 de 2024 | Relatoría de la Corte Suprema de Justicia | https://ecosistemadigitalindice.cortesuprema.gov.co/api/v1/link/share/6615b19b4051fbcca141847d | 2026-09-30 | — (89 fragm.) | Comercial y sociedades |
| `sentencia_sc_8453_2016` | Sentencia SC-8453 de 2016 | Relatoría de la Corte Suprema de Justicia | https://cortesuprema.gov.co/corte/wp-content/uploads/2022/03/SC8453-2016-2014-02243-00-C.pdf | 2026-09-30 | — (45 fragm.) | Comercial y sociedades |
| `sentencia_sl_1050_2023` | Sentencia SL-1050 de 2023 | Relatoría de la Corte Suprema de Justicia | https://cortesuprema.gov.co/corte/wp-content/uploads/2023/07/SL1050-2023.pdf | 2026-09-30 | — (69 fragm.) | Laboral |
| `sentencia_sl_1730_2020` | Sentencia SL-1730 de 2020 | Relatoría de la Corte Suprema de Justicia | https://cortesuprema.gov.co/corte/wp-content/uploads/relatorias/la/bjul2020/SL1730-2020.pdf | 2026-10-01 | — (68 fragm.) | Laboral |
| `sentencia_sl_3385_2022` | Sentencia SL-3385 de 2022 | Relatoría de la Corte Suprema de Justicia | https://www.cortesuprema.gov.co/corte/wp-content/uploads/relatorias/la/bnov2022/SL3385-2022.pdf | 2026-09-30 | — (26 fragm.) | Laboral |
| `sentencia_sl_3871_2021` | Sentencia SL-3871 de 2021 | Relatoría de la Corte Suprema de Justicia | https://cortesuprema.gov.co/corte/wp-content/uploads/relatorias/la/bnov2021/SL3871-2021.pdf | 2026-10-03 | — (25 fragm.) | Laboral |
| `sentencia_sl_648_2018` | Sentencia SL-648 de 2018 | Relatoría de la Corte Suprema de Justicia | https://cortesuprema.gov.co/corte/wp-content/uploads/2018/03/SL648-2018-55122-Acoso-sexual-en-el-trabajo.pdf | 2026-09-30 | — (54 fragm.) | Laboral |
| `sentencia_sp_1167_2022` | Sentencia SP-1167 de 2022 | Relatoría de la Corte Suprema de Justicia | https://cortesuprema.gov.co/corte/wp-content/uploads/relatorias/pe/b1may2022/SP1167-2022(57957).pdf | 2026-09-30 | — (42 fragm.) | Penal |
| `sentencia_sp_1680_2022` | Sentencia SP-1680 de 2022 | Relatoría de la Corte Suprema de Justicia | https://cortesuprema.gov.co/corte/wp-content/uploads/relatorias/pe/b1may2022/SP1680-2022(60875).pdf | 2026-09-30 | — (42 fragm.) | Penal |
| `sentencia_sp_1945_2019` | Sentencia SP-1945 de 2019 | Relatoría de la Corte Suprema de Justicia | https://cortesuprema.gov.co/corte/wp-content/uploads/relatorias/pe/b1ago2019/SP1945-2019(50523).PDF | 2026-10-01 | — (25 fragm.) | Penal |
| `sentencia_sp_3218_2021` | Sentencia SP-3218 de 2021 | Relatoría de la Corte Suprema de Justicia | https://cortesuprema.gov.co/corte/wp-content/uploads/relatorias/pe/b1ago2021/SP3218-2021(47063).pdf | 2026-09-30 | — (106 fragm.) | Penal |
| `sentencia_su_111_2025` | Sentencia SU-111 de 2025 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2025/SU111-25.htm | 2026-09-28 | — (180 fragm.) | Laboral |
| `sentencia_su_11_2020` | Sentencia SU-11 de 2020 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2020/SU011-20.htm | 2026-09-28 | — (108 fragm.) | Administrativo |
| `sentencia_su_138_2024` | Sentencia SU-138 de 2024 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2024/SU138-24.htm | 2026-09-28 | — (201 fragm.) | Civil |
| `sentencia_su_149_2021` | Sentencia SU-149 de 2021 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2021/SU149-21.htm | 2026-09-28 | — (116 fragm.) | Laboral |
| `sentencia_su_16_2020` | Sentencia SU-16 de 2020 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2020/SU016-20.htm | 2026-09-28 | — (263 fragm.) | Constitucional |
| `sentencia_su_207_2022` | Sentencia SU-207 de 2022 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2022/SU207-22.htm | 2026-09-28 | — (120 fragm.) | Civil |
| `sentencia_su_214_2016` | Sentencia SU-214 de 2016 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2016/SU214-16.htm | 2026-09-28 | — (627 fragm.) | De familia |
| `sentencia_su_240_2015` | Sentencia SU-240 de 2015 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2015/SU240-15.htm | 2026-09-28 | — (96 fragm.) | Administrativo |
| `sentencia_su_277_2025` | Sentencia SU-277 de 2025 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2025/SU277-25.htm | 2026-09-28 | — (157 fragm.) | Administrativo |
| `sentencia_su_27_2021` | Sentencia SU-27 de 2021 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2021/SU027-21.htm | 2026-09-28 | — (100 fragm.) | Laboral |
| `sentencia_su_296_2023` | Sentencia SU-296 de 2023 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2023/SU296-23.htm | 2026-09-28 | — (160 fragm.) | Laboral |
| `sentencia_su_315_2025` | Sentencia SU-315 de 2025 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2025/SU315-25.htm | 2026-09-28 | — (164 fragm.) | Civil |
| `sentencia_su_380_2021` | Sentencia SU-380 de 2021 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2021/SU380-21.htm | 2026-09-28 | — (102 fragm.) | Civil |
| `sentencia_su_396_2024` | Sentencia SU-396 de 2024 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2024/SU396-24.htm | 2026-09-28 | — (173 fragm.) | Laboral |
| `sentencia_su_425_2025` | Sentencia SU-425 de 2025 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2025/SU425-25.htm | 2026-09-28 | — (77 fragm.) | Civil |
| `sentencia_su_429_2024` | Sentencia SU-429 de 2024 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2024/SU429-24.htm | 2026-09-28 | — (242 fragm.) | Penal |
| `sentencia_su_431_2015` | Sentencia SU-431 de 2015 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2015/SU431-15.htm | 2026-09-28 | — (257 fragm.) | Civil |
| `sentencia_su_455_2020` | Sentencia SU-455 de 2020 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2020/SU455-20.htm | 2026-09-28 | — (104 fragm.) | Civil |
| `sentencia_su_47_1999` | Sentencia SU-047 de 1999 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/1999/SU047-99.htm | 2026-09-28 | — (253 fragm.) | Constitucional |
| `sentencia_su_49_2017` | Sentencia SU-049 de 2017 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2017/SU049-17.htm | 2026-09-28 | — (70 fragm.) | Laboral |
| `sentencia_su_500_2015` | Sentencia SU-500 de 2015 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2015/SU500-15.htm | 2026-09-28 | — (340 fragm.) | Civil |
| `sentencia_su_566_2015` | Sentencia SU-566 de 2015 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2015/SU566-15.htm | 2026-09-28 | — (183 fragm.) | Administrativo |
| `sentencia_su_75_2018` | Sentencia SU-075 de 2018 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2018/SU075-18.htm | 2026-09-28 | — (247 fragm.) | Laboral |
| `sentencia_t_1001_2001` | Sentencia T-1001 de 2001 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2001/T-1001-01.htm | 2026-09-28 | — (69 fragm.) | Constitucional |
| `sentencia_t_1059_2001` | Sentencia T-1059 de 2001 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2001/T-1059-01.htm | 2026-09-28 | — (67 fragm.) | Laboral |
| `sentencia_t_1096_2008` | Sentencia T-1096 de 2008 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2008/T-1096-08.htm | 2026-09-28 | — (102 fragm.) | De familia |
| `sentencia_t_145_2016` | Sentencia T-145 de 2016 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2016/T-145-16.htm | 2026-09-28 | — (82 fragm.) | Laboral |
| `sentencia_t_230_2023` | Sentencia T-230 de 2023 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2023/T-230-23.htm | 2026-09-28 | — (28 fragm.) | Constitucional |
| `sentencia_t_232_2025` | Sentencia T-232 de 2025 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2025/T-232-25.htm | 2026-09-28 | — (95 fragm.) | De familia |
| `sentencia_t_243_2018` | Sentencia T-243 de 2018 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2018/T-243-18.htm | 2026-09-28 | — (67 fragm.) | Laboral |
| `sentencia_t_256_2025` | Sentencia T-256 de 2025 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2025/T-256-25.htm | 2026-10-01 | — (243 fragm.) | Constitucional |
| `sentencia_t_25_2004` | Sentencia T-025 de 2004 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2004/T-025-04.htm | 2026-09-28 | — (315 fragm.) | Constitucional |
| `sentencia_t_262_2025` | Sentencia T-262 de 2025 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2025/T-262-25.htm | 2026-09-28 | — (98 fragm.) | Constitucional |
| `sentencia_t_26_2025` | Sentencia T-26 de 2025 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2025/T-026-25.htm | 2026-09-28 | — (134 fragm.) | Civil |
| `sentencia_t_323_2024` | Sentencia T-323 de 2024 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2024/T-323-24.htm | 2026-09-28 | — (244 fragm.) | Constitucional |
| `sentencia_t_325_2025` | Sentencia T-325 de 2025 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2025/T-325-25.htm | 2026-09-28 | — (75 fragm.) | Constitucional |
| `sentencia_t_350_2025` | Sentencia T-350 de 2025 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2025/T-350-25.htm | 2026-09-28 | — (93 fragm.) | De familia |
| `sentencia_t_406_1992` | Sentencia T-406 de 1992 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/1992/T-406-92.htm | 2026-09-28 | — (62 fragm.) | Constitucional |
| `sentencia_t_429_2011` | Sentencia T-429 de 2011 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2011/T-429-11.htm | 2026-09-28 | — (46 fragm.) | Constitucional |
| `sentencia_t_445_2024` | Sentencia T-445 de 2024 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2024/T-445-24.htm | 2026-09-28 | — (125 fragm.) | Constitucional |
| `sentencia_t_4_2026` | Sentencia T-4 de 2026 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2026/T-004-26.htm | 2026-09-28 | — (113 fragm.) | Civil |
| `sentencia_t_547_2017` | Sentencia T-547 de 2017 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2017/T-547-17.htm | 2026-09-28 | — (71 fragm.) | Constitucional, Laboral |
| `sentencia_t_67_2025` | Sentencia T-67 de 2025 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2025/T-067-25.htm | 2026-09-28 | — (187 fragm.) | Constitucional |
| `sentencia_t_71_2016` | Sentencia T-71 de 2016 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2016/T-071-16.htm | 2026-09-28 | — (63 fragm.) | De familia |
| `sentencia_t_760_2008` | Sentencia T-760 de 2008 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2008/T-760-08.htm | 2026-09-28 | — (459 fragm.) | Administrativo, Constitucional |
| `sentencia_t_77_2025` | Sentencia T-77 de 2025 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2025/T-077-25.htm | 2026-09-28 | — (77 fragm.) | De familia |
| `sentencia_t_881_2002` | Sentencia T-881 de 2002 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2002/T-881-02.htm | 2026-09-28 | — (135 fragm.) | Constitucional |
| `sentencia_t_925_2014` | Sentencia T-925 de 2014 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2014/T-925-14.htm | 2026-09-28 | — (35 fragm.) | Constitucional |
| `sentencia_t_970_2014` | Sentencia T-970 de 2014 | Relatoría de la Corte Constitucional | https://www.corteconstitucional.gov.co/relatoria/2014/T-970-14.htm | 2026-09-28 | — (113 fragm.) | Constitucional |
