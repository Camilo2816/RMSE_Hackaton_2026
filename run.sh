#!/usr/bin/env bash
# Comando único de reproducción: responde el split y lo evalúa (sin --ragas).
#   bash run.sh [sample|test] [configs/agentic.yaml|configs/baseline.yaml]   (por defecto el agéntico, el de la entrega)
# Requiere el índice en corpus/index/ (corpus_snapshot.zip o python -m src.index.construir)
# y Ollama con el modelo de generation.model sirviendo en localhost:11434.
# Si la corrida se cae, relanzar el mismo comando con OUT=<carpeta> la reanuda.
set -euo pipefail
cd "$(dirname "$0")"
SPLIT="${1:-sample}"
CONFIG="${2:-configs/agentic.yaml}"
OUT="${OUT:-eval/runs/$(date +%Y-%m-%d_%H%M)_$(basename "$CONFIG" .yaml)}"
PY="${PYTHON:-python}"

# Reconstrucción del corpus desde las fuentes (opcional; el índice publicado ya lo trae):
# $PY -m src.ingest.resolver && $PY -m src.ingest.descargar && $PY -m src.ingest.extraer
# $PY -m src.ingest.segmentar && $PY -m src.ingest.manifest && $PY -m src.index.construir

"$PY" -m src.main --config "$CONFIG" --split "$SPLIT" --out "$OUT"
"$PY" -m src.submission.validate "$OUT/submission.jsonl" --split "$SPLIT"
if [ "$SPLIT" = "sample" ]; then
  "$PY" scripts/evaluate.py --submission "$OUT/submission.jsonl" --split "$SPLIT" --out "$OUT/report.json"
fi
