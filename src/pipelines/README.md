# src/pipelines

**Responsabilidad:** Componer las etapas: `baseline` (una pasada) y `agentic` (subconsultas + re-planeo acotado por `max_iter`). `registry.build_pipeline(cfg)` elige según la config.
**Entradas:** `Question`, config.
**Salidas:** `(Answer, Trace)`.
