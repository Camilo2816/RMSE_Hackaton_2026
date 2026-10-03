# src/common

**Responsabilidad:** Contratos (`types.py`), configuración (`config.py`), medición de tiempos (`timing.py`), rutas, E/S, logging y alias de normas.
**Entradas:** `configs/base.yaml` + `configs/<pipeline>.yaml`, `configs/alias_normas.yaml`.
**Salidas:** `Question`, `Passage`, `Answer`, `Verdict`, `Trace`; config fusionada (dict).
