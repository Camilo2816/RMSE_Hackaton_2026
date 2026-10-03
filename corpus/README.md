# corpus/

Artefactos pesados del corpus. **Su contenido no se versiona** (ver `.gitignore`):
se publica comprimido en Zenodo y el enlace va en la sección "Corpus e índice"
del `README.md`. Solo se versiona esta estructura.

| Carpeta | Contenido | Lo produce |
|---|---|---|
| `raw/` | HTML/PDF/JS originales por `<doc_id>/` + `_descarga.json` (URL, fecha, sha256) | `src/ingest/descargar.py` |
| `interim/` | `<doc_id>.json`: estructura extraída (artículos, ruta, notas) + `qa` | `src/ingest/extraer.py` |
| `processed/` | `<doc_id>.txt` (concatenación literal de fragmentos) + `fragmentos/<doc_id>.jsonl` + `fragmentos.jsonl` | `src/ingest/segmentar.py` |
| `index/` | `embeddings.npy` / `index.faiss`, `bm25/`, `metadata.jsonl`, `config.json` | `src/index/construir.py` |
| `dist/` | `corpus_<equipo>.zip` para Zenodo | empaquetado final (ver `docs/CONTRATOS.md` §10) |

Para reconstruirlo desde cero: `bash run.sh`.
