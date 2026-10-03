# Benchmark de decoders — 2026-10-01

Mismo sistema para todos (`configs/agentic.yaml`, índice congelado, prompts
ajustados con Qwen3); solo cambia `generation.model_ollama`, que también hace de
planner. Local en Ollama 0.12.6 (RTX 4090), q4, temperatura 0: las mismas
condiciones de la ejecución del sábado. RAGAS: los cinco juzgados en la misma
sesión con `scripts/evaluate.py --ragas` (juez `z-ai/glm-5.3-flash`).

## sample_50 (rúbrica automática, /80)

| Decoder | Cerradas (/15) | RAGAS | Citas | Abstención | **Total** | s/pregunta |
|---|---:|---:|---:|---:|---:|---:|
| **Llama-3.1-8B-Instruct** (`llama3.1:8b`) | 13 · 17,33 | 0,460 · 13,80 | 18,37 | 9,53 | **59,03** | 3,3 |
| Ministral-8B-Instruct-2410 (GGUF Q4_K_M) | 10 · 13,33 | **0,500 · 15,00** | 17,96 | 8,60 | 54,89 | 3,4 |
| Qwen3-8B (`qwen3:8b`, entrega actual) | 11 · 14,67 | 0,431 · 12,92 ¹ | 18,37 | 8,84 | 54,80 | 3,4 |
| Salamandra-7B-Instruct (GGUF Q4_K_M, ctx 8192) | 8 · 10,67 | 0,441 · 13,23 | 17,14 | 7,91 | 48,95 | 3,5 |
| Granite 4.2 8B (`granite4.2:8b`) | 5 · 6,67 | 0,273 · 8,19 | 16,33 | 6,86 | 38,05 | 9,8 |

¹ El juez no devolvió veredicto en 1 ítem (cuenta 0). La misma submission juzgada
antes dio 13,59 (total 55,47): el ruido del juez es de ~0,5 pts.

## data_50.jsonl (50 cerradas adicionales, ids 9001–9050)

| Decoder | Aciertos | Citas (/58 cuerpos) | Sin respaldo |
|---|---:|---:|---:|
| Llama-3.1-8B | **49** (98 %) | 57 | 0 |
| Ministral-8B-2410 | **49** (98 %) | 57 | 0 |
| Qwen3-8B | 47 (94 %) | 57 | 0 |
| Salamandra-7B | 31 (62 %) | 57 | 0 |
| Granite 4.2 8B | 13 (26 %) | — | — |

Las citas no dependen del decoder: `completar_referencia` las arma desde los pasajes.

## Llama frente a Qwen3 en las 65 cerradas

Qwen falla y Llama acierta: 9005, 9020, 9035, 58, 128 · Llama falla y Qwen
acierta: 9021 · ambos fallan: 528, 671. 62/65 (95 %) frente a 58/65 (89 %);
McNemar exacto 5 contra 1, p ≈ 0,22 (dirección consistente en los dos
conjuntos, no concluyente por sí sola).

## Observaciones

- **Llama-3.1-8B gana en total (+4,2 sobre Qwen3)**: cerradas (+2,67),
  abstención (+0,69) y RAGAS (+0,2 a +0,9 según el juzgamiento de Qwen).
  Determinista: salidas idénticas en tres corridas independientes (24, 58, 679).
- Ministral tiene el mejor RAGAS (0,50) pero pierde cerradas en sample_50.
  Ministral 3 (2512) no corre en Ollama 0.12.6; se usó la versión 2410.
- Granite 4.2 devuelve marcadores (`"<texto completo>"`, `"String"`) en lugar
  de respuestas con el JSON restringido: incompatible con este formato de salida.
- Salamandra copia la plantilla del prompt (`"Ley <número> de <año>"`) y su
  contexto de 8192 tokens obliga a recortar `num_ctx`.
- Descartados antes de medir: Qwen3.5-9B (> 8B), Aya Expanse 8B (Cohere,
  prohibido por el enunciado §3.2).

Corridas: `eval/runs/bench_dec_sample_<modelo>/` y `eval/runs/bench_dec_data50_<modelo>/`
(Qwen3 en sample: `eval/runs/2026-10-01_fase3b_feedback_fijo/`, `report_ragas_bench.json`).
