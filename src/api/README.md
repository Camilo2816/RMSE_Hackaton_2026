# src/api

**Responsabilidad:** FastAPI para la interfaz: el pipeline se construye una vez al arrancar con `registry.build_pipeline(cfg)`; `POST /preguntar` responde con `Answer` + `Trace` + normas citadas. También sirve la interfaz estática de `interfaz/`.
**Entradas:** Pregunta (texto, formato, opciones).
**Salidas:** Respuesta, pasajes, normas citadas, tiempos por etapa.

## Arrancar

```bash
python -m src.api --config configs/agentic.yaml --port 8000   # --host 0.0.0.0 para abrirla en la red local
```

Abrir `http://127.0.0.1:8000/`. La carga del pipeline (modelos a GPU) ocurre antes
de que el servidor acepte peticiones; la primera consulta con Ollama en frío
puede tardar más de un minuto, luego ~4 s. Requiere `corpus/` con el índice y Ollama corriendo.

## Endpoints

| Método | Ruta | Qué hace |
|---|---|---|
| `POST` | `/preguntar` | Corre el pipeline sobre una pregunta (de a una: un lock, una sola GPU). |
| `GET` | `/salud` | `{"estado", "pipeline", "config", "ocupado", "atendidas"}`. |
| `GET` | `/` | Interfaz (`interfaz/index.html`, `estilos.css`, `app.js`). |
| `GET` | `/docs` | Swagger de FastAPI. |

### `POST /preguntar` (docs/CONTRATOS.md §8)

```json
// request
{"pregunta": "...", "formato": "semi_open", "opciones": null, "config": "configs/baseline.yaml"}
// response
{"answer": {"id", "formato", "abstencion", "<claves del formato>", "pasajes_recuperados", "latencia_ms"},
 "trace":  {"subqueries", "fused_passages", "verdicts", "iterations", "timings", "...": "Trace.to_json()"},
 "normas_citadas": [{"cita": "Ley 472 de 1998, art. 3", "respaldada": true, "articulo_en_pasajes": true,
                     "canonica": ["ley", "472", "1998", "3"], "patrones": {"cuerpo": ["..."], "articulo": "..."}}],
 "pasajes": [{"doc_id", "chunk_id", "norma", "articulo", "texto", "score", "fuente_query", "normas_citadas": [0]}]}
```

- `formato`: `multiple_choice` | `semi_open` | `open_ended`. En `multiple_choice` son obligatorias las
  opciones `A`–`D` con texto; en los otros formatos las opciones se ignoran. Entrada inválida → 422.
- `config` es opcional; si no coincide con la que cargó el servidor → 409 (el pipeline no se recarga por petición).
- Falla del pipeline → 500 con `detail`; el servidor sigue atendiendo.
- `normas_citadas` sale del extractor oficial (`src.verification.citations`) sobre el mismo texto que usa
  `evaluate.py` (`answer_text`). `respaldada`: el cuerpo normativo aparece en los 10 pasajes entregados
  (así cuenta el evaluador). `articulo_en_pasajes`: además el artículo. `patrones`: regex sobre texto en
  minúsculas y sin tildes, para resaltar en la interfaz.
- `pasajes` (extensión del contrato): los mismos `answer.pasajes_recuperados`, con `norma` y `articulo`
  (que `to_submission()` no trae) y los índices de `normas_citadas` cuyo cuerpo aparece en cada pasaje.

## Pruebas

`pytest tests/test_api.py`: pipeline falso, sin GPU, índice ni Ollama. Para inyectarlo:
`create_app(cfg, pipeline=objeto_con_run)`.
