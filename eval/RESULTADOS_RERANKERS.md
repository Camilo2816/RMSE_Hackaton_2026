# Benchmark de rerankers — 2026-10-01

`eval/benchmark_rerankers.py`: reemplaza solo el reranker del pipeline
**baseline** en memoria (lookup, híbrido y bge-m3 son los de la entrega) y mide
con `eval/retrieval_ceiling.ceiling` sobre los 41 ítems calificables de
sample_50, sin LLM generador. Los rerankers LLM puntúan con P("yes") en el
formato oficial de cada modelo; Qwen3-Reranker recibe una instrucción de dominio
(derecho colombiano). Datos por ítem: `eval/runs/benchmark_rerankers.json`.

| Reranker | Tipo | Body-hit | Recall cuerpos | Article-hit | Rerank p95 | Fallos |
|---|---|---:|---:|---:|---:|---|
| `BAAI/bge-reranker-v2-m3` (entrega) | cross-encoder 568M | 0,927 | 0,898 | 0,579 | 0,22 s | 128, 247, 679 |
| `Qwen/Qwen3-Reranker-4B` | LLM 4B | 0,927 | 0,898 | **0,632** | 1,35 s | 128, 247, 679 |
| `Qwen/Qwen3-Reranker-0.6B` | LLM 0,6B | 0,927 | 0,898 | **0,632** | 0,45 s | 128, 247, 679 |
| `BAAI/bge-reranker-v2-gemma` | LLM 2,5B | 0,927 | 0,898 | **0,632** | 0,65 s | 128, 247, 679 |
| sin reranker (orden del híbrido) | — | 0,927 | 0,918 | 0,421 | — | 247, 679, 879 |
| `jinaai/jina-reranker-v2-base-multilingual` | cross-encoder 278M | no carga con transformers 5.18 (código remoto) | | | | |
| `Alibaba-NLP/gte-multilingual-reranker-base` | cross-encoder 306M | no carga con transformers 5.18 (código remoto) | | | | |

## Por ítem frente a bge-reranker-v2-m3

- Qwen3-Reranker 4B y 0,6B y bge-v2-gemma: los mismos cuerpos en los 41 ítems;
  solo ganan el artículo exacto en 674.
- Sin reranker: gana 128 y 1073, pierde 879 y el artículo exacto en 352, 358 y 589.

## Lectura

- Ningún reranker arregla 128 ni 247: la norma correcta queda abajo con los
  cuatro. No es una limitación de bge-reranker-v2-m3 sino del planteamiento
  (pregunta narrativa frente a texto normativo: patrón P2 de la auditoría).
- La ganancia de los LLM rerankers es un artículo en 19 ítems, a 2–6 veces la
  latencia y con otra escala de score (habría que recalibrar
  `verification.replan_min_rerank_score`). No justifica el cambio antes del
  congelamiento.
- El reranker sí aporta: sin él el article-hit cae de 0,579 a 0,421.
