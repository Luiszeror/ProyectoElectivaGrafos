/* Pestaña de comparación: pantalla partida PostgreSQL | Neo4j con medición en vivo y variables de justicia. */
const HISTORIAL_CMP = [];

async function vistaComparar(cont) {
  const escenarios = await intentar(() => api('/api/admin/comparar/escenarios'));
  if (!escenarios) { cont.replaceChildren(h('p', { class: 'motivo' }, 'No se pudieron cargar las preguntas de prueba. Revisa la conexión y vuelve a abrir esta pestaña.')); return; }
  const est = { esc: escenarios[0], alcance: 'base', corriendo: false, continuo: false, redNeo: null };

  /* ---------- 1. elegir la pregunta (tarjetas agrupadas por dificultad) */
  const tarjetas = h('div', { class: 'niveles', role: 'radiogroup', 'aria-label': 'Pregunta de prueba' });
  const detalle = h('div', { class: 'detalle-pregunta' });
  const pintarTarjetas = () => {
    const grupos = [...new Set(escenarios.map(e => e.nivel))].sort();
    tarjetas.replaceChildren(...grupos.map(n => h('div', { class: 'grupo-nivel' },
      h('h4', {}, `${'●'.repeat(n)}${'○'.repeat(4 - n)}  ${escenarios.find(e => e.nivel === n).nivel_nombre}`),
      h('div', { class: 'opciones' }, escenarios.filter(e => e.nivel === n).map(e =>
        h('button', { type: 'button', role: 'radio', 'aria-checked': e.id === est.esc.id, class: 'opcion' + (e.id === est.esc.id ? ' on' : ''),
          onclick: () => elegir(e.id) }, h('b', {}, e.titulo), h('span', {}, e.que_mide)))))));
    detalle.replaceChildren(h('p', {}, h('b', {}, 'La pregunta: '), est.esc.pregunta),
      h('p', { class: 'dato-et' }, h('b', {}, 'Qué esperar: '), est.esc.que_esperar));
  };

  /* ---------- 2. condiciones de justicia */
  const inSujeto = h('input', { id: 'cmp-sujeto', size: 10, placeholder: 'código' });
  const lblSujeto = h('span', {});
  const selAlc = h('select', {}, h('option', { value: 'base' }, 'Datos base (pocos)'), h('option', { value: 'volumen' }, 'Datos de volumen (muchos)'));
  const reps = h('input', { type: 'number', min: 1, max: 30, value: 8, style: 'width:5rem' });
  const selRed = h('select', {}, h('option', { value: 'igualar' }, 'Igualar a Neo4j Aura (recomendado)'), h('option', { value: 'ninguna' }, 'Sin red: PostgreSQL local'),
    h('option', { value: 'manual' }, 'Elegir milisegundos'));
  const inRed = h('input', { type: 'number', min: 0, max: 1000, value: 50, style: 'width:5.5rem', disabled: true, 'aria-label': 'Milisegundos de red simulada' });
  const redInfo = h('span', { class: 'dato-et' });
  const btnRed = h('button', { type: 'button', class: 'sec small', onclick: () => medirRed() }, 'Medir red hasta Aura');
  const selMetrica = h('select', {}, h('option', { value: 'total' }, 'Tiempo total (lo que espera la app)'), h('option', { value: 'motor' }, 'Solo el motor de la base'));
  const chkCal = h('input', { type: 'checkbox', checked: true });
  const chkAlt = h('input', { type: 'checkbox', checked: true });
  const chkMat = h('input', { type: 'checkbox' });
  const chkCont = h('input', { type: 'checkbox' });
  const btn = h('button', { class: 'grande-btn', onclick: () => correr() }, 'Ejecutar comparación');
  const sal = h('div', {});
  const histBox = h('div', { class: 'hist' });
  const estadoBox = h('div', {});
  const check = (input, texto, ayuda) => h('label', { class: 'check' }, input, h('span', {}, h('b', {}, texto), h('small', {}, ayuda)));

  const medirRed = async () => {
    btnRed.disabled = true; redInfo.textContent = 'Midiendo…';
    const r = await intentar(() => api('/api/admin/comparar/latencia'));
    btnRed.disabled = false;
    if (r) { est.redNeo = r.red_ms; redInfo.textContent = `Aura tarda ${fmtMs(r.red_ms)} ms solo en ir y volver.`; }
    else redInfo.textContent = 'No se pudo medir.';
  };
  const sincRed = () => {
    inRed.disabled = selRed.value !== 'manual';
    redInfo.textContent = selRed.value === 'igualar' ? 'A PostgreSQL se le suma la misma espera de red que tiene Aura.' :
      selRed.value === 'ninguna' ? 'PostgreSQL responde sin espera: gana por estar en tu equipo, no por ser mejor.' : 'Espera simulada que se suma al tiempo total de PostgreSQL.';
  };
  const preset = (justo) => {
    selRed.value = justo ? 'igualar' : 'ninguna'; selMetrica.value = justo ? 'total' : 'motor';
    chkCal.checked = true; chkAlt.checked = true; sincRed();
  };
  selRed.addEventListener('change', sincRed);

  const sincSujeto = async () => {
    if (est.esc.sujeto === 'ninguno') { inSujeto.value = ''; inSujeto.disabled = true; lblSujeto.textContent = 'Sin sujeto'; return; }
    inSujeto.disabled = false;
    lblSujeto.textContent = est.esc.sujeto === 'curso' ? 'Curso' : 'Estudiante';
    try {
      const r = await api(`/api/admin/comparar/muestra?sujeto=${est.esc.sujeto}&alcance=${est.alcance}`);
      inSujeto.value = r.id;
    } catch (e) { inSujeto.value = ''; if (est.alcance === 'volumen') toast(e.message, 'error'); }
  };
  const elegir = (id) => {
    est.esc = escenarios.find(e => e.id === id) || escenarios[0];
    chkMat.disabled = !est.esc.sql_mat; if (!est.esc.sql_mat) chkMat.checked = false;
    pintarTarjetas(); pintar(null); sincSujeto();
  };
  selAlc.addEventListener('change', () => { est.alcance = selAlc.value; sincSujeto(); });

  /* ---------- resultados */
  const mitad = (clase, titulo, version, r, sqlTexto, lang, metrica) => {
    const motor = r ? r.motor : null, total = r ? r.total : null;
    const principal = r ? r[metrica] : null;
    const max = r ? Math.max(...r.muestras) || 1 : 1;
    const red = r ? Math.max(total.mediana - motor.mediana, 0) : 0;
    return h('section', { class: 'mitad ' + clase },
      h('div', { class: 'cab' }, h('h3', {}, titulo), h('span', { class: 'dato-et' }, version || '')),
      r ? [
        h('div', { class: 'medidor' }, h('span', { class: 'dato' }, fmtMs(principal.mediana)),
          h('span', {}, metrica === 'total' ? 'ms en total (mediana)' : 'ms en el motor (mediana)')),
        h('div', { class: 'desglose', title: 'Del tiempo total: cuánto es la base resolviendo y cuánto es esperar la red' },
          h('i', { class: 'seg motor', style: `flex:${Math.max(motor.mediana, .01)}` }), red > 0.05 ? h('i', { class: 'seg red', style: `flex:${red}` }) : null),
        h('p', { class: 'dato-et' }, `Motor ${fmtMs(motor.mediana)} ms` + (red > 0.05 ? ` + red ${fmtMs(red)} ms` : ' · sin red')),
        h('div', { class: 'stats' }, h('span', {}, 'mejor ', h('b', {}, fmtMs(principal.min))), h('span', {}, 'p95 ', h('b', {}, fmtMs(principal.p95))),
          h('span', {}, 'filas ', h('b', {}, r.filas))),
        h('div', { class: 'muestras', title: 'Tiempo total de cada repetición', 'aria-label': 'Tiempos por repetición' },
          r.muestras.map(m => h('i', { style: `height:${Math.max(4, 100 * m / max)}%`, title: fmtMs(m) + ' ms' }))),
        tabla([{ t: 'Código', f: x => x.codigo }, { t: 'Nombre', f: x => x.nombre || '' },
          { t: 'Valor', f: x => { const k = Object.keys(x).find(k => !['codigo', 'nombre', 'porque'].includes(k)); return k ? fmt(x[k], 1) : ''; }, num: 1 }], r.resultado.slice(0, 6), 'La consulta no devolvió filas.'),
      ] : h('p', { class: 'vacio' }, est.corriendo ? 'Midiendo…' : 'Aún no se ha ejecutado.'),
      h('details', {}, h('summary', {}, `Ver consulta (${lang})`), code(sqlTexto)));
  };

  const chips = (j) => h('div', { class: 'chips', 'aria-label': 'Condiciones de esta medición' },
    pill(j.metrica === 'total' ? 'decide el tiempo total' : 'decide solo el motor'),
    pill(j.red_pg_ms > 0 ? `red simulada a PostgreSQL: ${fmtMs(j.red_pg_ms)} ms` : 'PostgreSQL sin red', j.red_pg_ms > 0 ? 'ok' : 'aviso'),
    pill(j.calentar ? 'con calentamiento' : 'sin calentamiento (arranque en frío)'),
    pill(j.intercalar ? 'orden alternado' : 'siempre Neo4j primero'),
    pill(j.variante === 'sql_mat' ? 'SQL con tabla curso_similar' : 'SQL calculado al vuelo'),
    pill(`${j.repeticiones} repeticiones · datos ${j.datos}`));

  const pintar = (res) => {
    if (!res) { sal.replaceChildren(h('div', { class: 'partida' }, mitad('pg', 'PostgreSQL', '', null, est.esc.sql, 'SQL', 'total'), h('div', { class: 'centro' }), mitad('neo', 'Neo4j', '', null, est.esc.cypher, 'Cypher', 'total'))); return; }
    const sqlTexto = res.variante === 'sql_mat' ? est.esc.sql_mat : est.esc.sql;
    const v = res.veredicto, nombre = v.ganador === 'neo4j' ? 'Neo4j' : 'PostgreSQL';
    const noSinc = res.postgres.filas === 0 && res.neo4j.filas > 0;
    const titular = v.empate_tecnico ? `Empate técnico: la diferencia (${fmt(v.veces, 2)}×) es demasiado pequeña para decidir`
      : `${nombre} fue ${fmt(v.veces, 1)}× más rápido`;
    sal.replaceChildren(
      h('div', { class: 'partida' },
        mitad('pg', 'PostgreSQL', estadoGlobal ? estadoGlobal.postgres.version : '', res.postgres, sqlTexto, res.variante === 'sql_mat' ? 'SQL con curso_similar' : 'SQL', v.metrica),
        h('div', { class: 'centro' }, h('span', { class: 'veredicto ' + (res.equivalentes ? 'igual' : 'dif') }, res.equivalentes ? '✓ mismo resultado' : '✗ resultados distintos')),
        mitad('neo', 'Neo4j', estadoGlobal ? estadoGlobal.neo4j.version : '', res.neo4j, est.esc.cypher, 'Cypher', v.metrica)),
      h('div', { class: 'ganador' },
        h('div', { class: 'ganador-txt' }, h('strong', {}, titular), h('span', { class: 'dato-et' }, res.nota_tiempos)),
        chips(res.justicia),
        noSinc ? pill('PostgreSQL parece vacío: pulsa «Sincronizar PostgreSQL» en Datos y volumen', 'mal') : null,
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
    const cuerpo = { ...planCuerpo(), repeticiones: +reps.value || 5, alcance: est.alcance, red_pg: selRed.value, red_pg_ms: +inRed.value || 0,
      metrica: selMetrica.value, calentar: chkCal.checked, intercalar: chkAlt.checked };
    const res = await intentar(() => api('/api/admin/comparar/ejecutar', { method: 'POST', body: cuerpo }));
    est.corriendo = false; btn.disabled = false; btn.textContent = 'Ejecutar comparación';
    if (res) {
      pintar(res);
      const m = res.veredicto.metrica;
      HISTORIAL_CMP.unshift({ hora: new Date().toLocaleTimeString('es-CO'), esc: est.esc.titulo, sujeto: res.sujeto || '—', alcance: est.alcance, pg: res.postgres[m].mediana, neo: res.neo4j[m].mediana,
        ok: res.equivalentes, variante: res.variante, red: res.justicia.red_pg_ms, metrica: m, empate: res.veredicto.empate_tecnico });
      HISTORIAL_CMP.splice(40);
      pintarHistorial();
    }
    if (est.continuo && document.body.contains(btn)) window.__cmpTimer = setTimeout(correr, 1500);
  };
  chkCont.addEventListener('change', () => { est.continuo = chkCont.checked; if (est.continuo) correr(); else clearTimeout(window.__cmpTimer); });

  const pintarHistorial = () => histBox.replaceChildren(h('div', { class: 'caja' }, h('h3', {}, 'Mediciones de esta sesión'),
    tabla([{ t: 'Hora', f: x => x.hora }, { t: 'Pregunta', f: x => x.esc }, { t: 'Sujeto', f: x => x.sujeto }, { t: 'Datos', f: x => x.alcance === 'volumen' ? 'volumen' : 'base' },
      { t: 'SQL', f: x => x.variante === 'sql_mat' ? 'materializado' : 'al vuelo' }, { t: 'Red PG', f: x => x.red ? fmtMs(x.red) + ' ms' : 'ninguna' },
      { t: 'Tiempo', f: x => x.metrica === 'total' ? 'total' : 'motor' },
      { t: 'PostgreSQL ms', f: x => fmtMs(x.pg), num: 1 }, { t: 'Neo4j ms', f: x => fmtMs(x.neo), num: 1 },
      { t: 'Más rápido', f: x => x.empate ? 'empate técnico' : (x.pg < x.neo ? 'PostgreSQL' : 'Neo4j') + ` ${fmt(Math.max(x.pg, x.neo) / Math.max(Math.min(x.pg, x.neo), 0.001), 1)}×` },
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
      h('p', { class: 'dato-et', style: 'max-width:70ch' }, 'Elige una pregunta, ajusta las condiciones para que la comparación sea justa y pulsa «Ejecutar». Ambas bases responden exactamente lo mismo; aquí se mide cuánto tarda cada una.'),
      h('h3', { class: 'paso' }, '1. Elige qué quieres preguntar'), tarjetas, detalle),
    h('div', { class: 'caja' },
      h('h3', { class: 'paso' }, '2. Haz la comparación justa'),
      h('p', { class: 'dato-et', style: 'max-width:70ch' }, 'PostgreSQL corre en tu equipo y Neo4j Aura está en internet, así que sin ajustes PostgreSQL siempre parecería ganar solo por no tener red. Estas opciones iguala las condiciones.'),
      h('div', { class: 'fila', style: 'margin:.6rem 0' },
        h('button', { type: 'button', class: 'sec small', onclick: () => preset(true) }, 'Condiciones justas (recomendado)'),
        h('button', { type: 'button', class: 'sec small', onclick: () => preset(false) }, 'Solo motores, sin red')),
      h('div', { class: 'justicia' },
        h('div', { class: 'grupo' }, h('h4', {}, 'Red'),
          h('label', {}, 'Red de PostgreSQL', selRed), h('label', { style: 'flex-direction:row;display:flex;gap:.4rem;align-items:center' }, 'Espera manual', inRed, 'ms'),
          h('div', { class: 'fila' }, btnRed, redInfo)),
        h('div', { class: 'grupo' }, h('h4', {}, 'Qué se compara'),
          h('label', {}, 'Tiempo que decide', selMetrica), h('label', {}, 'Cantidad de datos', selAlc),
          h('label', {}, lblSujeto, inSujeto)),
        h('div', { class: 'grupo' }, h('h4', {}, 'Cómo se mide'),
          h('label', {}, 'Repeticiones', reps),
          check(chkCal, 'Calentar antes de medir', 'Una pasada previa que no cuenta; quita el efecto de «primera vez».'),
          check(chkAlt, 'Alternar quién va primero', 'Así el cansancio del equipo no favorece a una sola base.'),
          check(chkMat, 'SQL con tabla curso_similar', 'Le da a PostgreSQL la similitud ya calculada, como las relaciones SIMILAR_A del grafo.'))),
      h('div', { class: 'fila', style: 'margin-top:.8rem' }, btn, check(chkCont, 'Repetir en vivo', 'Vuelve a medir cada pocos segundos.'))),
    h('div', { style: 'margin-top:1rem' }, sal), histBox, h('div', { style: 'margin-top:1rem' }, estadoBox));
  sincRed(); elegir(est.esc.id); pintarHistorial(); cargarEstado();
}
