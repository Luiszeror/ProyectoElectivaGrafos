/* Portal del estudiante. */
const colorEstado = { APROBADO: 'ok', REPROBADO: 'mal', EN_CURSO: 'aviso' };
const textoEstado = { APROBADO: 'Aprobado', REPROBADO: 'Reprobado', EN_CURSO: 'En curso' };
const estadoPill = (e) => e ? pill(textoEstado[e] || e, colorEstado[e]) : null;

async function vistaResumen(cont) {
  cont.replaceChildren(h('p', { class: 'vacio' }, 'Cargando…'));
  const p = await intentar(() => api('/api/estudiante/perfil'));
  if (!p) return;
  const { perfil, resumen } = p;
  const areas = await intentar(() => api('/api/estudiante/areas')) || [];
  const nivelPorArea = Object.fromEntries(p.intereses.map(i => [i.area, i.nivel]));
  const selects = {};

  const tarjeta = (n, et) => h('div', { class: 'caja' }, h('div', { class: 'dato' }, n), h('div', { class: 'dato-et' }, et));
  const pct = resumen.obligatorios_total ? Math.round(100 * resumen.obligatorios_aprobados / resumen.obligatorios_total) : 0;

  cont.replaceChildren(
    h('div', { class: 'caja' },
      h('h2', {}, perfil.nombre),
      h('p', {}, perfil.programa ? `${perfil.programa.nombre} · ${perfil.facultad ? perfil.facultad.nombre : 'sin facultad'}` : 'Sin programa asignado'),
      h('p', { class: 'dato-et' }, `Código ${perfil.id} · semestre ${perfil.semestre}${perfil.anio_ingreso ? ' · ingresó en ' + perfil.anio_ingreso : ''}` +
        (perfil.sedes.length ? ' · sedes: ' + perfil.sedes.map(s => s.nombre).join(', ') : ''))),
    h('div', { class: 'rejilla', style: 'margin-top:1rem' },
      tarjeta(resumen.aprobados, 'cursos aprobados'), tarjeta(resumen.en_curso, `en curso (${p.periodo_actual})`),
      tarjeta(resumen.perdidas, 'materias perdidas por repetir'), tarjeta(resumen.promedio == null ? '—' : fmt(resumen.promedio), 'promedio de notas'),
      h('div', { class: 'caja' }, h('div', { class: 'dato' }, `${pct}%`), h('div', { class: 'dato-et' }, `obligatorias aprobadas (${resumen.obligatorios_aprobados} de ${resumen.obligatorios_total})`),
        h('div', { class: 'barra-prog', style: 'margin-top:.5rem' }, h('i', { style: `width:${pct}%` })))),
    h('div', { class: 'dos' },
      h('div', { class: 'caja' }, h('h3', {}, 'Materias perdidas'),
        p.perdidas.length ? tabla([{ t: 'Curso', f: x => `${x.nombre} (${x.curso})` }, { t: 'Intentos', f: x => x.intentos, num: 1 }, { t: 'Última nota', f: x => fmt(x.ultima_nota, 1), num: 1 },
          { t: '', f: x => x.se_ofrece ? pill('Se ofrece este periodo', 'curso') : pill('No se ofrece') }], p.perdidas) : h('p', { class: 'vacio' }, 'No tienes materias perdidas pendientes.')),
      h('div', { class: 'caja' }, h('h3', {}, 'Obligatorias que faltan'),
        tabla([{ t: 'Curso', f: x => `${x.nombre} (${x.curso})` }, { t: 'Semestre sugerido', f: x => x.semestre, num: 1 }, { t: 'Estado', f: x => estadoPill(x.estado) || pill('Sin cursar') }],
          p.pendientes_obligatorios, 'Ya aprobaste todas las obligatorias de tu programa.'))),
    h('div', { class: 'caja', style: 'margin-top:1rem' }, h('h3', {}, 'Historial'),
      tabla([{ t: 'Periodo', f: x => x.periodo }, { t: 'Curso', f: x => `${x.nombre} (${x.curso})` }, { t: 'Tipo', f: x => x.tipo }, { t: 'Nivel', f: x => x.nivel },
        { t: 'Nota', f: x => x.nota == null ? '—' : fmt(x.nota, 1), num: 1 }, { t: 'Estado', f: x => estadoPill(x.estado) }], p.historial, 'Aún no tienes cursos en tu historial.')),
    h('div', { class: 'caja', style: 'margin-top:1rem' }, h('h3', {}, 'Mis intereses'),
      h('p', { class: 'dato-et' }, 'Define qué áreas te interesan (1 = poco, 5 = mucho). Las recomendaciones por intereses los usan.'),
      h('div', { class: 'rejilla', style: 'margin:.8rem 0' }, areas.map(a => {
        const s = h('select', {}, h('option', { value: 0 }, 'Sin interés'), [1, 2, 3, 4, 5].map(n => h('option', { value: n, selected: nivelPorArea[a.codigo] === n }, n)));
        selects[a.codigo] = s;
        return h('label', {}, a.nombre, s);
      })),
      h('button', { onclick: async () => {
        const items = Object.entries(selects).filter(([, s]) => +s.value > 0).map(([area, s]) => ({ area, nivel: +s.value }));
        await intentar(() => api('/api/estudiante/intereses', { method: 'PUT', body: { items } }), 'Intereses guardados');
      } }, 'Guardar intereses')));
}

async function vistaInscribir(cont) {
  const buscar = h('input', { type: 'search', placeholder: 'Buscar por nombre o código', style: 'min-width:16rem' });
  const lista = h('div', {});
  const solo = h('input', { type: 'checkbox' });
  let datos = null;
  const pintar = () => {
    const q = buscar.value.trim().toLowerCase();
    const filas = datos.cursos.filter(c => (!q || c.nombre.toLowerCase().includes(q) || c.codigo.toLowerCase().includes(q)) && (!solo.checked || c.puede || c.estado === 'EN_CURSO'));
    lista.replaceChildren(tabla([
      { t: 'Curso', f: c => h('div', {}, h('b', {}, c.nombre), ' ', h('span', { class: 'dato-et' }, `${c.codigo} · ${c.tipo} · ${c.nivel}`),
          h('div', { class: 'dato-et' }, c.areas.map(a => a.nombre).join(', '))) },
      { t: 'Requisitos', f: c => c.requisitos.length ? c.requisitos.map(r => h('div', {}, (r.cumplido ? '✓ ' : '✗ ') + r.nombre, r.tipo === 'CORREQUISITO' ? ' (correquisito)' : '')) : '—' },
      { t: 'Cupos', f: c => c.sedes.length ? `${c.cupos_libres} · ${c.sedes.map(s => s.nombre).join(', ')}` : 'No se ofrece', num: 0 },
      { t: 'Docente', f: c => c.docentes.map(d => d.nombre).join(', ') || '—' },
      { t: '', f: c => c.estado === 'EN_CURSO'
          ? h('button', { class: 'sec small', onclick: async () => { if (await intentar(() => api('/api/estudiante/retirar', { method: 'POST', body: { curso: c.codigo } }), 'Curso retirado')) cargar(); } }, 'Retirar')
          : c.puede ? h('button', { class: 'small', onclick: async () => { if (await intentar(() => api('/api/estudiante/inscribir', { method: 'POST', body: { curso: c.codigo } }), `Inscrito en ${c.nombre}`)) cargar(); } }, 'Inscribir')
          : h('div', {}, estadoPill(c.estado), c.motivos.map(m => h('div', { class: 'motivo' }, m))) },
    ], filas, 'Ningún curso coincide con tu búsqueda.'));
  };
  const cargar = async () => { datos = await intentar(() => api('/api/estudiante/catalogo')); if (datos) pintar(); };
  buscar.addEventListener('input', () => datos && pintar());
  solo.addEventListener('change', () => datos && pintar());
  cont.replaceChildren(h('div', { class: 'caja' }, h('h2', {}, 'Inscribir cursos'),
    h('p', { class: 'dato-et' }, 'Solo puedes inscribir cursos que se ofrecen este periodo, con cupo y con tus prerrequisitos aprobados. Los cursos perdidos se pueden repetir.'),
    h('div', { class: 'fila', style: 'margin:.8rem 0' }, buscar, h('label', { style: 'display:flex;flex-direction:row;align-items:center;gap:.4rem;flex:0 0 auto' }, solo, 'Mostrar solo los que puedo inscribir')), lista));
  cargar();
}

async function vistaRecomendaciones(cont) {
  cont.replaceChildren(h('p', { class: 'vacio' }, 'Calculando recomendaciones en el grafo…'));
  const r = await intentar(() => api('/api/estudiante/recomendaciones'));
  if (!r) return;
  const bloque = (titulo, ayuda, filas, porque) => h('div', { class: 'caja' }, h('h3', {}, titulo), h('p', { class: 'dato-et' }, ayuda),
    filas.length ? h('ul', { class: 'lista-rec' }, filas.map(x => h('li', {}, h('span', {}, h('b', {}, x.nombre), ' ', h('span', { class: 'dato-et' }, x.codigo)), pill(fmt(x.puntaje, 1) + ' pts'),
      h('span', { class: 'porque' }, porque(x))))) : h('p', { class: 'vacio' }, 'Por ahora no hay sugerencias aquí.'));
  cont.replaceChildren(
    h('div', { class: 'dos', style: 'margin-top:0' },
      bloque('Por lo que ya aprobaste', 'Cursos similares (comparten áreas) a los que aprobaste, con prerrequisitos cumplidos.', r.por_historial, x => 'Parecido a: ' + x.porque.join(', ')),
      bloque('Por tus intereses', 'Cursos de las áreas que marcaste, ponderados por tu nivel de interés.', r.por_intereses, x => 'Áreas: ' + x.porque.join(', ')),
      bloque('Fuera de tu programa', 'Electivos de otros programas que se parecen a lo que ya dominas.', r.otros_programas, x => 'Parecido a: ' + x.porque.join(', ')),
      bloque('Lo que hicieron otros como tú', 'Cursos aprobados por estudiantes que comparten cursos contigo.', r.estudiantes_similares, x => `${x.porque} estudiante(s) similares lo aprobaron`)),
    h('div', { class: 'dos' },
      h('div', { class: 'caja' }, h('h3', {}, 'Tus áreas fuertes'),
        tabla([{ t: 'Área', f: a => a.nombre }, { t: 'Cursos aprobados', f: a => a.cursos, num: 1 }, { t: 'Promedio', f: a => fmt(a.promedio, 1), num: 1 }], r.areas_fortalezas, 'Aprueba cursos para ver tus fortalezas.')),
      h('div', { class: 'caja' }, h('h3', {}, 'Áreas para explorar'),
        h('p', { class: 'dato-et' }, 'Áreas nuevas conectadas con las que ya conoces mediante cursos puente.'),
        tabla([{ t: 'Área', f: a => a.nombre }, { t: 'Cursos puente', f: a => a.cursos_puente, num: 1 }, { t: 'Desde', f: a => a.desde.join(', ') }], r.areas_explorar, 'Sin áreas nuevas por ahora.'))));
}

async function vistaRed(cont) {
  const caja = h('div', { id: 'red' });
  cont.replaceChildren(h('div', { class: 'caja' }, h('h2', {}, 'Mi red en el grafo'),
    h('p', { class: 'dato-et' }, 'Tú, tus cursos, sus áreas y tu programa, tal como los guarda Neo4j. Arrastra los nodos para explorar.')), caja);
  const r = await intentar(() => api('/api/estudiante/red'));
  if (!r) return;
  crearRed(caja, r.nodos, r.aristas);
}
