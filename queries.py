"""Consultas Cypher de la aplicación.

Regla: el texto de cada consulta es fijo; los valores viajan SIEMPRE como parámetros ($x).
Así nadie puede "colar" Cypher desde un formulario y las pruebas pueden reconocer cada consulta.
"""

# ------------------------------------------------------------------ generales
PING = "RETURN 1 AS ok"
CONTEO_ETIQUETAS = "MATCH (n) UNWIND labels(n) AS etiqueta RETURN etiqueta, count(*) AS total"
CONTEO_RELACIONES = "MATCH ()-[r]->() RETURN type(r) AS tipo, count(*) AS total"

# ------------------------------------------------------------------ acceso del estudiante
EST_POR_ID = "MATCH (e:Estudiante {id: $id}) RETURN e.id AS id, e.nombre AS nombre"
EST_DEMO = """MATCH (e:Estudiante) WHERE e.sintetico IS NULL
RETURN e.id AS id, e.nombre AS nombre ORDER BY size(e.id), e.id LIMIT 24"""
EST_MAX_ID = """MATCH (e:Estudiante) WHERE e.id =~ 'E[0-9]+'
RETURN coalesce(max(toInteger(substring(e.id, 1))), 0) AS maximo"""
EST_CREAR = """CREATE (e:Estudiante {id: $id, nombre: $nombre, semestre: $semestre})
WITH e MATCH (p:Programa {codigo: $programa})
CREATE (e)-[:ESTUDIA_EN {anio_ingreso: $anio}]->(p)
RETURN e.id AS id"""
LISTA_PROGRAMAS = """MATCH (p:Programa) WHERE $todos OR p.sintetico IS NULL
OPTIONAL MATCH (p)-[:PERTENECE_A]->(f:Facultad)
RETURN p.codigo AS codigo, p.nombre AS nombre, f.codigo AS facultad
ORDER BY size(p.codigo), p.codigo"""
LISTA_AREAS = """MATCH (a:Area) WHERE $todos OR a.sintetico IS NULL
RETURN a.codigo AS codigo, a.nombre AS nombre ORDER BY size(a.codigo), a.codigo"""
LISTA_SEDES = """MATCH (s:Sede) WHERE $todos OR s.sintetico IS NULL
RETURN s.codigo AS codigo, s.nombre AS nombre ORDER BY size(s.codigo), s.codigo"""
LISTA_FACULTADES = """MATCH (f:Facultad) WHERE $todos OR f.sintetico IS NULL
RETURN f.codigo AS codigo, f.nombre AS nombre ORDER BY size(f.codigo), f.codigo"""
PROGRAMA_SEDES_TODAS = """MATCH (p:Programa)-[:SE_OFRECE_EN]->(s:Sede)
RETURN p.codigo AS programa, s.codigo AS sede"""

# ------------------------------------------------------------------ perfil, historial, intereses
PERFIL = """MATCH (e:Estudiante {id: $id})
OPTIONAL MATCH (e)-[r:ESTUDIA_EN]->(p:Programa)
OPTIONAL MATCH (p)-[:PERTENECE_A]->(f:Facultad)
RETURN e.id AS id, e.nombre AS nombre, e.semestre AS semestre, r.anio_ingreso AS anio_ingreso,
       p.codigo AS programa, p.nombre AS programa_nombre,
       f.codigo AS facultad, f.nombre AS facultad_nombre"""
PROGRAMA_SEDES = """MATCH (p:Programa {codigo: $programa})-[:SE_OFRECE_EN]->(s:Sede)
RETURN s.codigo AS codigo, s.nombre AS nombre ORDER BY s.codigo"""
PROGRAMA_OBLIGATORIOS = """MATCH (c:Curso)-[r:INCLUIDO_EN {es_obligatorio: true}]->(p:Programa {codigo: $programa})
RETURN c.codigo AS curso, c.nombre AS nombre, r.semestre_sugerido AS semestre
ORDER BY r.semestre_sugerido, c.codigo"""
HISTORIAL = """MATCH (:Estudiante {id: $id})-[h:HA_CURSADO]->(c:Curso)
RETURN c.codigo AS curso, c.nombre AS nombre, c.tipo AS tipo, c.nivel AS nivel,
       h.periodo AS periodo, h.nota AS nota, h.estado AS estado
ORDER BY h.periodo, c.codigo"""
INTERESES = """MATCH (:Estudiante {id: $id})-[i:INTERESADO_EN]->(a:Area)
RETURN a.codigo AS area, a.nombre AS nombre, i.nivel AS nivel ORDER BY i.nivel DESC, a.codigo"""
INTERESES_BORRAR = "MATCH (:Estudiante {id: $id})-[i:INTERESADO_EN]->(:Area) DELETE i"
INTERESES_GUARDAR = """MATCH (e:Estudiante {id: $id})
UNWIND $items AS it
MATCH (a:Area {codigo: it.area})
MERGE (e)-[r:INTERESADO_EN]->(a)
SET r.nivel = it.nivel"""

# ------------------------------------------------------------------ catálogo (compartido)
CAT_CURSOS = """MATCH (c:Curso) WHERE $todos OR c.sintetico IS NULL
RETURN c.codigo AS codigo, c.nombre AS nombre, c.tipo AS tipo, c.nivel AS nivel,
       coalesce(c.sintetico, false) AS sintetico
ORDER BY c.codigo"""
CAT_AREAS = """MATCH (c:Curso)-[t:TRATA_DE]->(a:Area) WHERE $todos OR c.sintetico IS NULL
RETURN c.codigo AS curso, a.codigo AS area, a.nombre AS nombre, t.peso AS peso ORDER BY a.codigo"""
CAT_PROGRAMAS = """MATCH (c:Curso)-[r:INCLUIDO_EN]->(p:Programa) WHERE $todos OR c.sintetico IS NULL
RETURN c.codigo AS curso, p.codigo AS programa, p.nombre AS nombre,
       r.semestre_sugerido AS semestre, r.es_obligatorio AS obligatorio ORDER BY p.codigo"""
CAT_SEDES = """MATCH (c:Curso)-[r:SE_DICTA_EN {periodo: $periodo}]->(s:Sede) WHERE $todos OR c.sintetico IS NULL
RETURN c.codigo AS curso, s.codigo AS sede, s.nombre AS nombre, r.cupos AS cupos ORDER BY s.codigo"""
CAT_PRERREQ = """MATCH (c:Curso)-[r:REQUIERE]->(q:Curso) WHERE $todos OR c.sintetico IS NULL
RETURN c.codigo AS curso, q.codigo AS requisito, q.nombre AS nombre, r.tipo AS tipo ORDER BY q.codigo"""
CAT_DOCENTES = """MATCH (d:Docente)-[r:DICTA {periodo: $periodo}]->(c:Curso) WHERE $todos OR c.sintetico IS NULL
RETURN c.codigo AS curso, d.id AS docente, d.nombre AS nombre, r.grupo AS grupo ORDER BY d.id"""
OCUPACION = """MATCH (:Estudiante)-[h:HA_CURSADO {estado: 'EN_CURSO', periodo: $periodo}]->(c:Curso)
RETURN c.codigo AS curso, count(*) AS ocupados"""

# ------------------------------------------------------------------ inscripción
INSCRIBIR = """MATCH (e:Estudiante {id: $id}), (c:Curso {codigo: $curso})
MERGE (e)-[h:HA_CURSADO {periodo: $periodo}]->(c)
SET h.estado = 'EN_CURSO'
REMOVE h.nota
RETURN h.estado AS estado"""
RETIRAR = """MATCH (:Estudiante {id: $id})-[h:HA_CURSADO {estado: 'EN_CURSO', periodo: $periodo}]->(:Curso {codigo: $curso})
DELETE h
RETURN count(*) AS borradas"""

# ------------------------------------------------------------------ recomendaciones (versión del portal)
# Los tres filtros se repiten a propósito en cada consulta para que cada una se pueda leer sola:
#  1) no recomendar lo aprobado ni lo que ya cursa; 2) prerrequisitos aprobados.
REC_HISTORIAL = """MATCH (e:Estudiante {id: $id})-[:HA_CURSADO {estado: 'APROBADO'}]->(base:Curso)-[s:SIMILAR_A]->(rec:Curso)
WHERE NOT EXISTS { MATCH (e)-[h:HA_CURSADO]->(rec) WHERE h.estado IN ['APROBADO', 'EN_CURSO'] }
  AND NOT EXISTS {
    MATCH (rec)-[:REQUIERE {tipo: 'PRERREQUISITO'}]->(pre:Curso)
    WHERE NOT (e)-[:HA_CURSADO {estado: 'APROBADO'}]->(pre)
  }
RETURN rec.codigo AS codigo, rec.nombre AS nombre, sum(s.peso) AS puntaje,
       collect(DISTINCT base.nombre) AS porque
ORDER BY puntaje DESC, codigo
LIMIT 20"""

REC_OTROS_PROGRAMAS = """MATCH (e:Estudiante {id: $id})-[:ESTUDIA_EN]->(p:Programa)
MATCH (e)-[:HA_CURSADO {estado: 'APROBADO'}]->(base:Curso)-[s:SIMILAR_A]->(rec:Curso)
WHERE NOT (rec)-[:INCLUIDO_EN]->(p)
  AND NOT EXISTS { MATCH (e)-[h:HA_CURSADO]->(rec) WHERE h.estado IN ['APROBADO', 'EN_CURSO'] }
  AND NOT EXISTS {
    MATCH (rec)-[:REQUIERE {tipo: 'PRERREQUISITO'}]->(pre:Curso)
    WHERE NOT (e)-[:HA_CURSADO {estado: 'APROBADO'}]->(pre)
  }
RETURN rec.codigo AS codigo, rec.nombre AS nombre, sum(s.peso) AS puntaje,
       collect(DISTINCT base.nombre) AS porque
ORDER BY puntaje DESC, codigo
LIMIT 20"""

REC_INTERESES = """MATCH (e:Estudiante {id: $id})-[i:INTERESADO_EN]->(a:Area)<-[t:TRATA_DE]-(c:Curso)
WHERE NOT EXISTS { MATCH (e)-[h:HA_CURSADO]->(c) WHERE h.estado IN ['APROBADO', 'EN_CURSO'] }
  AND NOT EXISTS {
    MATCH (c)-[:REQUIERE {tipo: 'PRERREQUISITO'}]->(pre:Curso)
    WHERE NOT (e)-[:HA_CURSADO {estado: 'APROBADO'}]->(pre)
  }
RETURN c.codigo AS codigo, c.nombre AS nombre, sum(i.nivel * t.peso) AS puntaje,
       collect(DISTINCT a.nombre) AS porque
ORDER BY puntaje DESC, codigo
LIMIT 20"""

REC_SIMILARES = """MATCH (e:Estudiante {id: $id})-[:HA_CURSADO {estado: 'APROBADO'}]->(c:Curso)<-[:HA_CURSADO {estado: 'APROBADO'}]-(otro:Estudiante)
WHERE otro <> e
WITH e, otro, count(DISTINCT c) AS compartidos
MATCH (otro)-[:HA_CURSADO {estado: 'APROBADO'}]->(rec:Curso)
WHERE NOT EXISTS { MATCH (e)-[h:HA_CURSADO]->(rec) WHERE h.estado IN ['APROBADO', 'EN_CURSO'] }
  AND NOT EXISTS {
    MATCH (rec)-[:REQUIERE {tipo: 'PRERREQUISITO'}]->(pre:Curso)
    WHERE NOT (e)-[:HA_CURSADO {estado: 'APROBADO'}]->(pre)
  }
RETURN rec.codigo AS codigo, rec.nombre AS nombre, sum(compartidos) AS puntaje,
       count(DISTINCT otro) AS porque
ORDER BY puntaje DESC, codigo
LIMIT 20"""

AREAS_FORTALEZAS = """MATCH (:Estudiante {id: $id})-[h:HA_CURSADO {estado: 'APROBADO'}]->(c:Curso)-[:TRATA_DE]->(a:Area)
RETURN a.codigo AS area, a.nombre AS nombre, count(DISTINCT c) AS cursos, avg(h.nota) AS promedio
ORDER BY cursos DESC, area"""

AREAS_EXPLORAR = """MATCH (e:Estudiante {id: $id})-[:HA_CURSADO {estado: 'APROBADO'}]->(:Curso)-[:TRATA_DE]->(a1:Area)
WITH e, collect(DISTINCT a1) AS propias
MATCH (a:Area)<-[:TRATA_DE]-(c:Curso)-[:TRATA_DE]->(a2:Area)
WHERE a IN propias AND NOT a2 IN propias AND NOT (e)-[:INTERESADO_EN]->(a2)
RETURN a2.codigo AS area, a2.nombre AS nombre, count(DISTINCT c) AS cursos_puente,
       collect(DISTINCT a.nombre) AS desde
ORDER BY cursos_puente DESC, area
LIMIT 8"""

RED_ESTUDIANTE = """MATCH p = (e:Estudiante {id: $id})-[*1..2]->(x)
WHERE all(r IN relationships(p) WHERE type(r) IN ['HA_CURSADO', 'ESTUDIA_EN', 'INTERESADO_EN', 'TRATA_DE', 'REQUIERE', 'INCLUIDO_EN'])
UNWIND relationships(p) AS r
WITH DISTINCT r, startNode(r) AS a, endNode(r) AS b
LIMIT $limite
RETURN elementId(r) AS rid, type(r) AS tipo, properties(r) AS rp,
       elementId(a) AS aid, labels(a)[0] AS al, properties(a) AS ap,
       elementId(b) AS bid, labels(b)[0] AS bl, properties(b) AS bp"""

# ------------------------------------------------------------------ gestión: docentes
DOC_LISTA = """MATCH (d:Docente) WHERE $todos OR d.sintetico IS NULL
OPTIONAL MATCH (d)-[r:DICTA]->(c:Curso)
WITH d, collect(CASE WHEN c IS NULL THEN NULL ELSE {curso: c.codigo, nombre: c.nombre, periodo: r.periodo, grupo: r.grupo} END) AS cursos
RETURN d.id AS id, d.nombre AS nombre, cursos
ORDER BY size(id), id
LIMIT 300"""
DOC_MAX_ID = """MATCH (d:Docente) WHERE d.id =~ 'D[0-9]+'
RETURN coalesce(max(toInteger(substring(d.id, 1))), 0) AS maximo"""
DOC_EXISTE = "MATCH (d:Docente {id: $id}) RETURN d.id AS id"
DOC_CREAR = "CREATE (d:Docente {id: $id, nombre: $nombre}) RETURN d.id AS id"
DOC_ACTUALIZAR = "MATCH (d:Docente {id: $id}) SET d.nombre = $nombre RETURN d.id AS id"
DOC_BORRAR = "MATCH (d:Docente {id: $id}) DETACH DELETE d"
DOC_ASIGNAR = """MATCH (d:Docente {id: $id}), (c:Curso {codigo: $curso})
MERGE (d)-[r:DICTA {periodo: $periodo, grupo: $grupo}]->(c)
RETURN d.id AS id"""
DOC_DESASIGNAR = """MATCH (:Docente {id: $id})-[r:DICTA {periodo: $periodo, grupo: $grupo}]->(:Curso {codigo: $curso})
DELETE r"""

# ------------------------------------------------------------------ gestión: cursos
CUR_MAX_CODIGO = """MATCH (c:Curso) WHERE c.codigo =~ 'C[0-9]+'
RETURN coalesce(max(toInteger(substring(c.codigo, 1))), 0) AS maximo"""
CUR_EXISTE = "MATCH (c:Curso {codigo: $codigo}) RETURN c.codigo AS codigo"
CUR_CREAR = "CREATE (c:Curso {codigo: $codigo, nombre: $nombre, tipo: $tipo, nivel: $nivel})"
CUR_ACTUALIZAR = "MATCH (c:Curso {codigo: $codigo}) SET c.nombre = $nombre, c.tipo = $tipo, c.nivel = $nivel"
CUR_LIMPIAR_AREAS = "MATCH (:Curso {codigo: $codigo})-[r:TRATA_DE]->(:Area) DELETE r"
CUR_LIMPIAR_PROGRAMAS = "MATCH (:Curso {codigo: $codigo})-[r:INCLUIDO_EN]->(:Programa) DELETE r"
CUR_LIMPIAR_REQUISITOS = "MATCH (:Curso {codigo: $codigo})-[r:REQUIERE]->(:Curso) DELETE r"
CUR_LIMPIAR_SEDES = "MATCH (:Curso {codigo: $codigo})-[r:SE_DICTA_EN {periodo: $periodo}]->(:Sede) DELETE r"
CUR_LIMPIAR_DOCENTES = "MATCH (:Docente)-[r:DICTA {periodo: $periodo}]->(:Curso {codigo: $codigo}) DELETE r"
CUR_PONER_AREAS = """MATCH (c:Curso {codigo: $codigo})
UNWIND $items AS it
MATCH (a:Area {codigo: it.id})
MERGE (c)-[r:TRATA_DE]->(a)
SET r.peso = it.peso"""
CUR_PONER_PROGRAMAS = """MATCH (c:Curso {codigo: $codigo})
UNWIND $items AS it
MATCH (p:Programa {codigo: it.id})
MERGE (c)-[r:INCLUIDO_EN]->(p)
SET r.semestre_sugerido = it.semestre, r.es_obligatorio = it.obligatorio"""
CUR_PONER_REQUISITOS = """MATCH (c:Curso {codigo: $codigo})
UNWIND $items AS it
MATCH (q:Curso {codigo: it.id})
MERGE (c)-[r:REQUIERE]->(q)
SET r.tipo = it.tipo"""
CUR_PONER_SEDES = """MATCH (c:Curso {codigo: $codigo})
UNWIND $items AS it
MATCH (s:Sede {codigo: it.id})
MERGE (c)-[r:SE_DICTA_EN {periodo: $periodo}]->(s)
SET r.cupos = it.cupos"""
CUR_PONER_DOCENTES = """MATCH (c:Curso {codigo: $codigo})
UNWIND $items AS it
MATCH (d:Docente {id: it.id})
MERGE (d)-[:DICTA {periodo: $periodo, grupo: it.grupo}]->(c)"""
CUR_CICLO = """MATCH p = (b:Curso {codigo: $requisito})-[:REQUIERE*1..20 {tipo: 'PRERREQUISITO'}]->(a:Curso {codigo: $curso})
RETURN count(p) AS n"""
CUR_USO = """MATCH (c:Curso {codigo: $codigo})
OPTIONAL MATCH (c)<-[h:HA_CURSADO]-(:Estudiante)
WITH c, count(h) AS matriculas
OPTIONAL MATCH (c)<-[:REQUIERE]-(d:Curso)
RETURN matriculas, count(DISTINCT d) AS dependientes"""
CUR_BORRAR = "MATCH (c:Curso {codigo: $codigo}) DETACH DELETE c"

# SIMILAR_A: relación derivada (cursos que comparten áreas). Peso = número de áreas en común.
SIM_BORRAR_UNO = "MATCH (:Curso {codigo: $codigo})-[s:SIMILAR_A]-(:Curso) DELETE s"
SIM_CONSTRUIR_UNO = """MATCH (c:Curso {codigo: $codigo})-[:TRATA_DE]->(a:Area)<-[:TRATA_DE]-(o:Curso)
WHERE o <> c
WITH c, o, count(a) AS comunes
MERGE (c)-[s1:SIMILAR_A]->(o) SET s1.peso = comunes, s1.criterio = 'area_comun'
MERGE (o)-[s2:SIMILAR_A]->(c) SET s2.peso = comunes, s2.criterio = 'area_comun'"""
SIM_BORRAR_TODAS = "MATCH ()-[s:SIMILAR_A]->() DELETE s"
SIM_CONSTRUIR_TODAS = """MATCH (c1:Curso)-[:TRATA_DE]->(a:Area)<-[:TRATA_DE]-(c2:Curso)
WHERE c1.codigo < c2.codigo
WITH c1, c2, count(a) AS comunes
MERGE (c1)-[s1:SIMILAR_A]->(c2) SET s1.peso = comunes, s1.criterio = 'area_comun'
MERGE (c2)-[s2:SIMILAR_A]->(c1) SET s2.peso = comunes, s2.criterio = 'area_comun'
RETURN count(*) AS pares"""

# ------------------------------------------------------------------ gestión: catálogos (Facultad, Programa, Sede, Area)
ETIQUETAS_CATALOGO = ("Facultad", "Programa", "Sede", "Area")
CATALOGO_EXISTE = {e: f"MATCH (n:{e} {{codigo: $codigo}}) RETURN n.codigo AS codigo" for e in ETIQUETAS_CATALOGO}
CATALOGO_CREAR = {e: f"CREATE (n:{e} {{codigo: $codigo, nombre: $nombre}})" for e in ETIQUETAS_CATALOGO}
CATALOGO_ACTUALIZAR = {e: f"MATCH (n:{e} {{codigo: $codigo}}) SET n.nombre = $nombre" for e in ETIQUETAS_CATALOGO}
CATALOGO_USO = {e: f"MATCH (n:{e} {{codigo: $codigo}}) OPTIONAL MATCH (n)--(x) RETURN count(x) AS usos"
                for e in ETIQUETAS_CATALOGO}
CATALOGO_BORRAR = {e: f"MATCH (n:{e} {{codigo: $codigo}}) DETACH DELETE n" for e in ETIQUETAS_CATALOGO}
PROG_LIMPIAR_FACULTAD = "MATCH (:Programa {codigo: $codigo})-[r:PERTENECE_A]->(:Facultad) DELETE r"
PROG_PONER_FACULTAD = """MATCH (p:Programa {codigo: $codigo}), (f:Facultad {codigo: $facultad})
MERGE (p)-[:PERTENECE_A]->(f)"""
PROG_LIMPIAR_SEDES = "MATCH (:Programa {codigo: $codigo})-[r:SE_OFRECE_EN]->(:Sede) DELETE r"
PROG_PONER_SEDES = """MATCH (p:Programa {codigo: $codigo})
UNWIND $sedes AS s
MATCH (x:Sede {codigo: s})
MERGE (p)-[:SE_OFRECE_EN]->(x)"""

# ------------------------------------------------------------------ gestión: matrículas y notas
MATRICULAS = """MATCH (e:Estudiante)-[h:HA_CURSADO]->(c:Curso)
WHERE ($estado = '' OR h.estado = $estado)
  AND ($curso = '' OR c.codigo = $curso)
  AND ($q = '' OR toLower(e.nombre) CONTAINS toLower($q) OR toLower(e.id) CONTAINS toLower($q))
  AND ($todos OR e.sintetico IS NULL)
RETURN e.id AS estudiante, e.nombre AS nombre, c.codigo AS curso, c.nombre AS curso_nombre,
       h.periodo AS periodo, h.estado AS estado, h.nota AS nota
ORDER BY h.periodo DESC, e.id
LIMIT 200"""
MATRICULA_PONER_NOTA = """MATCH (:Estudiante {id: $est})-[h:HA_CURSADO {periodo: $periodo}]->(:Curso {codigo: $curso})
SET h.nota = $nota, h.estado = $estado
RETURN h.estado AS estado"""

# ------------------------------------------------------------------ modelos (introspección)
NEO_CONSTRAINTS = """SHOW CONSTRAINTS YIELD name, type, entityType, labelsOrTypes, properties
RETURN name, type, entityType, labelsOrTypes, properties ORDER BY name"""
NEO_INDEXES = """SHOW INDEXES YIELD name, type, entityType, labelsOrTypes, properties, state
RETURN name, type, entityType, labelsOrTypes, properties, state ORDER BY name"""
NEO_MUESTRA_NODO = {
    e: f"MATCH (n:{e}) WHERE n.sintetico IS NULL RETURN properties(n) AS props LIMIT 1" for e in
    ("Estudiante", "Docente", "Curso", "Programa", "Facultad", "Sede", "Area")
}
def neo_muestra_rel(tipo: str) -> str:
    """Una relación de ejemplo de ese tipo. El tipo va en el patrón (no en un WHERE type(r) = $t) para que
    Neo4j use el índice de tipos de relación en vez de recorrer todas las relaciones del grafo."""
    assert tipo.replace("_", "").isalnum(), tipo
    return (f"MATCH (a)-[r:`{tipo}`]->(b) WHERE a.sintetico IS NULL "
            "RETURN properties(r) AS props, labels(a)[0] AS de, labels(b)[0] AS a LIMIT 1")


NEO_EJEMPLO_MATRICULA = """MATCH (e:Estudiante {id: $est})-[h:HA_CURSADO]->(c:Curso {codigo: $curso})
RETURN e.id AS estudiante, c.codigo AS curso, properties(h) AS relacion ORDER BY h.periodo LIMIT 1"""
NEO_MATRICULA_REAL = """MATCH (e:Estudiante)-[h:HA_CURSADO {estado: 'APROBADO'}]->(c:Curso)
WHERE e.sintetico IS NULL
RETURN e.id AS estudiante, c.codigo AS curso LIMIT 1"""

# ------------------------------------------------------------------ comparación: muestras
MUESTRA_EST_BASE = """MATCH (e:Estudiante)-[h:HA_CURSADO]->(:Curso) WHERE e.sintetico IS NULL
RETURN e.id AS id, count(h) AS n ORDER BY n DESC, id LIMIT 1"""
MUESTRA_EST_VOLUMEN = """MATCH (e:Estudiante)-[h:HA_CURSADO]->(:Curso) WHERE e.sintetico = true
WITH e, count(h) AS n ORDER BY n DESC, e.id LIMIT 1
RETURN e.id AS id, n"""
MUESTRA_EST_AZAR = """MATCH (e:Estudiante) WHERE $sintetico = (e.sintetico IS NOT NULL)
WITH e, rand() AS r ORDER BY r LIMIT 1
RETURN e.id AS id"""
MUESTRA_CURSO_PROFUNDO = """MATCH p = (c:Curso)-[:REQUIERE*1..10 {tipo: 'PRERREQUISITO'}]->(:Curso)
WHERE $sintetico = (c.sintetico IS NOT NULL)
RETURN c.codigo AS id, max(length(p)) AS prof ORDER BY prof DESC, id LIMIT 1"""

# ------------------------------------------------------------------ extracción para sincronizar con PostgreSQL
EXTRAER = {
    "facultad": "MATCH (n:Facultad) RETURN n.codigo AS a, n.nombre AS b",
    "sede": "MATCH (n:Sede) RETURN n.codigo AS a, n.nombre AS b",
    "area": "MATCH (n:Area) RETURN n.codigo AS a, n.nombre AS b",
    "docente": "MATCH (n:Docente) RETURN n.id AS a, n.nombre AS b",
    "curso": "MATCH (n:Curso) RETURN n.codigo AS a, n.nombre AS b, n.tipo AS c, n.nivel AS d",
    "programa": """MATCH (n:Programa) OPTIONAL MATCH (n)-[:PERTENECE_A]->(f:Facultad)
RETURN n.codigo AS a, n.nombre AS b, f.codigo AS c""",
    "estudiante": """MATCH (n:Estudiante) OPTIONAL MATCH (n)-[r:ESTUDIA_EN]->(p:Programa)
RETURN n.id AS a, n.nombre AS b, n.semestre AS c, p.codigo AS d, r.anio_ingreso AS e""",
    "programa_sede": "MATCH (p:Programa)-[:SE_OFRECE_EN]->(s:Sede) RETURN p.codigo AS a, s.codigo AS b",
    "curso_programa": """MATCH (c:Curso)-[r:INCLUIDO_EN]->(p:Programa)
RETURN c.codigo AS a, p.codigo AS b, r.semestre_sugerido AS c, r.es_obligatorio AS d""",
    "curso_area": "MATCH (c:Curso)-[r:TRATA_DE]->(a:Area) RETURN c.codigo AS a, a.codigo AS b, r.peso AS c",
    "prerrequisito": "MATCH (c:Curso)-[r:REQUIERE]->(q:Curso) RETURN c.codigo AS a, q.codigo AS b, r.tipo AS c",
    "curso_sede": """MATCH (c:Curso)-[r:SE_DICTA_EN]->(s:Sede)
RETURN c.codigo AS a, s.codigo AS b, r.periodo AS c, r.cupos AS d""",
    "dictado": """MATCH (d:Docente)-[r:DICTA]->(c:Curso)
RETURN d.id AS a, c.codigo AS b, r.periodo AS c, r.grupo AS d""",
    "interes_estudiante": """MATCH (e:Estudiante)-[r:INTERESADO_EN]->(a:Area)
RETURN e.id AS a, a.codigo AS b, r.nivel AS c""",
    "matricula": """MATCH (e:Estudiante)-[h:HA_CURSADO]->(c:Curso)
RETURN e.id AS a, c.codigo AS b, h.periodo AS c, h.nota AS d, h.estado AS e""",
}

# ------------------------------------------------------------------ explorador del grafo (administrador)
GRAFO_GENERAL = """MATCH (a)-[r]->(b)
WHERE ($todos OR a.sintetico IS NULL) AND type(r) IN $tipos
WITH r, a, b LIMIT $limite
RETURN elementId(r) AS rid, type(r) AS tipo, properties(r) AS rp,
       elementId(a) AS aid, labels(a)[0] AS al, properties(a) AS ap,
       elementId(b) AS bid, labels(b)[0] AS bl, properties(b) AS bp"""
GRAFO_VECINDAD = """MATCH (n)-[r]-(m) WHERE elementId(n) = $eid AND type(r) IN $tipos
WITH r, startNode(r) AS a, endNode(r) AS b LIMIT $limite
RETURN elementId(r) AS rid, type(r) AS tipo, properties(r) AS rp,
       elementId(a) AS aid, labels(a)[0] AS al, properties(a) AS ap,
       elementId(b) AS bid, labels(b)[0] AS bl, properties(b) AS bp"""
