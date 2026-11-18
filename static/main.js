/* Portada, acceso y carcasa de la aplicación. */
const app = $('#app');

const NS = 'http://www.w3.org/2000/svg';
const svg = (tag, attrs = {}, ...kids) => {
  const el = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  kids.flat().forEach(c => el.append(c.nodeType ? c : document.createTextNode(c)));
  return el;
};

/* El grafo de la portada es el propio dominio: una estudiante, lo que aprobó y lo que se le recomienda. */
function grafoHero() {
  const N = { ana: [90, 150, 'Ana', 'var(--ink)', '#fff'], bd1: [250, 70, 'Bases de Datos I', 'var(--grafo-bg)', 'var(--ink)'],
              prog: [250, 235, 'Programación I', 'var(--grafo-bg)', 'var(--ink)'], bd2: [430, 70, 'Bases de Datos II', '#fff', 'var(--ink)'],
              nosql: [430, 150, 'Bases de Datos NoSQL', 'var(--acento)', 'var(--ink)'], area: [340, 20, 'Área: Bases de datos', 'none', 'var(--muted)'] };
  const E = [['ana', 'bd1', 1], ['ana', 'prog', 0], ['bd1', 'bd2', 0], ['bd1', 'nosql', 1]];
  const g = svg('svg', { class: 'grafo-hero', viewBox: '0 0 540 290', role: 'img',
    'aria-label': 'Ana aprobó Bases de Datos I, que es similar a Bases de Datos NoSQL; por eso se le recomienda.' });
  E.forEach(([a, b, viva]) => g.append(svg('line', { class: 'arista' + (viva ? ' viva' : ''), x1: N[a][0], y1: N[a][1], x2: N[b][0], y2: N[b][1] })));
  Object.entries(N).forEach(([k, [x, y, t, fill, txt]]) => {
    if (k === 'area') return;
    const w = Math.max(70, t.length * 8.4 + 14);
    g.append(svg('rect', { x: x - w / 2, y: y - 19, width: w, height: 38, rx: 19, fill, stroke: 'var(--ink)', 'stroke-width': 1.5 }),
      svg('text', { x, y, style: `fill:${txt}` }, t));
  });
  g.append(svg('text', { x: 372, y: 96, style: 'fill:var(--grafo);font-size:12px' }, 'SIMILAR_A'),
    svg('text', { x: 440, y: 190, style: 'fill:var(--muted);font-size:12px' }, 'recomendado'));
  return g;
}

function portada() {
  app.replaceChildren(h('div', { class: 'portada' },
    h('div', { class: 'portada-in' },
      h('div', {},
        h('h1', {}, 'Qué cursos tomar después'),
        h('p', { class: 'lead' }, 'Un sistema de recomendación de cursos construido sobre un grafo (Neo4j), con una copia relacional (PostgreSQL) para medir qué base responde mejor cada pregunta.'),
        h('div', { class: 'puertas' },
          h('button', { class: 'puerta est', onclick: accesoEstudiante }, h('span', {}, 'Soy estudiante', h('small', {}, 'Ver mi avance, inscribir cursos y recibir recomendaciones')), '›'),
          h('button', { class: 'puerta adm', onclick: accesoAdmin }, h('span', {}, 'Soy administrador', h('small', {}, 'Comparar Neo4j y PostgreSQL, gestionar cursos y docentes')), '›'))),
      h('div', {}, grafoHero())),
    h('div', { class: 'pie' }, 'Proyecto de Bases de Datos · demostración sin contraseñas')));
}

/* ---------------------------------------------------------------- acceso */
async function accesoEstudiante() {
  const info = await intentar(() => api('/api/auth/info'));
  if (!info) return;
  const id = h('input', { id: 'est-id', placeholder: 'Ej.: E1', autocomplete: 'off' });
  const entrar = async (valor) => {
    const r = await intentar(() => api('/api/auth/estudiante/entrar', { method: 'POST', body: { id: valor } }));
    if (r) { SES.set(r); shell(); }
  };
  const nombre = h('input', { id: 'nuevo-nombre', placeholder: 'Tu nombre', maxlength: 60 });
  const sem = h('input', { id: 'nuevo-sem', type: 'number', min: 1, max: 12, value: 1 });
  const prog = h('select', { id: 'nuevo-prog' }, info.programas.map(p => h('option', { value: p.codigo }, p.nombre)));
  app.replaceChildren(h('div', { class: 'portada' }, h('div', { class: 'portada-in' },
    h('div', { class: 'panel-acceso' },
      h('h2', {}, 'Entrar como estudiante'),
      h('p', {}, 'Elige un estudiante de ejemplo o escribe tu código.'),
      h('div', { class: 'demo-lista' }, info.estudiantes_demo.map(e => h('button', { onclick: () => entrar(e.id) }, `${e.id} · ${e.nombre}`))),
      h('div', { class: 'fila' }, h('label', {}, 'Código de estudiante', id), h('button', { onclick: () => entrar(id.value) }, 'Entrar')),
      h('hr', { class: 'sep' }),
      h('h3', {}, 'Crear estudiante'),
      h('div', { class: 'fila', style: 'margin-top:.6rem' },
        h('label', {}, 'Nombre', nombre), h('label', {}, 'Semestre', sem), h('label', {}, 'Programa', prog)),
      h('div', { class: 'fila', style: 'margin-top:.8rem' },
        h('button', { onclick: async () => {
          const r = await intentar(() => api('/api/auth/estudiante/crear', { method: 'POST', body: { nombre: nombre.value, semestre: sem.value, programa: prog.value } }));
          if (r) { SES.set(r); toast(`Creado: tu código es ${r.id}`); shell(); }
        } }, 'Crear y entrar'),
        h('button', { class: 'sec', onclick: portada }, 'Volver'))),
    h('div', {}, grafoHero()))));
}

function accesoAdmin() {
  api('/api/auth/info').then(info => {
    const pin = h('input', { id: 'pin', type: 'password', placeholder: 'PIN', autocomplete: 'off' });
    const entrar = async () => {
      const r = await intentar(() => api('/api/auth/admin/entrar', { method: 'POST', body: { pin: pin.value } }));
      if (r) { SES.set(r); shell(); }
    };
    pin.addEventListener('keydown', e => { if (e.key === 'Enter') entrar(); });
    app.replaceChildren(h('div', { class: 'portada' }, h('div', { class: 'portada-in' },
      h('div', { class: 'panel-acceso' },
        h('h2', {}, 'Entrar como administrador'),
        info.admin_pin ? h('div', { class: 'fila' }, h('label', {}, 'PIN de administrador', pin)) : h('p', {}, 'No hay PIN configurado: basta con entrar.'),
        h('div', { class: 'fila', style: 'margin-top:1rem' }, h('button', { onclick: entrar }, 'Entrar'), h('button', { class: 'sec', onclick: portada }, 'Volver'))),
      h('div', {}, grafoHero()))));
    if (info.admin_pin) pin.focus();
  }).catch(e => toast(e.message, 'error'));
}

/* ---------------------------------------------------------------- carcasa */
const VISTAS = {
  estudiante: [['resumen', 'Mi avance'], ['inscribir', 'Inscribir cursos'], ['recomendaciones', 'Recomendaciones'], ['red', 'Mi red']],
  admin: [['comparar', 'Comparación en vivo'], ['gestion', 'Profesores y materias'], ['grafo', 'Explorador del grafo'], ['modelos', 'Modelos y estructuras']],
};
let vistaActual = null;

function shell(vista) {
  const s = SES.get();
  if (!s) return portada();
  clearTimeout(window.__cmpTimer);
  vista = vista || vistaActual || VISTAS[s.rol][0][0];
  vistaActual = vista;
  const cuerpo = h('main', {});
  const barra = h('header', { class: 'barra' },
    h('span', { class: 'marca' }, h('i'), 'Recomendador'),
    tabs(VISTAS[s.rol], vista, (v) => { vistaActual = v; shell(v); }),
    h('div', { class: 'quien' }, h('span', {}, s.rol === 'admin' ? 'Administrador' : `${s.nombre} (${s.id})`),
      h('button', { class: 'sec small', onclick: async () => { try { await api('/api/auth/salir', { method: 'POST' }); } catch {} SES.clear(); vistaActual = null; portada(); } }, 'Salir')));
  app.replaceChildren(barra, cuerpo);
  const pintores = { resumen: vistaResumen, inscribir: vistaInscribir, recomendaciones: vistaRecomendaciones, red: vistaRed,
                     comparar: vistaComparar, gestion: vistaGestion, grafo: vistaGrafo, modelos: vistaModelos };
  pintores[vista](cuerpo);
}

(SES.get() ? shell : portada)();
