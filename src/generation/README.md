# src/generation

**Responsabilidad:** Cliente vLLM (temperatura 0, guided JSON, thinking configurable) y generación de la respuesta por formato.
**Entradas:** `Question` + ≤ 10 `Passage`; prompts en `prompts/planner/` y `prompts/answer/`.
**Salidas:** `Answer` con las claves oficiales del formato.
