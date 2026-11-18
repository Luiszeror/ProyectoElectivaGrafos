/* Pestaña de modelos: cómo se organiza la información en PostgreSQL y en Neo4j (leído de las bases reales). */

/* ----- diagrama entidad-relación de PostgreSQL, generado desde el catálogo real */
const ER_POS = [['facultad', 'programa', 'programa_sede', 'sede'], ['estudiante', 'curso_programa', 'curso_sede', 'curso_similar'],
                ['matricula', 'curso', 'curso_area', 'area'], ['interes_estudiante', 'prerrequisito', 'dictado', 'docente']];

function diagramaER(tablas) {
  const W = 190, GX = 40, GY = 36, RH = 13, CAB = 22;
  const por = Object.fromEntries(tablas.map(t => [t.nombre, t]));
  const caja = {};
  let y = 10; const altos = [];
  ER_POS.forEach((fila, r) => {
    const hmax = Math.max(...fila.map(n => por[n] ? CAB + RH * por[n].columnas.length + 8 : 0));
    fila.forEach((n, c) => { if (por[n]) caja[n] = { x: 10 + c * (W + GX), y, h: CAB + RH * por[n].columnas.length + 8 }; });
    y += hmax + GY; altos.push(hmax);
  });
  const g = svg('svg', { class: 'diagrama', viewBox: `0 0 ${10 + 4 * (W + GX)} ${y}`, role: 'img', 'aria-label': 'Diagrama entidad-relación de PostgreSQL' });
  g.append(svg('defs', {}, svg('marker', { id: 'pie', viewBox: '0 0 10 10', refX: 9, refY: 5, markerWidth: 7, markerHeight: 7, orient: 'auto' }, svg('path', { d: 'M0 0L10 5L0 10z', fill: '#3F51B5' }))));
  const centro = (n) => [caja[n].x + W / 2, caja[n].y + caja[n].h / 2];
  const borde = (n, hacia) => { // punto del borde de la caja n en dirección a `hacia`
    const [cx, cy] = centro(n), dx = hacia[0] - cx, dy = hacia[1] - cy, hw = W / 2, hh = caja[n].h / 2;
    const k = Math.min(dx ? hw / Math.abs(dx) : 1e9, dy ? hh / Math.abs(dy) : 1e9); return [cx + dx * k, cy + dy * k];
  };
  tablas.forEach(t => t.restricciones.filter(r => r.tipo === 'FOREIGN KEY').forEach(r => {
    const m = /REFERENCES (\w+)\(/.exec(r.definicion); if (!m || !caja[t.nombre] || !caja[m[1]]) return;
    const a = borde(t.nombre, centro(m[1])), b = borde(m[1], centro(t.nombre));
    g.append(svg('line', { x1: a[0], y1: a[1], x2: b[0], y2: b[1], stroke: '#3F51B5', 'stroke-opacity': .55, 'stroke-width': 1.3, 'marker-end': 'url(#pie)' }));
  }));
  tablas.forEach(t => {
    const c = caja[t.nombre]; if (!c) return;
    const pk = new Set(), fk = new Set();
    t.restricciones.forEach(r => { const cols = (/\(([^)]*)\)/.exec(r.definicion) || [, ''])[1].split(',').map(s => s.trim());
      if (r.tipo === 'PRIMARY KEY') cols.forEach(x => pk.add(x)); if (r.tipo === 'FOREIGN KEY') cols.forEach(x => fk.add(x)); });
    const derivada = t.nombre === 'curso_similar';
    g.append(svg('rect', { x: c.x, y: c.y, width: W, height: c.h, rx: 6, fill: '#fff', stroke: derivada ? '#8d99ae' : '#3F51B5', 'stroke-width': 1.5, 'stroke-dasharray': derivada ? '5 4' : '0' }),
      svg('rect', { x: c.x, y: c.y, width: W, height: CAB, rx: 6, fill: derivada ? '#8d99ae' : '#3F51B5' }),
      svg('text', { x: c.x + 8, y: c.y + 15, fill: '#fff', 'font-size': 12, 'font-weight': 700 }, t.nombre + (derivada ? ' (derivada)' : '')));
    t.columnas.forEach((col, i) => {
      const marca = pk.has(col.nombre) ? 'PK' : fk.has(col.nombre) ? 'FK' : '';
      g.append(svg('text', { x: c.x + 8, y: c.y + CAB + 12 + i * RH, 'font-size': 10.5, fill: '#172033', 'font-weight': pk.has(col.nombre) ? 700 : 400 }, col.nombre),
        svg('text', { x: c.x + W - 8, y: c.y + CAB + 12 + i * RH, 'font-size': 9.5, fill: marca === 'PK' ? '#C0392B' : '#3F51B5', 'text-anchor': 'end', 'font-weight': 700 }, marca));
    });
  });
  return g;
}

/* ----- diagrama del esquema de grafo de Neo4j */
const NEO_POS = { Estudiante: [80, 200], Area: [300, 60], Programa: [300, 340], Curso: [300, 200], Docente: [520, 60], Sede: [520, 340], Facultad: [80, 340] };
const NEO_COL = { Estudiante: '#172033', Curso: '#0B8A83', Area: '#F2B705', Programa: '#3F51B5', Docente: '#6C7A91', Sede: '#6C7A91', Facultad: '#6C7A91' };

function diagramaGrafo(rels) {
  const g = svg('svg', { class: 'diagrama', viewBox: '0 0 620 410', role: 'img', 'aria-label': 'Esquema de nodos y relaciones de Neo4j' });
  g.append(svg('defs', {}, svg('marker', { id: 'flecha', viewBox: '0 0 10 10', refX: 9, refY: 5, markerWidth: 7, markerHeight: 7, orient: 'auto' }, svg('path', { d: 'M0 0L10 5L0 10z', fill: '#0B8A83' }))));
  const R = 36, pares = {};
  rels.forEach(r => {
    const [x1, y1] = NEO_POS[r.de], [x2, y2] = NEO_POS[r.a];
    if (r.de === r.a) { // relaciones del curso consigo mismo: bucles a la derecha
      const k = pares.self = (pares.self || 0) + 1, oy = k === 1 ? -14 : 14, dy = k === 1 ? -30 : 30;
      g.append(svg('path', { d: `M${x1 + R - 4} ${y1 + oy} C ${x1 + 100} ${y1 + oy + dy * 1.6}, ${x1 + 100} ${y1 + oy - dy * 1.6}, ${x1 + R - 3} ${y1 + oy - dy * .3}`, fill: 'none', stroke: r.derivada ? '#8d99ae' : '#0B8A83', 'stroke-width': 1.6, 'stroke-dasharray': r.derivada ? '5 4' : '0', 'marker-end': 'url(#flecha)' }),
        svg('text', { x: x1 + 92, y: y1 + oy + dy * (k === 1 ? 1.15 : 1.15), 'font-size': 10, fill: '#172033', 'text-anchor': 'start' }, r.tipo));
      return;
    }
    const dx = x2 - x1, dy = y2 - y1, d = Math.hypot(dx, dy), ux = dx / d, uy = dy / d;
    g.append(svg('line', { x1: x1 + ux * R, y1: y1 + uy * R, x2: x2 - ux * (R + 3), y2: y2 - uy * (R + 3), stroke: '#0B8A83', 'stroke-width': 1.6, 'marker-end': 'url(#flecha)' }));
    const mx = (x1 + x2) / 2, my = (y1 + y2) / 2;
    const w = r.tipo.length * 6 + 8;
    g.append(svg('rect', { x: mx - w / 2, y: my - 8, width: w, height: 15, rx: 4, fill: '#F4F6FA' }), svg('text', { x: mx, y: my + 3, 'font-size': 10, fill: '#172033', 'text-anchor': 'middle' }, r.tipo));
  });
  Object.entries(NEO_POS).forEach(([n, [x, y]]) => {
    const c = NEO_COL[n], oscuro = c !== '#F2B705';
    g.append(svg('circle', { cx: x, cy: y, r: R, fill: c, stroke: '#172033', 'stroke-width': 1.5 }), svg('text', { x, y: y + 4, 'font-size': 12, 'font-weight': 700, fill: oscuro ? '#fff' : '#172033', 'text-anchor': 'middle' }, n));
  });
  return g;
}

const ampliable = (titulo, fabrica) => h('div', { class: 'ampliable' },
  h('button', { class: 'sec small', onclick: () => modal(titulo, fabrica(), { ancho: 1400 }) }, 'Ampliar'), fabrica());
const lista = (items) => h('ul', { class: 'explica' }, items.map(t => h('li', {}, t)));
const mono = (t) => h('code', {}, t);

async function vistaModelos(cont) {
  cont.replaceChildren(h('p', { class: 'vacio' }, 'Leyendo la estructura de las dos bases…'));
  const m = await intentar(() => api('/api/admin/modelos'));
  if (!m) return;
  const err = (x) => x && x.error ? h('p', { class: 'motivo' }, 'No se pudo leer: ' + x.error) : null;

  /* ------------------------------ mitad PostgreSQL */
  const pg = m.postgres;
  const izq = h('section', { class: 'mitad pg modelos' }, h('h2', {}, 'PostgreSQL · modelo relacional'),
    h('p', { class: 'explica' }, 'La información se guarda en tablas con columnas tipadas. Cada hecho vive en un solo lugar (tercera forma normal) y las relaciones entre cosas se expresan con llaves foráneas; para recorrerlas se hacen JOIN.'),
    err(pg),
    !pg.error ? [
      h('h4', {}, 'Diagrama entidad-relación'), ampliable('Diagrama entidad-relación', () => diagramaER(pg.tablas)),
      h('p', { class: 'dato-et' }, 'PK = llave primaria · FK = llave foránea · la flecha apunta a la tabla referenciada · línea punteada = tabla derivada que se recalcula.'),
      h('h4', {}, 'Cómo se representan las relaciones'),
      lista([
        ['Uno a muchos: ', mono('estudiante.id_programa'), ' es una FK a ', mono('programa'), '.'],
        ['Muchos a muchos con datos: la matrícula es la tabla ', mono('matricula'), ' con PK compuesta (id_estudiante, codigo_curso, periodo); por eso se puede repetir un curso perdido en otro periodo.'],
        ['Muchos a muchos simples: ', mono('curso_area'), ', ', mono('prerrequisito'), ', ', mono('dictado'), ', ', mono('curso_sede'), ' (una tabla puente por relación).'],
        ['Relación derivada: ', mono('curso_similar'), ' guarda los pares de cursos que comparten áreas, equivalente a SIMILAR_A.'],
        'Colecciones y documentos: no aplican; en un modelo relacional las "filas" son los registros.'].map(x => Array.isArray(x) ? x : [x])),
      h('h4', {}, 'Reglas que la base hace cumplir'),
      lista(['CHECK en matricula: EN_CURSO sin nota, APROBADO con nota ≥ 3.0, REPROBADO con nota < 3.0.', 'CHECK en curso (tipo y nivel válidos), en periodo (formato AAAA-S) y en prerrequisito (un curso no se exige a sí mismo).',
        'ON DELETE CASCADE: al borrar un curso o estudiante se borran sus filas dependientes.']),
      h('h4', {}, 'Tablas, columnas, llaves e índices (leído de la base)'),
      pg.tablas.map(t => h('details', {}, h('summary', {}, `${t.nombre} · ${fmt(t.filas, 0)} filas`),
        tabla([{ t: 'Columna', f: c => c.nombre }, { t: 'Tipo', f: c => c.tipo }, { t: 'Nulo', f: c => c.nulo ? 'sí' : 'no' }], t.columnas),
        t.restricciones.length ? code(t.restricciones.map(r => `${r.tipo}  ${r.definicion}`).join('\n')) : null,
        t.indices.length ? code(t.indices.map(i => i.definicion).join('\n')) : null)),
      h('h4', {}, 'Estructuras de claves e índices creados'),
      lista(['Cada PK crea un índice único automáticamente (búsqueda por id en O(log n)).', 'idx_matricula_curso (codigo_curso, estado): cuenta aprobados por curso y cupos.',
        'idx_curso_area_area, idx_interes_area: unen cursos con áreas sin recorrer toda la tabla.', 'idx_prerreq_req: encuentra quién depende de un curso.',
        'idx_curso_sede_periodo: filtra lo que se ofrece en el periodo actual.', 'Después de cargar se ejecuta ANALYZE para que el planificador conozca el tamaño real de cada tabla.']),
      h('details', {}, h('summary', {}, 'Ver el DDL completo'), code(pg.ddl))] : null);

  /* ------------------------------ mitad Neo4j */
  const ne = m.neo4j;
  const der = h('section', { class: 'mitad neo modelos' }, h('h2', {}, 'Neo4j · modelo de grafo'),
    h('p', { class: 'explica' }, 'La información se guarda como nodos (cosas) y relaciones (conexiones con nombre y dirección) que ya vienen unidas. Para recorrer una conexión no se calcula un JOIN: se sigue el enlace directo entre nodos.'),
    err(ne),
    !ne.error ? [
      h('h4', {}, 'Esquema de nodos y relaciones'), ampliable('Esquema de nodos y relaciones', () => diagramaGrafo(ne.relaciones)),
      h('p', { class: 'dato-et' }, 'Línea continua = relación guardada · punteada = relación derivada (SIMILAR_A se calcula a partir de las áreas compartidas).'),
      h('h4', {}, 'Cómo se representan las cosas'),
      lista([['Cada fila de ', mono('estudiante'), ', ', mono('curso'), ', etc. es un nodo con su etiqueta y propiedades, p. ej. ', mono('(:Curso {codigo, nombre, tipo, nivel})'), '.'],
        ['Las tablas puente desaparecen: ', mono('matricula'), ' pasa a ser la relación ', mono('(:Estudiante)-[:HA_CURSADO {periodo, nota, estado}]->(:Curso)'), ' con sus propiedades.'],
        'Una relación guarda su tipo, su dirección y sus propiedades (periodo, peso, cupos…); no existe una columna de llave foránea.',
        'Colecciones y documentos: no aplican; los datos son un grafo de propiedades, no documentos.'].map(x => Array.isArray(x) ? x : [x])),
      h('h4', {}, 'Nodos'),
      tabla([{ t: 'Etiqueta', f: n => h('b', {}, n.etiqueta) }, { t: 'Clave', f: n => n.clave }, { t: 'Propiedades', f: n => n.props.join(', ') }, { t: 'Equivale a', f: n => n.tabla }, { t: 'Cantidad', f: n => fmt(n.total, 0), num: 1 }], ne.nodos),
      h('h4', {}, 'Relaciones'),
      tabla([{ t: 'Tipo', f: r => h('b', {}, r.tipo) }, { t: 'De → a', f: r => `${r.de} → ${r.a}` }, { t: 'Propiedades', f: r => r.props.join(', ') || '—' }, { t: 'Origen en el modelo relacional', f: r => r.origen },
        { t: 'Cantidad', f: r => fmt(r.total, 0), num: 1 }], ne.relaciones),
      h('h4', {}, 'Restricciones (llaves) e índices (leídos de la base)'),
      ne.restricciones.length ? tabla([{ t: 'Nombre', f: x => x.name }, { t: 'Tipo', f: x => x.type }, { t: 'Sobre', f: x => `${x.labelsOrTypes.join(':')}(${x.properties.join(', ')})` }], ne.restricciones) : h('p', { class: 'vacio' }, 'Sin restricciones.'),
      ne.indices.length ? tabla([{ t: 'Nombre', f: x => x.name }, { t: 'Tipo', f: x => x.type }, { t: 'Sobre', f: x => `${x.labelsOrTypes.join(':')}(${x.properties.join(', ')})` }, { t: 'Estado', f: x => x.state }], ne.indices) : null,
      lista(['Una restricción UNIQUE por clave de nodo (id o código) garantiza que no haya duplicados y crea su índice.', 'Los índices solo se usan para ENCONTRAR el nodo de inicio (p. ej. el estudiante E1); desde ahí el recorrido sigue relaciones sin índices.',
        'hc_estado y hc_periodo indexan propiedades de la relación HA_CURSADO para filtrar por estado o periodo.']),
      h('details', {}, h('summary', {}, 'Ver el Cypher que crea las restricciones e índices'), code(ne.cypher_esquema))] : null);

  /* ------------------------------ ejemplo lado a lado */
  const ej = m.ejemplo;
  const ejemplo = ej && !ej.error ? h('div', { class: 'caja' }, h('h3', {}, `El mismo dato en las dos bases: ${ej.estudiante} aprobó ${ej.curso}`),
    h('div', { class: 'dos' },
      h('div', {}, h('h4', {}, 'PostgreSQL: una fila de matricula'), code(JSON.stringify(ej.postgres, null, 2))),
      h('div', {}, h('h4', {}, 'Neo4j: la relación HA_CURSADO entre dos nodos'), code(JSON.stringify(ej.neo4j, null, 2))))) : err(ej);

  cont.replaceChildren(h('div', { class: 'partida delgada' }, izq, h('div', { class: 'centro' }), der), h('div', { style: 'margin-top:1rem' }, ejemplo));
}
