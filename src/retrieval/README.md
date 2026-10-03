# src/retrieval

**Responsabilidad:** Lookup directo (sin LLM), denso, BM25, híbrido RRF, rerank y fusión final determinista.
**Entradas:** Consultas + índice congelado de `corpus/index/`.
**Salidas:** ≤ 10 `Passage`, lookup primero.

| Módulo | Qué hace |
|---|---|
| `bm25.py` | BM25 de bm25s sobre `src/index/tokenizar.py`; top-k exacto con desempate `(doc_id, chunk_id)` |
| `dense.py` | bge-m3 (prefijos `query:` si el encoder es E5); producto interno contra la matriz normalizada |
| `hybrid.py` | RRF entre denso y BM25 (`retrieval.top_k_per_query` de cada uno, `rrf_k`) |
| `lookup.py` | Citas de la consulta con el extractor oficial → artículos exactos (`partes_por_articulo`), ficha de sentencias y mejores fragmentos del documento nombrado (`por_norma`); tope `max_hits`. Complementa artículos compuestos (`2.2.1.1.1.1`, `240-1`) y sentencias sin año; exige "Constitución Política" completa si no hay artículo |
| `rerank.py` | bge-reranker-v2-m3 (fp16) sobre los `rerank.candidates` primeros del híbrido; entrada en orden canónico para que los lotes no dependan del híbrido |
| `fusion.py` | `ordenar` (score redondeado a 1e-6, desempate estable), `rrf`, `penalizar_vigencia` (tras el rerank, score × `fusion.factor_vigencia` para ordenar derogados e inexequibles; no filtra ni cambia el score) y `fuse` (lookup primero, sin duplicados, ≤ `max_passages`) |

Medición: `python eval/retrieval_ceiling.py --config configs/baseline.yaml [--set clave=valor ...]`.
