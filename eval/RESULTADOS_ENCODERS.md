# Benchmark de encoders — 2026-10-01

`eval/benchmark_encoders.py`: cada encoder embebe los 66.291 fragmentos del
índice congelado (caché fuera del repo) y reemplaza solo el recuperador denso
del pipeline **baseline** en memoria; BM25, lookup y reranker
(`bge-reranker-v2-m3`) son los de la entrega. 41 ítems calificables de
sample_50, sin LLM. `corpus/index/` no se toca. Datos: `eval/runs/benchmark_encoders.json`.

| Encoder | Denso solo body-hit@10 | Denso solo recall@10 | Propio en top-50 | Pipeline body-hit | Pipeline recall | Pipeline article-hit | Indexar (4090) |
|---|---:|---:|---:|---:|---:|---:|---:|
| `BAAI/bge-m3` (entrega) | 0,902 | 0,857 | 0,927 | 0,927 | 0,898 | 0,579 | — |
| `jinaai/jina-embeddings-v3` | 0,878 | 0,857 | 0,927 | **0,951** | **0,939** | 0,526 | 9 min |
| `Qwen/Qwen3-Embedding-4B` | **0,951** | **0,918** | 0,927 | 0,927 | 0,898 | 0,579 | 33 min |
| `Snowflake/snowflake-arctic-embed-l-v2.0` | 0,902 | 0,857 | 0,878 | 0,927 | 0,918 | 0,579 | 2,5 min |
| `intfloat/multilingual-e5-large` | 0,854 | 0,796 | 0,854 | 0,927 | 0,898 | 0,579 | 2,9 min |

## Lectura

- El mejor encoder aislado (Qwen3-Embedding-4B) no mejora el pipeline: BM25,
  lookup y reranker compensan las diferencias del denso. El cuello de botella
  medido sigue siendo el reranker (hunde la norma de 128 y 247).
- jina-v3 es el único que mejora el pipeline baseline (arregla 679 en la primera
  pasada; el agéntico ya lo arregla con el re-planeo) y baja el article-hit.
  Su código remoto no carga con transformers 5.18 sin un parche
  (`PreTrainedModel.all_tied_weights_keys`), aplicado solo en el benchmark.
- Lección de la fase 2 y de la fusión híbrido/reranker: mejoras del techo de
  recuperación de 1–2 cuerpos no se trasladan a la corrida completa; cambiar el
  encoder cambia los 10 pasajes de casi todos los ítems.
