// Interfaz de consulta: POST /preguntar (docs/CONTRATOS.md §8). Sin dependencias ni build.
"use strict";

// Ejemplos tomados de data/sample_50.jsonl (ids 51, 79 y 513): solo los campos de entrada.
const EJEMPLOS = [
  {
    etiqueta: "Selección múltiple",
    formato: "multiple_choice",
    pregunta: "¿En cuál de los siguientes casos procede la acción judicial de grupo?",
    opciones: {
      A: "Cuando un grupo de personas busca proteger derechos fundamentales individuales de aplicación inmediata.",
      B: "Cuando un grupo de ciudadanos busca defender el interés colectivo ambiental o del espacio público.",
      C: "Cuando un conjunto de personas resulta afectado por un mismo hecho que les causa perjuicios individuales derivados de una causa común.",
      D: "Cuando se pretende declarar la inconstitucionalidad de una norma con fuerza de ley.",
    },
  },
  {
    etiqueta: "Semiabierta",
    formato: "semi_open",
    pregunta: "¿Existe alguna norma en el ordenamiento jurídico colombiano que regule el acoso laboral?",
  },
  {
    etiqueta: "Abierta",
    formato: "open_ended",
    pregunta: "¿Cómo debería actuar una empresa si esta decide ingresar de manera legal su producto a un país para generar una venta y el consumidor final decide revender dicho producto? ¿Es posible que la empresa prohíba la venta por segunda vez?",
  },
];

const ETAPAS = {
  lookup: "Búsqueda directa", retrieval: "Recuperación", fusion: "Fusión", rerank: "Reranking",
  planning: "Planeación", generation: "Generación", verification: "Verificación",
};
const LETRAS = ["A", "B", "C", "D"];

const $ = (sel) => document.querySelector(sel);
const form = $("#formulario");
const estado = { consulta: null };

function el(tag, attrs = {}, ...hijos) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") n.className = v;
    else if (k === "text") n.textContent = v;
    else n.setAttribute(k, v);
  }
  for (const h of hijos) if (h != null) n.append(h);
  return n;
}

function formato() {
  return form.querySelector('input[name="formato"]:checked').value;
}

function actualizarOpciones() {
  const mc = formato() === "multiple_choice";
  $("#opciones").hidden = !mc;
  for (const l of LETRAS) form.elements["op-" + l].required = mc;
}

function cargarEjemplo(ej) {
  form.elements.pregunta.value = ej.pregunta;
  form.querySelector(`input[name="formato"][value="${ej.formato}"]`).checked = true;
  for (const l of LETRAS) form.elements["op-" + l].value = ej.opciones ? ej.opciones[l] : "";
  actualizarOpciones();
  ocultarError();
  form.elements.pregunta.focus();
}

function mostrarError(msg) {
  const e = $("#error");
  e.textContent = msg;
  e.hidden = false;
}

function ocultarError() {
  $("#error").hidden = true;
}

function mensajeDeError(status, cuerpo) {
  const d = cuerpo && cuerpo.detail;
  if (Array.isArray(d)) {
    return "Revise la consulta: " + d.map((x) => (x.msg || "").replace(/^Value error, /, "")).join("; ");
  }
  if (typeof d === "string") return d;
  return `El servidor respondió ${status}.`;
}

// --- Envío -----------------------------------------------------------------

let reloj = null;

function iniciarCarga() {
  const t0 = performance.now();
  $("#enviar").disabled = true;
  $("#cargando").hidden = false;
  const texto = $("#cargando-texto");
  const pintar = () => {
    const s = Math.floor((performance.now() - t0) / 1000);
    texto.textContent = s < 10
      ? `Consultando… ${s} s`
      : `Consultando… ${s} s. La primera consulta tras arrancar puede tardar más de un minuto (carga de modelos).`;
  };
  pintar();
  reloj = setInterval(pintar, 1000);
}

function terminarCarga() {
  clearInterval(reloj);
  $("#enviar").disabled = false;
  $("#cargando").hidden = true;
}

async function enviar(ev) {
  ev.preventDefault();
  ocultarError();
  const pregunta = form.elements.pregunta.value.trim();
  const fmt = formato();
  if (!pregunta) return mostrarError("Escriba una pregunta.");
  let opciones = null;
  if (fmt === "multiple_choice") {
    opciones = {};
    for (const l of LETRAS) opciones[l] = form.elements["op-" + l].value.trim();
    const faltan = LETRAS.filter((l) => !opciones[l]);
    if (faltan.length) return mostrarError(`Complete las opciones ${faltan.join(", ")}.`);
  }
  iniciarCarga();
  try {
    const r = await fetch("preguntar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pregunta, formato: fmt, opciones }),
    });
    const cuerpo = await r.json().catch(() => null);
    if (!r.ok) throw new Error(mensajeDeError(r.status, cuerpo));
    estado.consulta = { pregunta, formato: fmt, opciones };
    pintarResultado(cuerpo);
  } catch (e) {
    mostrarError(e instanceof TypeError ? "No se pudo contactar el servidor. ¿Está corriendo python -m src.api?" : e.message);
  } finally {
    terminarCarga();
  }
}

// --- Resaltado -------------------------------------------------------------

// Minúsculas y sin tildes, como citations.norm, con el mapa de posiciones al texto original.
function normalizar(texto) {
  let out = "";
  const mapa = [];
  for (let i = 0; i < texto.length; i++) {
    const c = texto[i].normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
    for (let k = 0; k < c.length; k++) {
      out += c[k];
      mapa.push(i);
    }
  }
  mapa.push(texto.length);
  return { out, mapa };
}

function rangos(texto, patrones) {
  const { out, mapa } = normalizar(texto);
  const rs = [];
  for (const p of patrones) {
    let re;
    try { re = new RegExp(p, "g"); } catch { continue; }
    for (const m of out.matchAll(re)) {
      if (!m[0]) continue;
      rs.push([mapa[m.index], mapa[m.index + m[0].length - 1] + 1]);
    }
  }
  rs.sort((a, b) => a[0] - b[0]);
  const unidos = [];
  for (const r of rs) {
    const u = unidos[unidos.length - 1];
    if (u && r[0] <= u[1]) u[1] = Math.max(u[1], r[1]);
    else unidos.push([...r]);
  }
  return unidos;
}

function textoResaltado(texto, patrones) {
  const frag = document.createDocumentFragment();
  let i = 0;
  for (const [a, b] of rangos(texto, patrones)) {
    if (a > i) frag.append(texto.slice(i, a));
    frag.append(el("mark", { text: texto.slice(a, b) }));
    i = b;
  }
  frag.append(texto.slice(i));
  return frag;
}

// --- Pintado ---------------------------------------------------------------

function parrafo(t) {
  return t ? el("p", { text: t }) : el("p", { class: "vacio", text: "(vacío)" });
}

function bloque(titulo, contenido) {
  return el("section", { class: "bloque" }, el("h3", { text: titulo }), contenido);
}

function pintarRespuesta(a) {
  const c = $("#respuesta-cuerpo");
  c.replaceChildren();
  if (a.formato === "multiple_choice") {
    const letra = a.respuesta_correcta || "—";
    const ops = (estado.consulta && estado.consulta.opciones) || {};
    c.append(el("div", { class: "eleccion" },
      el("span", { class: "eleccion__letra", "aria-label": `Opción ${letra}`, text: letra }),
      el("span", { class: "eleccion__texto", text: ops[letra] || "" })));
    c.append(bloque("Justificación", parrafo(a.justificacion)));
    const lista = el("ul", { class: "descartes" });
    for (const [l, razon] of Object.entries(a.descarte_opciones || {}).sort()) {
      lista.append(el("li", {}, el("b", { text: l }), el("span", { text: razon })));
    }
    if (lista.children.length) c.append(bloque("Descarte de las demás opciones", lista));
  } else if (a.formato === "semi_open") {
    c.append(bloque("Respuesta", parrafo(a.respuesta)));
    c.append(bloque("Referencia legal", parrafo(a.referencia_legal)));
    const chips = el("ul", { class: "chips chips--palabras" });
    for (const p of a.palabras_clave || []) chips.append(el("li", { class: "chip", text: p }));
    if (chips.children.length) c.append(bloque("Palabras clave", chips));
  } else {
    c.append(bloque("Marco normativo", parrafo(a.marco_normativo)));
    c.append(bloque("Análisis", parrafo(a.analisis)));
    c.append(bloque("Jurisprudencia", parrafo(a.jurisprudencia)));
    c.append(bloque("Conclusión", parrafo(a.conclusion)));
  }
}

function pintarNormas(normas, pasajes) {
  const ul = $("#normas");
  ul.replaceChildren();
  if (!normas.length) {
    ul.append(el("li", { class: "vacio", text: "La respuesta no cita normas." }));
    return;
  }
  normas.forEach((n, i) => {
    const ok = n.respaldada;
    const destino = pasajes.findIndex((p) => p.normas_citadas.includes(i));
    const chip = el("button", {
      type: "button",
      class: `chip ${ok ? "chip--ok" : "chip--mal"}${destino < 0 ? " chip--estatico" : ""}`,
      title: ok ? "Aparece en los pasajes entregados" : "No aparece en los pasajes entregados",
    },
    el("span", { class: "chip__icono", "aria-hidden": "true", text: ok ? "✓" : "!" }),
    el("span", { text: n.cita }),
    el("span", { class: "chip__estado", text: ok ? "respaldada" : "sin respaldo" }));
    if (destino >= 0) chip.addEventListener("click", () => enfocarPasaje(destino));
    else chip.setAttribute("aria-disabled", "true");
    ul.append(el("li", {}, chip));
  });
}

function enfocarPasaje(i) {
  const li = $("#pasajes").children[i];
  if (!li) return;
  li.querySelector("details").open = true;
  document.querySelectorAll(".pasaje--foco").forEach((x) => x.classList.remove("pasaje--foco"));
  li.classList.add("pasaje--foco");
  li.scrollIntoView({ behavior: "smooth", block: "start" });
  li.querySelector("summary").focus({ preventScroll: true });
}

function pintarPasajes(pasajes, normas) {
  const ol = $("#pasajes");
  ol.replaceChildren();
  if (!pasajes.length) {
    ol.append(el("li", { class: "vacio", text: "No se recuperaron pasajes." }));
    return;
  }
  const maxScore = Math.max(...pasajes.map((p) => p.score), 1e-9);
  const tpl = $("#tpl-pasaje");
  pasajes.forEach((p, i) => {
    const li = tpl.content.firstElementChild.cloneNode(true);
    const citado = p.normas_citadas.length > 0;
    li.classList.toggle("pasaje--citado", citado);
    li.querySelector(".pasaje__rango").textContent = `#${i + 1}`;
    li.querySelector(".pasaje__titulo").textContent = p.articulo ? `${p.norma}, art. ${p.articulo}` : p.norma;
    li.querySelector(".pasaje__citado").hidden = !citado;
    li.querySelector(".pasaje__valor").textContent = p.score.toFixed(3);
    li.querySelector(".pasaje__barra span").style.width = `${Math.max(0, Math.min(1, p.score / maxScore)) * 100}%`;
    li.querySelector(".pasaje__score").setAttribute("aria-label", `score ${p.score.toFixed(3)}`);
    const meta = [p.doc_id, p.fuente_query ? `vía: ${p.fuente_query}` : null].filter(Boolean).join(" · ");
    li.querySelector(".pasaje__meta").textContent = meta;
    const patrones = [];
    for (const k of p.normas_citadas) {
      const n = normas[k];
      patrones.push(...n.patrones.cuerpo);
      if (n.patrones.articulo) patrones.push(n.patrones.articulo);
    }
    // Normas citadas que no se detectaron como cuerpo del pasaje también se resaltan si aparecen.
    normas.forEach((n, k) => { if (!p.normas_citadas.includes(k)) patrones.push(...n.patrones.cuerpo); });
    li.querySelector(".pasaje__texto").append(textoResaltado(p.texto || "", patrones));
    li.querySelector("details").open = citado;
    ol.append(li);
  });
}

function segundos(s) {
  return s >= 10 ? `${s.toFixed(1)} s` : s >= 1 ? `${s.toFixed(2)} s` : `${Math.round(s * 1000)} ms`;
}

function pintarTraza(trace, answer) {
  const dl = $("#tiempos");
  dl.replaceChildren();
  const tiempos = Object.entries(trace.timings || {});
  const max = Math.max(...tiempos.map(([, v]) => v), 1e-9);
  for (const [k, v] of tiempos) {
    const barra = el("span", { class: "tiempos__barra", "aria-hidden": "true" }, el("span"));
    barra.firstChild.style.width = `${(v / max) * 100}%`;
    dl.append(el("div", {}, el("dt", { text: ETAPAS[k] || k }), barra, el("dd", { text: segundos(v) })));
  }
  if (answer.latencia_ms != null) {
    dl.append(el("div", { class: "tiempos__total" },
      el("dt", { text: "Total" }), el("span"), el("dd", { text: segundos(answer.latencia_ms / 1000) })));
  }
  if (!dl.children.length) dl.append(el("p", { class: "vacio", text: "Sin tiempos registrados." }));

  const ol = $("#subconsultas");
  ol.replaceChildren();
  for (const q of trace.subqueries || []) ol.append(el("li", { text: q }));
  if (!ol.children.length) ol.append(el("li", { class: "vacio", text: "Sin subconsultas." }));

  const partes = [`${trace.iterations || 0} iteración(es)`];
  if ((trace.verdicts || []).length) partes.push(`veredictos: ${trace.verdicts.join(", ")}`);
  if ((trace.dropped_citations || []).length) partes.push(`${trace.dropped_citations.length} cita(s) sin respaldo eliminadas`);
  if (trace.fallback) partes.push(`respuesta de respaldo (${trace.fallback})`);
  if (trace.abstention_reason) partes.push(`abstención: ${trace.abstention_reason}`);
  $("#verificacion").textContent = partes.join(" · ");
}

function pintarResultado(r) {
  const a = r.answer;
  $("#abstencion").hidden = !a.abstencion;
  $("#latencia").textContent = a.latencia_ms != null ? `Respondida en ${segundos(a.latencia_ms / 1000)}` : "";
  pintarRespuesta(a);
  pintarNormas(r.normas_citadas || [], r.pasajes || []);
  pintarPasajes(r.pasajes || [], r.normas_citadas || []);
  pintarTraza(r.trace || {}, a);
  $("#resultado").hidden = false;
  const h = $("#titulo-respuesta");
  h.scrollIntoView({ behavior: "smooth", block: "start" });
  h.focus({ preventScroll: true });
}

// --- Arranque --------------------------------------------------------------

async function salud() {
  const s = $("#salud");
  try {
    const r = await fetch("salud");
    const d = await r.json();
    s.textContent = `Servicio listo · ${d.pipeline || "pipeline"}`;
    s.className = "salud salud--ok";
  } catch {
    s.textContent = "Servidor no disponible";
    s.className = "salud salud--mal";
  }
}

for (const ej of EJEMPLOS) {
  const b = el("button", { type: "button", class: "boton boton--ejemplo", text: ej.etiqueta });
  b.addEventListener("click", () => cargarEjemplo(ej));
  $("#ejemplos").append(b);
}
form.addEventListener("change", (e) => { if (e.target.name === "formato") actualizarOpciones(); });
form.addEventListener("submit", enviar);
$("#abrir-todos").addEventListener("click", () => document.querySelectorAll("#pasajes details").forEach((d) => { d.open = true; }));
$("#cerrar-todos").addEventListener("click", () => document.querySelectorAll("#pasajes details").forEach((d) => { d.open = false; }));
actualizarOpciones();
salud();
