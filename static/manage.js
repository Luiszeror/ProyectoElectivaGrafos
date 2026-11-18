/* Pestaña de gestión: docentes, cursos, catálogos y notas. Todo se escribe en Neo4j. */
let subGestion = 'docentes';

function vistaGestion(cont) {
  const cuerpo = h('div', {});
  const pintar = () => {
    cont.replaceChildren(
      tabs([['docentes', 'Docentes'], ['cursos', 'Cursos'], ['catalogos', 'Programas, sedes y áreas'], ['notas', 'Notas']], subGestion, (s) => { subGestion = s; pintar(); }, 'sub'),
      cuerpo);
    ({ docentes: gDocentes, cursos: gCursos, catalogos: gCatalogos, notas: gNotas })[subGestion](cuerpo);
  };
  pintar();
}

const confirmar = (msg) => window.confirm(msg);

/* Formulario simple de un campo (nombre) en un modal. */
function formNombre(titulo, inicial, onGuardar) {
  const inp = h('input', { value: inicial || '', maxlength: 60, style: 'width:100%' });
  const cerrar = modal(titulo, h('div', {}, h('label', {}, 'Nombre', inp),
    h('div', { class: 'acciones', style: 'margin-top:1rem' },
      h('button', { onclick: async () => { if (await onGuardar(inp.value)) cerrar(); } }, 'Guardar'), h('button', { class: 'sec', onclick: () => cerrar() }, 'Cancelar'))), { ancho: 440 });
  inp.focus();
}

/* ---------------------------------------------------------------- docentes */
async function gDocentes(cont) {
  const r = await intentar(() => api('/api/admin/docentes'));
  const cursos = (await intentar(() => api('/api/admin/cursos')) || { cursos: [] }).cursos;
  if (!r) return;
  const recargar = () => gDocentes(cont);
  cont.replaceChildren(h('div', { class: 'caja' },
    h('div', { class: 'fila', style: 'justify-content:space-between;align-items:center' }, h('h2', {}, 'Docentes'),
      h('button', { onclick: () => formNombre('Nuevo docente', '', async (n) => !!(await intentar(() => api('/api/admin/docentes', { method: 'POST', body: { nombre: n } }), 'Docente creado')) && (recargar(), true)) }, 'Crear docente')),
    h('p', { class: 'dato-et' }, `Asignaciones del periodo ${r.periodo}.`),
    tabla([
      { t: 'Código', f: d => d.id }, { t: 'Nombre', f: d => d.nombre },
      { t: `Cursos que dicta`, f: d => d.cursos.filter(c => c.periodo === r.periodo).map(c =>
          h('div', {}, `${c.nombre} (${c.curso}) · grupo ${c.grupo} `, h('button', { class: 'ghost small', title: 'Quitar asignación', onclick: async () => {
            if (await intentar(() => api(`/api/admin/docentes/${d.id}/desasignar`, { method: 'POST', body: { curso: c.curso, grupo: c.grupo } }), 'Asignación quitada')) recargar(); } }, 'Quitar'))) },
      { t: '', f: d => h('div', { class: 'acciones' },
          h('button', { class: 'sec small', onclick: () => asignar(d, cursos, recargar) }, 'Asignar curso'),
          h('button', { class: 'sec small', onclick: () => formNombre('Editar docente', d.nombre, async (n) => !!(await intentar(() => api(`/api/admin/docentes/${d.id}`, { method: 'PUT', body: { nombre: n } }), 'Docente actualizado')) && (recargar(), true)) }, 'Editar'),
          h('button', { class: 'sec small', onclick: async () => { if (confirmar(`¿Eliminar a ${d.nombre}? Se quitan sus asignaciones.`) && await intentar(() => api(`/api/admin/docentes/${d.id}`, { method: 'DELETE' }), 'Docente eliminado')) recargar(); } }, 'Eliminar')) },
    ], r.docentes, 'No hay docentes. Crea el primero.')));
}

function asignar(d, cursos, recargar) {
  const sel = h('select', {}, cursos.map(c => h('option', { value: c.codigo }, `${c.codigo} · ${c.nombre}`)));
  const grupo = h('input', { type: 'number', min: 1, max: 20, value: 1, style: 'width:5rem' });
  const cerrar = modal(`Asignar curso a ${d.nombre}`, h('div', {}, h('div', { class: 'fila' }, h('label', {}, 'Curso', sel), h('label', {}, 'Grupo', grupo)),
    h('div', { class: 'acciones', style: 'margin-top:1rem' }, h('button', { onclick: async () => {
      if (await intentar(() => api(`/api/admin/docentes/${d.id}/asignar`, { method: 'POST', body: { curso: sel.value, grupo: +grupo.value } }), 'Curso asignado')) { cerrar(); recargar(); } } }, 'Asignar'),
      h('button', { class: 'sec', onclick: () => cerrar() }, 'Cancelar'))), { ancho: 520 });
}

/* ---------------------------------------------------------------- cursos */
async function gCursos(cont) {
  const r = await intentar(() => api('/api/admin/cursos'));
  if (!r) return;
  const recargar = () => gCursos(cont);
  cont.replaceChildren(h('div', { class: 'caja' },
    h('div', { class: 'fila', style: 'justify-content:space-between;align-items:center' }, h('h2', {}, 'Cursos'), h('button', { onclick: () => formCurso(null, recargar) }, 'Crear curso')),
    h('p', { class: 'dato-et' }, 'Al guardar se recalculan las relaciones SIMILAR_A del curso. Sincroniza PostgreSQL después para que la comparación use lo mismo.'),
    tabla([
      { t: 'Curso', f: c => h('div', {}, h('b', {}, c.nombre), h('div', { class: 'dato-et' }, `${c.codigo} · ${c.tipo} · ${c.nivel}`)) },
      { t: 'Áreas', f: c => c.areas.map(a => a.nombre).join(', ') },
      { t: 'Requisitos', f: c => c.prerreq.map(q => `${q.nombre}${q.tipo === 'CORREQUISITO' ? ' (co)' : ''}`).join(', ') || '—' },
      { t: 'Programas', f: c => c.programas.map(p => p.nombre).join(', ') || '—' },
      { t: `Sedes y cupos`, f: c => c.sedes.map(s => `${s.nombre}: ${s.cupos}`).join(' · ') || 'No se ofrece' },
      { t: 'Docentes', f: c => c.docentes.map(d => d.nombre).join(', ') || '—' },
      { t: '', f: c => h('div', { class: 'acciones' }, h('button', { class: 'sec small', onclick: () => formCurso(c, recargar) }, 'Editar'),
          h('button', { class: 'sec small', onclick: async () => {
            if (!confirmar(`¿Eliminar ${c.nombre}?`)) return;
            try { await api(`/api/admin/cursos/${c.codigo}`, { method: 'DELETE' }); toast('Curso eliminado'); recargar(); }
            catch (e) { if (confirmar(e.message + '\n\n¿Eliminarlo de todos modos?') && await intentar(() => api(`/api/admin/cursos/${c.codigo}?forzar=true`, { method: 'DELETE' }), 'Curso eliminado')) recargar(); }
          } }, 'Eliminar')) },
    ], r.cursos)));
}

/* Lista de casillas con un campo extra opcional por fila. */
function casillas(opciones, elegidos, extra) {
  const filas = opciones.map(o => {
    const chk = h('input', { type: 'checkbox', checked: elegidos.has(o.id), 'aria-label': o.nombre });
    const ex = extra ? extra(o, elegidos.get(o.id)) : null;
    return { o, chk, ex, el: h('div', { class: 'chk-fila' }, chk, h('span', {}, o.nombre), ex ? ex.el : h('span')) };
  });
  return { el: h('div', { class: 'chk-lista' }, filas.map(f => f.el)),
    valor: () => filas.filter(f => f.chk.checked).map(f => ({ id: f.o.id, ...(f.ex ? f.ex.leer() : {}) })) };
}
const numInput = (v, min, max, w = '4.5rem', paso) => h('input', { type: 'number', min, max, step: paso, value: v, style: `width:${w}` });

async function formCurso(curso, recargar) {
  const [cat, docs, todos] = await Promise.all([api('/api/admin/catalogos'), api('/api/admin/docentes'), api('/api/admin/cursos')]).catch(e => { toast(e.message, 'error'); return []; });
  if (!cat) return;
  const nombre = h('input', { value: curso ? curso.nombre : '', maxlength: 80 });
  const codigo = h('input', { value: curso ? curso.codigo : '', placeholder: 'Automático (C…)', disabled: !!curso });
  const tipo = h('select', {}, ['OBLIGATORIO', 'ELECTIVO'].map(t => h('option', { selected: curso && curso.tipo === t }, t)));
  const nivel = h('select', {}, ['Básico', 'Intermedio', 'Avanzado'].map(t => h('option', { selected: curso && curso.nivel === t }, t)));
  const mapa = (arr, k = 'codigo') => new Map((arr || []).map(x => [x[k], x]));
  const aA = mapa(curso && curso.areas), aP = mapa(curso && curso.programas), aR = mapa(curso && curso.prerreq), aS = mapa(curso && curso.sedes), aD = mapa(curso && curso.docentes, 'id');

  const areas = casillas(cat.areas.map(a => ({ id: a.codigo, nombre: a.nombre })), aA, (o, v) => { const i = numInput(v ? v.peso : 1, 0.1, 1, '4.5rem', 0.1); return { el: i, leer: () => ({ peso: +i.value }) }; });
  const progs = casillas(cat.programas.map(p => ({ id: p.codigo, nombre: p.nombre })), aP, (o, v) => {
    const s = numInput(v ? v.semestre : '', 1, 12, '3.5rem'); s.placeholder = 'sem.'; const ob = h('input', { type: 'checkbox', checked: v && v.obligatorio, title: 'Obligatorio en este programa' });
    return { el: h('span', { class: 'nivel' }, s, ob, h('span', { class: 'dato-et' }, 'oblig.')), leer: () => ({ semestre: s.value ? +s.value : null, obligatorio: ob.checked }) }; });
  const reqs = casillas(todos.cursos.filter(c => !curso || c.codigo !== curso.codigo).map(c => ({ id: c.codigo, nombre: `${c.codigo} · ${c.nombre}` })), aR, (o, v) => {
    const t = h('select', {}, ['PRERREQUISITO', 'CORREQUISITO'].map(x => h('option', { selected: v && v.tipo === x }, x))); return { el: t, leer: () => ({ tipo: t.value }) }; });
  const sedes = casillas(cat.sedes.map(s => ({ id: s.codigo, nombre: s.nombre })), aS, (o, v) => { const i = numInput(v ? v.cupos : 30, 0, 1000, '5rem'); return { el: i, leer: () => ({ cupos: +i.value }) }; });
  const docs2 = casillas(docs.docentes.map(d => ({ id: d.id, nombre: d.nombre })), aD, (o, v) => { const i = numInput(v ? v.grupo : 1, 1, 20, '4rem'); return { el: i, leer: () => ({ grupo: +i.value }) }; });

  const cerrar = modal(curso ? `Editar ${curso.nombre}` : 'Crear curso', h('div', {},
    h('div', { class: 'form-grid' }, h('label', {}, 'Nombre', nombre), h('label', {}, 'Código', codigo), h('label', {}, 'Tipo', tipo), h('label', {}, 'Nivel', nivel)),
    h('div', { class: 'form-grid', style: 'margin-top:1rem' },
      h('div', {}, h('h4', {}, 'Áreas que trata (peso 0.1–1)'), areas.el), h('div', {}, h('h4', {}, 'Programas (semestre sugerido)'), progs.el),
      h('div', {}, h('h4', {}, 'Requisitos'), reqs.el), h('div', {}, h('h4', {}, `Sedes y cupos (${todos.periodo})`), sedes.el),
      h('div', {}, h('h4', {}, `Docentes (grupo)`), docs2.el)),
    h('div', { class: 'acciones', style: 'margin-top:1rem' }, h('button', { onclick: async () => {
      const body = { codigo: codigo.value.trim() || undefined, nombre: nombre.value, tipo: tipo.value, nivel: nivel.value,
        areas: areas.valor(), programas: progs.valor(), requisitos: reqs.valor(), sedes: sedes.valor(), docentes: docs2.valor() };
      const ok = await intentar(() => curso ? api(`/api/admin/cursos/${curso.codigo}`, { method: 'PUT', body }) : api('/api/admin/cursos', { method: 'POST', body }), curso ? 'Curso actualizado' : 'Curso creado');
      if (ok) { cerrar(); recargar(); } } }, 'Guardar curso'), h('button', { class: 'sec', onclick: () => cerrar() }, 'Cancelar'))), { ancho: 980 });
}

/* ---------------------------------------------------------------- catálogos */
let subCat = 'programas';
async function gCatalogos(cont) {
  const cat = await intentar(() => api('/api/admin/catalogos'));
  if (!cat) return;
  const recargar = () => gCatalogos(cont);
  const defs = { facultades: ['Facultades', 'facultad'], programas: ['Programas', 'programa'], sedes: ['Sedes', 'sede'], areas: ['Áreas', 'área'] };
  const [titulo, singular] = defs[subCat];
  const sedesDe = (p) => cat.programa_sedes.filter(x => x.programa === p).map(x => x.sede);
  const nombreDe = (lista, c) => (lista.find(x => x.codigo === c) || {}).nombre || c;
  const cols = [{ t: 'Código', f: x => x.codigo }, { t: 'Nombre', f: x => x.nombre }];
  if (subCat === 'programas') cols.push({ t: 'Facultad', f: x => x.facultad ? nombreDe(cat.facultades, x.facultad) : '—' }, { t: 'Sedes', f: x => sedesDe(x.codigo).map(s => nombreDe(cat.sedes, s)).join(', ') || '—' });
  cols.push({ t: '', f: x => h('div', { class: 'acciones' }, h('button', { class: 'sec small', onclick: () => formCatalogo(subCat, singular, x, cat, sedesDe(x.codigo), recargar) }, 'Editar'),
    h('button', { class: 'sec small', onclick: async () => { if (confirmar(`¿Eliminar ${x.nombre}?`) && await intentar(() => api(`/api/admin/catalogos/${subCat}/${x.codigo}`, { method: 'DELETE' }), 'Eliminado')) recargar(); } }, 'Eliminar')) });
  cont.replaceChildren(h('div', { class: 'caja' },
    tabs(Object.entries(defs).map(([k, v]) => [k, v[0]]), subCat, (s) => { subCat = s; recargar(); }, 'sub'),
    h('div', { class: 'fila', style: 'justify-content:space-between;align-items:center;margin-bottom:.6rem' }, h('h2', {}, titulo),
      h('button', { onclick: () => formCatalogo(subCat, singular, null, cat, [], recargar) }, `Crear ${singular}`)),
    tabla(cols, cat[subCat], `No hay ${titulo.toLowerCase()}.`)));
}

function formCatalogo(clave, singular, item, cat, sedesSel, recargar) {
  const codigo = h('input', { value: item ? item.codigo : '', disabled: !!item, maxlength: 12 });
  const nombre = h('input', { value: item ? item.nombre : '', maxlength: 80 });
  const fac = h('select', {}, h('option', { value: '' }, 'Sin facultad'), cat.facultades.map(f => h('option', { value: f.codigo, selected: item && item.facultad === f.codigo }, f.nombre)));
  const sedes = casillas(cat.sedes.map(s => ({ id: s.codigo, nombre: s.nombre })), new Map(sedesSel.map(s => [s, true])));
  const prog = clave === 'programas';
  const cerrar = modal(item ? `Editar ${singular}` : `Crear ${singular}`, h('div', {}, h('div', { class: 'form-grid' }, h('label', {}, 'Código', codigo), h('label', {}, 'Nombre', nombre),
    prog ? h('label', {}, 'Facultad', fac) : null), prog ? h('div', { style: 'margin-top:1rem' }, h('h4', {}, 'Sedes donde se ofrece'), sedes.el) : null,
    h('div', { class: 'acciones', style: 'margin-top:1rem' }, h('button', { onclick: async () => {
      const body = { codigo: codigo.value.trim(), nombre: nombre.value, ...(prog ? { facultad: fac.value || null, sedes: sedes.valor().map(s => s.id) } : {}) };
      const ok = await intentar(() => item ? api(`/api/admin/catalogos/${clave}/${item.codigo}`, { method: 'PUT', body }) : api(`/api/admin/catalogos/${clave}`, { method: 'POST', body }), 'Guardado');
      if (ok) { cerrar(); recargar(); } } }, 'Guardar'), h('button', { class: 'sec', onclick: () => cerrar() }, 'Cancelar'))), { ancho: 560 });
}

/* ---------------------------------------------------------------- notas */
async function gNotas(cont) {
  const estado = h('select', {}, [['', 'Todos los estados'], ['EN_CURSO', 'En curso'], ['APROBADO', 'Aprobado'], ['REPROBADO', 'Reprobado']].map(([v, t]) => h('option', { value: v }, t)));
  const q = h('input', { type: 'search', placeholder: 'Estudiante (nombre o código)' });
  const lista = h('div', {});
  const cargar = async () => {
    const f = await intentar(() => api(`/api/admin/matriculas?estado=${estado.value}&q=${encodeURIComponent(q.value)}`));
    if (!f) return;
    lista.replaceChildren(tabla([{ t: 'Estudiante', f: x => `${x.nombre} (${x.estudiante})` }, { t: 'Curso', f: x => `${x.curso_nombre} (${x.curso})` }, { t: 'Periodo', f: x => x.periodo },
      { t: 'Estado', f: x => estadoPill(x.estado) },
      { t: 'Nota (0–5)', f: x => { const i = numInput(x.nota == null ? '' : x.nota, 0, 5, '5rem', 0.1);
          return h('div', { class: 'nivel' }, i, h('button', { class: 'sec small', onclick: async () => {
            if (i.value === '') return toast('Escribe una nota entre 0 y 5', 'error');
            const r = await intentar(() => api('/api/admin/matriculas/nota', { method: 'PUT', body: { estudiante: x.estudiante, curso: x.curso, periodo: x.periodo, nota: i.value } }), 'Nota guardada');
            if (r) cargar(); } }, 'Guardar')); } }], f, 'No hay matrículas con ese filtro.'));
  };
  estado.addEventListener('change', cargar); q.addEventListener('input', () => { clearTimeout(q._t); q._t = setTimeout(cargar, 300); });
  cont.replaceChildren(h('div', { class: 'caja' }, h('h2', {}, 'Notas'), h('p', { class: 'dato-et' }, 'La nota define el estado: 3.0 o más aprueba. Muestra las 200 matrículas más recientes.'),
    h('div', { class: 'fila', style: 'margin:.8rem 0' }, estado, q), lista));
  cargar();
}
