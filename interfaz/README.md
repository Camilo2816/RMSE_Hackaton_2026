# interfaz/

Front del sistema, inspirado en la identidad visual de Software Colombia
(patrocinador). Consume `POST /preguntar` de `src/api` (contrato en
`docs/CONTRATOS.md`, sección 8). No requiere despliegue público: basta con que
corra en el equipo del grupo durante la verificación en vivo.

Rúbrica (10 puntos):

| Criterio | Pts | Dónde |
|---|---:|---|
| Consulta de extremo a extremo desde la interfaz | 4 | formulario → `POST /preguntar` → respuesta por formato |
| Visualización de los pasajes recuperados y de las normas citadas en cada respuesta | 3 | chips de normas (respaldada / sin respaldo) y los 10 pasajes con resaltado |
| Aplicación de la identidad visual de Software Colombia | 3 | paleta y tipografía de software-colombia.com (abajo) |

## Arrancar

```bash
python -m src.api --config configs/agentic.yaml --port 8000
```

y abrir `http://127.0.0.1:8000/`. La API sirve estos archivos: no hay build ni
dependencias de front (HTML + CSS + JS vanilla). Detalles de la API en `src/api/README.md`.

## Qué muestra

- **Formulario:** pregunta, formato (semiabierta, selección múltiple, abierta) y opciones A–D solo en
  selección múltiple. Tres ejemplos precargados de `data/sample_50.jsonl` (ids 51, 79 y 513, uno por formato).
- **Carga:** contador de segundos; pasados 10 s avisa que la primera consulta en frío puede tardar más de un minuto.
- **Respuesta según formato:** opción elegida + justificación + descarte (MC); respuesta, referencia legal y
  palabras clave (semiabierta); marco normativo, análisis, jurisprudencia y conclusión (abierta). Aviso si hubo abstención.
- **Normas citadas:** chips verdes "respaldada" / rojos "sin respaldo" (ícono + texto, no solo color). Clic lleva al pasaje.
- **Pasajes recuperados:** los 10 entregados, con norma + artículo, score (barra y valor), texto plegable y
  las normas citadas **resaltadas** dentro del texto (cuerpo normativo en todos; el artículo, en los pasajes de esa norma).
  Los pasajes que contienen una norma citada se marcan "Citado" y se abren solos.
- **Traza:** latencia por etapa (`trace.timings`) y total, subconsultas, iteraciones, veredictos, citas eliminadas.

## Identidad visual

Fuente: hoja de estilos del sitio oficial, https://software-colombia.com/ (tema WordPress "Essentials",
consultado el 30/09/2026), variables CSS y colores más usados:

| Token (`estilos.css`) | Valor | Origen en el sitio |
|---|---|---|
| `--sc-turquesa` | `#09acc4` | `--text-primary` (color primario, el más usado) |
| `--sc-turquesa-hover` | `#0390a5` | tono hover/oscuro del primario |
| `--sc-naranja` | `#ff993b` | `--text-secondary` (acento) |
| `--fondo` | `#f3f3f3` | fondo de secciones |
| `--tinta`, `--tinta-suave` | `#212529`, `#495057` | textos (Bootstrap del tema) |
| Tipografía títulos | Montserrat 500–700 | `--pix-heading-font` / `--pix-body-font` |
| Tipografía texto | Roboto 400 | cargada por el slider del sitio junto a Montserrat |

Ambas fuentes se cargan de Google Fonts (licencia OFL); sin conexión caen a Segoe UI / system-ui.

**Contraste AA.** El turquesa `#09acc4` sobre blanco da 2,7:1 y el naranja 2,1:1, así que no se usan para
texto sobre blanco: el turquesa va en bordes (el filete inferior de la barra), barras de score y detalles; botones y
enlaces usan variantes oscurecidas del mismo tono (`#007585` 5,4:1 y `#006d7c` 6,0:1 con blanco); el naranja va
como acento de bordes/resaltado, con texto `#8a4300` (6,6:1 sobre `#fff1e3`). Chips: verde `#1e6b3a` sobre
`#e8f6ee` (5,9:1) y rojo `#b3261e` sobre `#fdecea` (5,7:1). Foco visible con contorno naranja; respeta
`prefers-reduced-motion`.

### Logotipo

El encabezado muestra el logotipo oficial desde `interfaz/assets/logo-software-colombia.png` (cubo isométrico
turquesa, "SOFTWARE COLOMBIA" y "eLogic Solutions SC"), a 56 px de alto sobre la barra blanca, porque el
logotipo trae texto negro sobre fondo blanco. Si el archivo falta, el `onerror` del `<img>` añade la clase
`marca--sin-logo` y se ve el marcador "SC" con el nombre en texto: la página nunca muestra una imagen rota.
