/* Explorador del grafo: vista general de Neo4j y panel de Cypher de solo lectura. */
const EJEMPLOS_CYPHER = [
  ['Cursos y sus áreas', "MATCH (c:Curso)-[t:TRATA_DE]->(a:Area)\nRETURN c, t, a\nLIMIT 40"],
  ['Cadena de prerrequisitos de un curso', "MATCH p = (c:Curso {codigo: 'C306'})-[:REQUIERE*1..5]->(:Curso)\nRETURN p"],
  ['Lo que aprobó un estudiante', "MATCH (e:Estudiante {id: 'E1'})-[h:HA_CURSADO {estado: 'APROBADO'}]->(c:Curso)\nRETURN e, h, c"],
  ['Cursos similares a uno', "MATCH (c:Curso {codigo: 'C101'})-[s:SIMILAR_A]->(o:Curso)\nRETURN c, s, o\nORDER BY s.peso DESC"],
  ['Cuántos nodos hay por etiqueta', "MATCH (n)\nUNWIND labels(n) AS etiqueta\nRETURN etiqueta, count(*) AS total\nORDER BY total DESC"],
  ['Cursos más aprobados', "MATCH (:Estudiante)-[h:HA_CURSADO {estado: 'APROBADO'}]->(c:Curso)\nRETURN c.codigo AS codigo, c.nombre AS nombre, count(h) AS aprobados\nORDER BY aprobados DESC\nLIMIT 10"],
];

function celda(v) {
  if (v && typeof v === 'object' && !Array.isArray(v)) {
    if (v._tipo === 'nodo') return `(${v.etiquetas.join(':')} ${JSON.stringify(v.props)})`;
    if (v._tipo === 'relacion') return `[:${v.tipo} ${JSON.stringify(v.props)}]`;
    if (v._tipo === 'ruta') return `ruta de ${v.nodos.length} nodos`;
    return JSON.stringify(v);
  }
  return Array.isArray(v) ? JSON.stringify(v) : String(v ?? '');
}

async function vistaGrafo(cont) {
  const tipos = (await intentar(() => api('/api/admin/grafo?limite=10'))) || { tipos: [] };
  const caja = h('div', { id: 'red', style: 'height:560px' });
  const info = h('p', { class: 'dato-et' });
  const limite = h('input', { type: 'number', min: 10, max: 500, value: 150, style: 'width:5.5rem' });
  const volumen = h('input', { type: 'checkbox' });
  const checks = tipos.tipos.map(t => ({ t, el: h('input', { type: 'checkbox', checked: t !== 'SIMILAR_A' }) }));
  let red = null;

  const seleccion = () => checks.filter(c => c.el.checked).map(c => c.t).join(',');
  const dibujar = (nodos, aristas, nota) => {
    red = crearRed(caja, nodos, aristas, { onDoble: async (id, poner) => {
      const v = await intentar(() => api(`/api/admin/grafo/vecindad?eid=${encodeURIComponent(id)}&tipos=${encodeURIComponent(seleccion() || '')}`));
      if (v) { poner(v.nodos, v.aristas); toast(`${v.aristas.length} conexiones del nodo`); }
    } });
    info.textContent = `${nodos.length} nodos y ${aristas.length} relaciones. ${nota || ''}`;
  };
  const cargar = async () => {
    const g = await intentar(() => api(`/api/admin/grafo?limite=${limite.value}&todos=${volumen.checked}&tipos=${encodeURIComponent(seleccion())}`));
    if (g) dibujar(g.nodos, g.aristas, 'Doble clic en un nodo para traer sus vecinos.');
  };

  const ta = h('textarea', { rows: 6, spellcheck: false, class: 'code', style: 'width:100%;resize:vertical;color:#D6E2F5' }, EJEMPLOS_CYPHER[0][1]);
  const sel = h('select', {}, EJEMPLOS_CYPHER.map(([t], i) => h('option', { value: i }, t)));
  sel.addEventListener('change', () => { ta.value = EJEMPLOS_CYPHER[sel.value][1]; });
  const resultado = h('div', {});
  const ejecutar = async () => {
    resultado.replaceChildren(h('p', { class: 'vacio' }, 'Ejecutando…'));
    const r = await intentar(() => api('/api/admin/cypher', { method: 'POST', body: { query: ta.value } }));
    if (!r) { resultado.replaceChildren(); return; }
    const filas = r.filas.map(f => Object.fromEntries(r.columnas.map((c, i) => [c, f[i]])));
    resultado.replaceChildren(
      h('p', { class: 'dato-et' }, `${r.filas.length} fila(s) en ${fmtMs(r.ms)} ms` + (r.truncado ? ' (se muestran las primeras 200)' : '') +
        (r.grafo.nodos.length ? ` · ${r.grafo.nodos.length} nodos dibujados arriba` : '')),
      tabla(r.columnas.map(c => ({ t: c, f: x => celda(x[c]) })), filas, 'La consulta no devolvió filas.'));
    if (r.grafo.nodos.length) { dibujar(r.grafo.nodos, r.grafo.aristas, 'Resultado de tu consulta.'); caja.scrollIntoView({ behavior: 'smooth', block: 'nearest' }); }
  };
  ta.addEventListener('keydown', e => { if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') ejecutar(); });

  cont.replaceChildren(
    h('div', { class: 'caja' }, h('h2', {}, 'Explorador del grafo'),
      h('p', { class: 'dato-et' }, 'Mira el grafo de Neo4j tal como está guardado. Arrastra nodos, pasa el cursor para ver sus propiedades y haz doble clic para expandir.'),
      h('div', { class: 'ctl', style: 'margin-top:.6rem' }, h('label', {}, 'Máx. relaciones', limite),
        h('label', { style: 'flex-direction:row;display:flex;align-items:center;gap:.4rem' }, volumen, 'Incluir datos de volumen'),
        h('button', { onclick: cargar }, 'Cargar grafo')),
      h('div', { class: 'acciones', style: 'margin-bottom:.4rem' }, checks.map(c => h('label', { style: 'flex-direction:row;display:flex;align-items:center;gap:.3rem;font-weight:500' }, c.el, c.t))),
      info),
    h('div', { style: 'margin-top:1rem' }, caja),
    h('div', { class: 'caja', style: 'margin-top:1rem' }, h('h3', {}, 'Consulta en Cypher (solo lectura)'),
      h('p', { class: 'dato-et' }, 'Si devuelves nodos, relaciones o rutas se dibujan en el grafo. No se permiten CREATE, MERGE, DELETE, SET ni REMOVE, y Neo4j ejecuta la consulta en una transacción de solo lectura. Ctrl+Enter para ejecutar.'),
      h('div', { class: 'fila', style: 'margin:.5rem 0' }, h('label', { style: 'flex:1 1 18rem' }, 'Ejemplos', sel)), ta,
      h('div', { class: 'acciones', style: 'margin:.6rem 0' }, h('button', { onclick: ejecutar }, 'Ejecutar consulta')), resultado));
  cargar();
}
