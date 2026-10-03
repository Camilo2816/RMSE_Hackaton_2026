# tests/

`pytest` desde la raíz. Los tests de etapas sin implementar siguen en `skip`.

| Archivo | Garantiza |
|---|---|
| `test_fusion.py` | ≤ 10 pasajes; mismo input → mismo orden; lookup primero; RRF |
| `test_common.py` | Merge de configs; `to_submission` válido para `evaluate.validate`; `Question` sin respuestas; respaldo igual que `evaluate.py` |
| `test_tokenizar.py` | Artículos de un dígito, ordinales, sentencias y numeraciones como tokens de BM25 |
| `test_indice.py` | Filas alineadas; BM25 trae la norma nombrada; híbrido determinista (si el índice existe) |
| `test_lookup.py` | Artículo nombrado primero; artículos compuestos; ficha de sentencias; "constitución de la sociedad" no es la Constitución; topes |
| `test_retrieve.py` | `Pipeline.retrieve` con reranker: ≤ 10, lookup primero, determinista, tiempos por etapa |
| `test_verifier.py` | Una cita ausente de los pasajes se elimina |
| `test_determinism.py` | Dos corridas del mismo pipeline → mismos pasajes y citas (verificación en vivo) |
| `test_fuentes.py` | `nombre_citable` de `sources/*.yaml` produce su `canonico`; `doc_id` únicos |
| `test_fragmentos.py` | Prefijo citable y offsets válidos en los fragmentos |
| `test_sin_fuga.py` | El índice no contiene `data/*.jsonl` ni `docs/kit/` |
| `test_submission.py` | Esquema oficial; `pasajes_recuperados` = pasajes que vio el LLM |
