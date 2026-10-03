# src/index

**Responsabilidad:** Construcción y carga del índice híbrido (denso + BM25).
**Entradas:** `corpus/processed/fragmentos.jsonl` únicamente (nunca data/ ni docs/kit/).
**Salidas:** `corpus/index/`: `embeddings.npy`, `bm25/`, `metadata.jsonl` con filas alineadas a
`fragmentos.jsonl`, `config.json` (docs/CONTRATOS.md §4).

```bash
python -m src.index.construir                  # denso (bge-m3, GPU) + BM25
python -m src.index.construir --partes bm25    # solo BM25, p. ej. tras cambiar tokenizar.py
```

| Módulo | Qué hace |
|---|---|
| `construir.py` | Embeddings normalizados en float16 (`retrieval.encoder`, `max_seq_length`), BM25 de bm25s, copia de metadata y `config.json` con el sha256 de `fragmentos.jsonl` por parte |
| `cargar.py` | `cargar()` → `Indice` (en caché). Rechaza partes construidas sobre otro `fragmentos.jsonl` o con otra versión del tokenizador; `Indice.pasaje()` arma un `Passage` |
| `tokenizar.py` | Tokenización de BM25, igual para corpus y consultas: sin tildes, ordinales ("3o" → "3"), sentencias ("C-355" → `c_355`) y numeraciones ("2.2.1.1" → `2_2_1_1`) como un token, stopwords y Snowball español |
