/* Utilidades de interfaz: constructor de DOM, llamadas a la API, avisos y pestañas. */
const $ = (s, r = document) => r.querySelector(s);

function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === 'class') el.className = v;
    else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
    else if (k === 'value') el.value = v;
    else if (v === true) el.setAttribute(k, '');
    else el.setAttribute(k, v);
  }
  const add = (c) => {
    if (c == null || c === false) return;
    if (Array.isArray(c)) c.forEach(add);
    else el.append(c.nodeType ? c : document.createTextNode(String(c)));
  };
  kids.forEach(add);
  return el;
}

const SES = {
  get() { try { return JSON.parse(sessionStorage.getItem('ses') || 'null'); } catch { return null; } },
  set(v) { try { sessionStorage.setItem('ses', JSON.stringify(v)); } catch {} },
  clear() { try { sessionStorage.removeItem('ses'); } catch {} },
};

async function api(path, { method = 'GET', body } = {}) {
  const s = SES.get();
  const r = await fetch(path, {
    method,
    headers: { 'Content-Type': 'application/json', ...(s ? { 'X-Token': s.token } : {}) },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  let data = null;
  try { data = await r.json(); } catch {}
  if (!r.ok) {
    if (r.status === 401 && s) { SES.clear(); location.reload(); }
    const d = data && data.detail;
    const msg = typeof d === 'string' ? d : Array.isArray(d) ? d.map(x => x.msg).join('. ') : `Error ${r.status}`;
    throw new Error(msg);
  }
  return data;
}

function toast(msg, tipo = 'ok') {
  const t = h('div', { class: 'toast ' + tipo, role: 'status' }, msg);
  $('#toasts').append(t);
  setTimeout(() => t.remove(), tipo === 'error' ? 7000 : 3200);
}

/* Ejecuta una acción mostrando errores como aviso; devuelve undefined si falló. */
async function intentar(fn, ok) {
  try { const r = await fn(); if (ok) toast(ok); return r; }
  catch (e) { toast(e.message, 'error'); }
}

function tabs(items, activa, onChange, clase = '') {
  return h('div', { class: 'tabs ' + clase, role: 'tablist' }, items.map(([id, label]) =>
    h('button', { class: 'tab' + (id === activa ? ' on' : ''), role: 'tab', 'aria-selected': id === activa, onclick: () => onChange(id) }, label)));
}

function tabla(cols, filas, vacio = 'Sin datos.') {
  if (!filas.length) return h('p', { class: 'vacio' }, vacio);
  return h('div', { class: 'tabla-wrap' }, h('table', {},
    h('thead', {}, h('tr', {}, cols.map(c => h('th', { class: c.num ? 'num' : '' }, c.t)))),
    h('tbody', {}, filas.map(f => h('tr', {}, cols.map(c => h('td', { class: c.num ? 'num' : '' }, c.f(f))))))));
}

const fmt = (n, d = 2) => n == null ? '—' : Number(n).toLocaleString('es-CO', { maximumFractionDigits: d, minimumFractionDigits: d });
const fmtMs = (n) => n == null ? '—' : n < 10 ? fmt(n, 2) : n < 100 ? fmt(n, 1) : fmt(n, 0);
const pill = (txt, clase = '') => h('span', { class: 'pill ' + clase }, txt);

function modal(titulo, cuerpo, { ancho = 720 } = {}) {
  const cerrar = () => { fondo.remove(); document.removeEventListener('keydown', esc); };
  const esc = (e) => { if (e.key === 'Escape') cerrar(); };
  const fondo = h('div', { class: 'modal-fondo', onclick: (e) => { if (e.target === fondo) cerrar(); } },
    h('div', { class: 'modal', style: `max-width:${ancho}px`, role: 'dialog', 'aria-label': titulo },
      h('div', { class: 'modal-cab' }, h('h3', {}, titulo), h('button', { class: 'ghost', onclick: cerrar, 'aria-label': 'Cerrar' }, '✕')),
      h('div', { class: 'modal-cuerpo' }, cuerpo)));
  document.addEventListener('keydown', esc);
  document.body.append(fondo);
  return cerrar;
}

function code(texto) { return h('pre', { class: 'code' }, h('code', {}, texto.trim())); }

/* Grafo interactivo compartido (portal del estudiante y explorador del administrador). */
const COLOR_NODO = { Estudiante: '#172033', Curso: '#0B8A83', Area: '#F2B705', Programa: '#3F51B5', Docente: '#6C7A91', Facultad: '#8d99ae', Sede: '#8d99ae' };

function crearRed(caja, nodos, aristas, { onDoble } = {}) {
  if (typeof vis === 'undefined') { caja.replaceChildren(h('p', { class: 'vacio', style: 'padding:1rem' }, 'No se pudo cargar la librería del grafo.')); return null; }
  const claro = (t) => t === 'Estudiante' || t === 'Programa' || t === 'Curso';
  const dn = new vis.DataSet(), de = new vis.DataSet();
  const poner = (ns, es) => {
    ns.forEach(n => { if (!dn.get(n.id)) dn.add({ id: n.id, label: String(n.nombre || n.id), shape: 'box', margin: 8,
      color: { background: COLOR_NODO[n.tipo] || '#9aa5b8', border: '#172033' }, font: { color: claro(n.tipo) ? '#fff' : '#172033', face: 'Schibsted Grotesk' },
      title: `${n.tipo}\n` + Object.entries(n.props || {}).map(([k, v]) => `${k}: ${v}`).join('\n') }); });
    es.forEach(a => { if (!de.get(a.id)) de.add({ id: a.id, from: a.de, to: a.a, arrows: 'to', label: aristas.length <= 40 ? a.tipo + (a.props && a.props.estado ? ` · ${a.props.estado}` : '') : undefined,
      title: a.tipo + ' ' + JSON.stringify(a.props || {}),
      font: { size: 10, align: 'middle', strokeWidth: 3 }, color: { color: a.tipo === 'SIMILAR_A' ? '#c3cad8' : '#9aa5b8' }, dashes: a.tipo === 'SIMILAR_A', smooth: { type: 'dynamic' } }); });
  };
  poner(nodos, aristas);
  const net = new vis.Network(caja, { nodes: dn, edges: de }, { physics: { stabilization: { iterations: 150 }, barnesHut: { springLength: 130 } }, interaction: { hover: true } });
  net.once('stabilizationIterationsDone', () => net.fit({ animation: false }));
  if (onDoble) net.on('doubleClick', ev => { if (ev.nodes.length) onDoble(ev.nodes[0], poner); });
  return { net, poner, nodos: dn, aristas: de };
}
