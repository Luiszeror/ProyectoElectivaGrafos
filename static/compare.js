/* Pestaña de comparación: pantalla partida PostgreSQL | Neo4j con medición en vivo. */
const HISTORIAL_CMP = [];

async function vistaComparar(cont) {
  const escenarios = await intentar(() => api('/api/admin/comparar/escenarios'));
  if (!escenarios) return;
  const est = { esc: escenarios[0], alcance: 'base', sujeto: '', variante: 'sql', corriendo: false, continuo: false };

  const selEsc = h('select', { id: 'cmp-esc' }, ['Recomendación', 'Relaciones', 'Reglas de negocio', 'Agregación'].map(t =>
    h('optgroup', { label: t }, escenarios.filter(e => e.tema === t).map(e => h('option', { value: e.id }, e.titulo)))));
  const pregunta = h('p', { class: 'dato-et', style: 'max-width:60ch' });
  const inSujeto = h('input', { id: 'cmp-sujeto', size: 10, placeholder: 'código' });
  const selAlc = h('select', {}, h('option', { value: 'base' }, 'Datos base'), h('option', { value: 'volumen' }, 'Datos de volumen'));
  const reps = h('input', { type: 'number', min: 1, max: 30, value: 8, style: 'width:5rem' });
  const chkMat = h('input', { type: 'checkbox' });
  const chkCont = h('input', { type: 'checkbox' });
  const btn = h('button', { onclick: () => correr() }, 'Ejecutar comparación');
  const lblSujeto = h('span', {});
  const sal = h('div', {});
  const histBox = h('div', { class: 'hist' });
  const estadoBox = h('div', {});

  const sincSujeto = async () => {
    if (est.esc.sujeto === 'ninguno') { inSujeto.value = ''; inSujeto.disabled = true; lblSujeto.textContent = 'Sin sujeto'; return; }
    inSujeto.disabled = false;
    lblSujeto.textContent = est.esc.sujeto === 'curso' ? 'Curso' : 'Estudiante';
    try {
      const r = await api(`/api/admin/comparar/muestra?sujeto=${est.esc.sujeto}&alcance=${est.alcance}`);
      inSujeto.value = r.id;
    } catch (e) { inSujeto.value = ''; if (est.alcance === 'volumen') toast(e.message, 'error'); }
  };
  const elegir = () => {
    est.esc = escenarios.find(e => e.id === selEsc.value);
    pregunta.textContent = est.esc.pregunta;
    chkMat.disabled = !est.esc.sql_mat; if (!est.esc.sql_mat) chkMat.checked = false;
    sincSujeto();
  };
  selEsc.addEventListener('change', elegir);
  selAlc.addEventListener('change', () => { est.alcance = selAlc.value; sincSujeto(); });

  const mitad = (clase, titulo, version, r, sqlTexto, lang) => {
    const motor = r ? r.motor : null, total = r ? r.total : null;
    const max = r ? Math.max(...r.muestras) || 1 : 1;
    return h('section', { class: 'mitad ' + clase },
      h('div', { class: 'cab' }, h('h3', {}, titulo), h('span', { class: 'dato-et' }, version || '')),
      r ? [
        h('div', { class: 'medidor' }, h('span', { class: 'dato' }, fmtMs(motor.mediana)), h('span', {}, 'ms en el motor (mediana)')),
        h('div', { class: 'stats' }, h('span', {}, 'tiempo total ', h('b', {}, fmtMs(total.mediana) + ' ms')), h('span', {}, 'mín ', h('b', {}, fmtMs(motor.min))),
          h('span', {}, 'p95 ', h('b', {}, fmtMs(motor.p95))), h('span', {}, 'filas ', h('b', {}, r.filas))),
        h('div', { class: 'muestras', title: 'Tiempo total de cada repetición', 'aria-label': 'Tiempos por repetición' },
          r.muestras.map(m => h('i', { style: `height:${Math.max(4, 100 * m / max)}%`, title: fmtMs(m) + ' ms' }))),
        tabla([{ t: 'Código', f: x => x.codigo }, { t: 'Nombre', f: x => x.nombre || '' },
          { t: 'Valor', f: x => { const k = Object.keys(x).find(k => !['codigo', 'nombre', 'porque'].includes(k)); return k ? fmt(x[k], 1) : ''; }, num: 1 }], r.resultado.slice(0, 6), 'La consulta no devolvió filas.'),
      ] : h('p', { class: 'vacio' }, est.corriendo ? 'Midiendo…' : 'Aún no se ha ejecutado.'),
      h('details', {}, h('summary', {}, `Ver consulta (${lang})`), code(sqlTexto)));
  };

  const pintar = (res, plan) => {
    if (!res) { sal.replaceChildren(h('div', { class: 'partida' }, mitad('pg', 'PostgreSQL', '', null, est.esc.sql, 'SQL'), h('div', { class: 'centro' }), mitad('neo', 'Neo4j', '', null, est.esc.cypher, 'Cypher'))); return; }
    const sqlTexto = res.variante === 'sql_mat' ? est.esc.sql_mat : est.esc.sql;
    const pg = res.postgres.motor.mediana, ne = res.neo4j.motor.mediana;
    const rapido = pg < ne ? 'PostgreSQL' : 'Neo4j', ratio = Math.max(pg, ne) / Math.max(Math.min(pg, ne), 0.001);
    const noSinc = res.postgres.filas === 0 && res.neo4j.filas > 0;
    sal.replaceChildren(
      h('div', { class: 'partida' },
        mitad('pg', 'PostgreSQL', estadoGlobal ? estadoGlobal.postgres.version : '', res.postgres, sqlTexto, res.variante === 'sql_mat' ? 'SQL con curso_similar' : 'SQL'),
        h('div', { class: 'centro' }, h('span', { class: 'veredicto ' + (res.equivalentes ? 'igual' : 'dif') }, res.equivalentes ? '✓ mismo resultado' : '✗ resultados distintos')),
        mitad('neo', 'Neo4j', estadoGlobal ? estadoGlobal.neo4j.version : '', res.neo4j, est.esc.cypher, 'Cypher')),
      h('div', { class: 'ganador' }, h('strong', {}, `${rapido} fue ${fmt(ratio, 1)}× más rápido en el motor`),
        h('span', { class: 'dato-et' }, res.nota_tiempos),
        noSinc ? pill('PostgreSQL parece vacío: pulsa «Sincronizar» en Datos y volumen', 'mal') : null,
        !res.equivalentes && !noSinc ? pill('Revisa si PostgreSQL está sincronizado', 'aviso') : null,
        h('button', { class: 'sec small', onclick: verPlanes }, 'Ver planes de ejecución')));
  };

  const verPlanes = async () => {
    const p = await intentar(() => api('/api/admin/comparar/plan', { method: 'POST', body: planCuerpo() }));
    if (p) modal('Planes de ejecución', h('div', { class: 'dos', style: 'margin:0' },
      h('div', {}, h('h4', {}, 'PostgreSQL · EXPLAIN (ANALYZE, BUFFERS)'), code(p.postgres.join('\n'))),
      h('div', {}, h('h4', {}, 'Neo4j · PROFILE'), code(p.neo4j.join('\n')))), { ancho: 1100 });
  };

  const planCuerpo = () => ({ escenario: est.esc.id, sujeto: inSujeto.value.trim() || null, variante: chkMat.checked ? 'sql_mat' : 'sql' });

  const correr = async () => {
    if (est.corriendo) return;
    est.corriendo = true; btn.disabled = true; btn.textContent = 'Midiendo…';
    const cuerpo = { ...planCuerpo(), repeticiones: +reps.value || 5 };
    const res = await intentar(() => api('/api/admin/comparar/ejecutar', { method: 'POST', body: cuerpo }));
    est.corriendo = false; btn.disabled = false; btn.textContent = 'Ejecutar comparación';
    if (res) {
      pintar(res);
      HISTORIAL_CMP.unshift({ hora: new Date().toLocaleTimeString('es-CO'), esc: est.esc.titulo, sujeto: res.sujeto || '—', alcance: est.alcance, pg: res.postgres.motor.mediana, neo: res.neo4j.motor.mediana, ok: res.equivalentes, variante: res.variante });
      HISTORIAL_CMP.splice(40);
      pintarHistorial();
    }
    if (est.continuo && document.body.contains(btn)) window.__cmpTimer = setTimeout(correr, 1500);
  };
  chkCont.addEventListener('change', () => { est.continuo = chkCont.checked; if (est.continuo) correr(); else clearTimeout(window.__cmpTimer); });

  const pintarHistorial = () => histBox.replaceChildren(h('div', { class: 'caja' }, h('h3', {}, 'Mediciones de esta sesión'),
    tabla([{ t: 'Hora', f: x => x.hora }, { t: 'Pregunta', f: x => x.esc }, { t: 'Sujeto', f: x => x.sujeto }, { t: 'Datos', f: x => x.alcance === 'volumen' ? 'volumen' : 'base' },
      { t: 'SQL', f: x => x.variante === 'sql_mat' ? 'materializado' : 'al vuelo' },
      { t: 'PostgreSQL ms', f: x => fmtMs(x.pg), num: 1 }, { t: 'Neo4j ms', f: x => fmtMs(x.neo), num: 1 },
      { t: 'Más rápido', f: x => (x.pg < x.neo ? 'PostgreSQL' : 'Neo4j') + ` ${fmt(Math.max(x.pg, x.neo) / Math.max(Math.min(x.pg, x.neo), 0.001), 1)}×` },
      { t: 'Igual', f: x => x.ok ? '✓' : '✗' }], HISTORIAL_CMP, 'Ejecuta una comparación para ver el historial.')));

  let estadoGlobal = null;
  const cargarEstado = async () => {
    estadoGlobal = await intentar(() => api('/api/admin/estado'));
    if (!estadoGlobal) return;
    const n = estadoGlobal.neo4j, p = estadoGlobal.postgres;
    estadoBox.replaceChildren(h('div', { class: 'caja' },
      h('div', { class: 'fila', style: 'justify-content:space-between;align-items:center' },
        h('h3', {}, 'Datos y volumen'),
        h('div', {}, estadoGlobal.sincronizado ? pill('PostgreSQL sincronizado con Neo4j', 'ok') : pill('PostgreSQL no coincide con Neo4j', 'mal'))),
      h('div', { class: 'rejilla', style: 'margin:.6rem 0' },
        h('div', {}, h('div', { class: 'dato' }, n.error ? '—' : fmt(n.total_nodos, 0)), h('div', { class: 'dato-et' }, n.error ? n.error : `nodos en Neo4j · ${fmt(n.total_relaciones, 0)} relaciones (tope Aura ${fmt(estadoGlobal.aura.max_nodos, 0)} / ${fmt(estadoGlobal.aura.max_relaciones, 0)})`)),
        h('div', {}, h('div', { class: 'dato' }, p.error ? '—' : fmt(p.tablas.matricula, 0)), h('div', { class: 'dato-et' }, p.error ? p.error : `matrículas en PostgreSQL · ${fmt(p.tablas.estudiante, 0)} estudiantes, ${fmt(p.tablas.curso, 0)} cursos`))),
      h('div', { class: 'fila' },
        h('label', {}, 'Estudiantes de prueba', h('input', { id: 'vol-est', type: 'number', min: 10, max: 15000, value: 2000 })),
        h('label', {}, 'Cursos de prueba', h('input', { id: 'vol-cur', type: 'number', min: 10, max: 400, value: 80 })),
        h('button', { onclick: () => lanzarJob('/api/admin/datos/generar', { estudiantes: +$('#vol-est').value, cursos: +$('#vol-cur').value }) }, 'Generar volumen'),
        h('button', { class: 'sec', onclick: () => lanzarJob('/api/admin/datos/sincronizar') }, 'Sincronizar PostgreSQL'),
        h('button', { class: 'sec', onclick: () => lanzarJob('/api/admin/datos/limpiar') }, 'Eliminar volumen')),
      h('p', { class: 'dato-et' }, 'El volumen son datos inventados, marcados y aislados: no aparecen en el portal de estudiantes y se pueden borrar sin tocar los datos reales. Después de crear, editar o borrar cursos, notas o estudiantes en Neo4j, sincroniza para que PostgreSQL tenga lo mismo.'),
      h('div', { id: 'job-box' })));
  };

  const lanzarJob = async (url, body) => {
    const r = await intentar(() => api(url, { method: 'POST', body }));
    if (!r) return;
    const box = $('#job-box');
    const barra = h('i', { style: 'width:0%' }), texto = h('p', { class: 'dato-et' }, 'Iniciando…');
    box.replaceChildren(h('div', { class: 'barra-prog' }, barra), texto);
    const tick = async () => {
      let j;
      try { j = await api(`/api/admin/datos/job/${r.job}`); } catch (e) { texto.textContent = e.message; return; }
      barra.style.width = j.pct + '%'; texto.textContent = `${j.nombre}: ${j.detalle}`;
      if (j.estado === 'corriendo') return setTimeout(tick, 700);
      if (j.estado === 'error') { texto.textContent = `${j.nombre} falló: ${j.error}`; toast(j.error, 'error'); }
      else { toast(`${j.nombre}: listo en ${j.segundos} s`); }
      cargarEstado(); sincSujeto();
    };
    tick();
  };

  cont.replaceChildren(
    h('div', { class: 'caja' },
      h('h2', {}, 'Misma pregunta, dos bases de datos'),
      h('div', { class: 'ctl', style: 'margin-top:.8rem' },
        h('label', { class: 'grande' }, 'Pregunta de negocio', selEsc),
        h('label', {}, 'Datos', selAlc),
        h('label', {}, lblSujeto, inSujeto),
        h('label', {}, 'Repeticiones', reps),
        h('label', { style: 'flex-direction:row;display:flex;align-items:center;gap:.4rem' }, chkMat, 'SQL con tabla curso_similar'),
        h('label', { style: 'flex-direction:row;display:flex;align-items:center;gap:.4rem' }, chkCont, 'Repetir en vivo'),
        btn),
      pregunta),
    h('div', { style: 'margin-top:1rem' }, sal), histBox, h('div', { style: 'margin-top:1rem' }, estadoBox));
  elegir(); pintar(null); pintarHistorial(); cargarEstado();
}
