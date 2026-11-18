"""Escenarios de comparación: la MISMA pregunta de negocio escrita en Cypher y en SQL.

Cada escenario trae el Cypher (el mismo del portal cuando existe), el SQL equivalente y, cuando
aplica, una variante de SQL que usa la tabla materializada `curso_similar` (el equivalente a las
relaciones SIMILAR_A precalculadas del grafo). Así se compara en condiciones justas.

Para que los resultados sean comparables, el SQL ordena con COLLATE "C" (igual que Cypher, que
compara cadenas por punto de código) y todos los empates se resuelven por código.
"""
import queries as Q

# Filtros comunes del SQL de recomendación: no repetir lo aprobado/en curso y exigir prerrequisitos aprobados.
_FILTROS_REC = """
  AND NOT EXISTS (SELECT 1 FROM matricula m WHERE m.id_estudiante = %(id)s AND m.codigo_curso = r.codigo
                  AND m.estado IN ('APROBADO', 'EN_CURSO'))
  AND NOT EXISTS (SELECT 1 FROM prerrequisito p WHERE p.codigo_curso = r.codigo AND p.tipo = 'PRERREQUISITO'
                  AND NOT EXISTS (SELECT 1 FROM matricula m2 WHERE m2.id_estudiante = %(id)s
                                  AND m2.codigo_curso = p.codigo_requisito AND m2.estado = 'APROBADO'))"""

_REC_BASE = """SELECT r.codigo, r.nombre, SUM(s.peso)::float8 AS puntaje
FROM (SELECT DISTINCT codigo_curso FROM matricula WHERE id_estudiante = %(id)s AND estado = 'APROBADO') ap
JOIN __SIMILAR__ s ON s.codigo_a = ap.codigo_curso
JOIN curso r ON r.codigo = s.codigo_b
WHERE TRUE__EXTRA____FILTROS__
GROUP BY r.codigo, r.nombre
ORDER BY puntaje DESC, r.codigo COLLATE "C"
LIMIT 20"""

_SIMILAR_AL_VUELO = """(SELECT a.codigo_curso AS codigo_a, b.codigo_curso AS codigo_b, COUNT(*) AS peso
        FROM curso_area a JOIN curso_area b ON a.id_area = b.id_area AND a.codigo_curso <> b.codigo_curso
        WHERE a.codigo_curso IN (SELECT codigo_curso FROM matricula
                                 WHERE id_estudiante = %(id)s AND estado = 'APROBADO')
        GROUP BY a.codigo_curso, b.codigo_curso)"""


def _rec(similar: str, extra: str = "") -> str:
    return (_REC_BASE.replace("__SIMILAR__", similar).replace("__EXTRA__", extra)
            .replace("__FILTROS__", _FILTROS_REC))


_EXTRA_OTRO_PROGRAMA = """
  AND EXISTS (SELECT 1 FROM estudiante x WHERE x.id_estudiante = %(id)s AND x.id_programa IS NOT NULL)
  AND NOT EXISTS (SELECT 1 FROM curso_programa cp WHERE cp.codigo_curso = r.codigo
                  AND cp.id_programa = (SELECT id_programa FROM estudiante WHERE id_estudiante = %(id)s))"""

ESCENARIOS = [
    {
        "id": "rec_historial",
        "titulo": "Recomendar cursos por historial",
        "tema": "Recomendación",
        "pregunta": "¿Qué cursos le recomendamos a un estudiante según lo que ya aprobó (cursos similares), "
                    "sin repetir lo cursado y respetando prerrequisitos?",
        "sujeto": "estudiante",
        "cypher": Q.REC_HISTORIAL,
        "sql": _rec(_SIMILAR_AL_VUELO),
        "sql_mat": _rec("curso_similar"),
        "cols": ["codigo", "puntaje"],
    },
    {
        "id": "rec_intereses",
        "titulo": "Recomendar cursos por intereses",
        "tema": "Recomendación",
        "pregunta": "¿Qué cursos encajan con las áreas que le interesan al estudiante (nivel de interés × peso del área)?",
        "sujeto": "estudiante",
        "cypher": Q.REC_INTERESES,
        "sql": """SELECT r.codigo, r.nombre, SUM(i.nivel * t.peso)::float8 AS puntaje
FROM interes_estudiante i
JOIN curso_area t ON t.id_area = i.id_area
JOIN curso r ON r.codigo = t.codigo_curso
WHERE i.id_estudiante = %(id)s""" + _FILTROS_REC + """
GROUP BY r.codigo, r.nombre
ORDER BY puntaje DESC, r.codigo COLLATE "C"
LIMIT 20""",
        "sql_mat": None,
        "cols": ["codigo", "puntaje"],
    },
    {
        "id": "rec_otros_programas",
        "titulo": "Recomendar cursos de otros programas",
        "tema": "Recomendación",
        "pregunta": "¿Qué cursos de OTROS programas se parecen a lo aprobado por el estudiante (electivos interdisciplinares)?",
        "sujeto": "estudiante",
        "cypher": Q.REC_OTROS_PROGRAMAS,
        "sql": _rec(_SIMILAR_AL_VUELO, _EXTRA_OTRO_PROGRAMA),
        "sql_mat": _rec("curso_similar", _EXTRA_OTRO_PROGRAMA),
        "cols": ["codigo", "puntaje"],
    },
    {
        "id": "rec_similares",
        "titulo": "Recomendar por estudiantes similares",
        "tema": "Relaciones",
        "pregunta": "¿Qué aprobaron otros estudiantes que comparten cursos aprobados con este y que él aún no ha cursado?",
        "sujeto": "estudiante",
        "cypher": Q.REC_SIMILARES,
        "sql": """WITH ap AS (SELECT DISTINCT codigo_curso FROM matricula
             WHERE id_estudiante = %(id)s AND estado = 'APROBADO'),
comp AS (SELECT m.id_estudiante AS otro, COUNT(DISTINCT m.codigo_curso) AS compartidos
         FROM matricula m JOIN ap ON ap.codigo_curso = m.codigo_curso
         WHERE m.estado = 'APROBADO' AND m.id_estudiante <> %(id)s
         GROUP BY m.id_estudiante)
SELECT r.codigo, r.nombre, SUM(comp.compartidos)::float8 AS puntaje
FROM comp
JOIN matricula mo ON mo.id_estudiante = comp.otro AND mo.estado = 'APROBADO'
JOIN curso r ON r.codigo = mo.codigo_curso
WHERE TRUE""" + _FILTROS_REC + """
GROUP BY r.codigo, r.nombre
ORDER BY puntaje DESC, r.codigo COLLATE "C"
LIMIT 20""",
        "sql_mat": None,
        "cols": ["codigo", "puntaje"],
    },
    {
        "id": "inscribibles",
        "titulo": "Cursos que puede inscribir ahora",
        "tema": "Reglas de negocio",
        "pregunta": "¿Qué cursos ofrecidos este periodo puede inscribir el estudiante (no aprobados, no en curso y con prerrequisitos aprobados)?",
        "sujeto": "estudiante",
        "cypher": """MATCH (e:Estudiante {id: $id})
MATCH (r:Curso)-[:SE_DICTA_EN {periodo: $periodo}]->(:Sede)
WHERE NOT EXISTS { MATCH (e)-[h:HA_CURSADO]->(r) WHERE h.estado IN ['APROBADO', 'EN_CURSO'] }
  AND NOT EXISTS {
    MATCH (r)-[:REQUIERE {tipo: 'PRERREQUISITO'}]->(pre:Curso)
    WHERE NOT (e)-[:HA_CURSADO {estado: 'APROBADO'}]->(pre)
  }
RETURN DISTINCT r.codigo AS codigo, r.nombre AS nombre
ORDER BY codigo""",
        "sql": """SELECT r.codigo, r.nombre
FROM curso r
WHERE EXISTS (SELECT 1 FROM estudiante x WHERE x.id_estudiante = %(id)s)
  AND EXISTS (SELECT 1 FROM curso_sede cs WHERE cs.codigo_curso = r.codigo AND cs.periodo = %(periodo)s)""" + _FILTROS_REC + """
ORDER BY r.codigo COLLATE "C\"""",
        "sql_mat": None,
        "cols": ["codigo"],
    },
    {
        "id": "cadena_prerreq",
        "titulo": "Cadena completa de prerrequisitos",
        "tema": "Relaciones",
        "pregunta": "¿Cuáles son TODOS los prerrequisitos (directos e indirectos) de un curso, y a qué profundidad?",
        "sujeto": "curso",
        "cypher": """MATCH p = (c:Curso {codigo: $id})-[:REQUIERE*1..10 {tipo: 'PRERREQUISITO'}]->(q:Curso)
RETURN q.codigo AS codigo, q.nombre AS nombre, min(length(p)) AS profundidad
ORDER BY profundidad, codigo""",
        "sql": """WITH RECURSIVE cadena(codigo, prof) AS (
    SELECT codigo_requisito, 1 FROM prerrequisito WHERE codigo_curso = %(id)s AND tipo = 'PRERREQUISITO'
    UNION ALL
    SELECT p.codigo_requisito, c.prof + 1
    FROM cadena c JOIN prerrequisito p ON p.codigo_curso = c.codigo AND p.tipo = 'PRERREQUISITO'
    WHERE c.prof < 10)
SELECT q.codigo, q.nombre, MIN(c.prof)::int AS profundidad
FROM cadena c JOIN curso q ON q.codigo = c.codigo
GROUP BY q.codigo, q.nombre
ORDER BY profundidad, q.codigo COLLATE "C\"""",
        "sql_mat": None,
        "cols": ["codigo", "profundidad"],
    },
    {
        "id": "companeros_2",
        "titulo": "Compañeros de compañeros (2 saltos)",
        "tema": "Relaciones",
        "pregunta": "¿Con qué estudiantes NO ha compartido curso, pero sí lo han hecho sus compañeros? (amigos de amigos)",
        "sujeto": "estudiante",
        "cypher": """MATCH (e:Estudiante {id: $id})-[:HA_CURSADO]->(:Curso)<-[:HA_CURSADO]-(a:Estudiante)
WHERE a <> e
MATCH (a)-[:HA_CURSADO]->(:Curso)<-[:HA_CURSADO]-(b:Estudiante)
WHERE b <> e AND NOT EXISTS { MATCH (e)-[:HA_CURSADO]->(:Curso)<-[:HA_CURSADO]-(b) }
RETURN b.id AS codigo, b.nombre AS nombre, count(DISTINCT a) AS puntaje
ORDER BY puntaje DESC, codigo
LIMIT 20""",
        "sql": """WITH mis AS (SELECT DISTINCT codigo_curso FROM matricula WHERE id_estudiante = %(id)s),
a1 AS (SELECT DISTINCT m.id_estudiante AS a FROM matricula m JOIN mis ON mis.codigo_curso = m.codigo_curso
       WHERE m.id_estudiante <> %(id)s)
SELECT s.id_estudiante AS codigo, s.nombre, COUNT(DISTINCT a1.a)::float8 AS puntaje
FROM a1
JOIN matricula m1 ON m1.id_estudiante = a1.a
JOIN matricula m2 ON m2.codigo_curso = m1.codigo_curso
JOIN estudiante s ON s.id_estudiante = m2.id_estudiante
WHERE m2.id_estudiante <> %(id)s AND m2.id_estudiante NOT IN (SELECT a FROM a1)
GROUP BY s.id_estudiante, s.nombre
ORDER BY puntaje DESC, s.id_estudiante COLLATE "C"
LIMIT 20""",
        "sql_mat": None,
        "cols": ["codigo", "puntaje"],
    },
    {
        "id": "mas_aprobados",
        "titulo": "Cursos más aprobados (agregación global)",
        "tema": "Agregación",
        "pregunta": "¿Cuáles son los 10 cursos con más aprobaciones? (una agregación sobre todas las matrículas, sin recorrer relaciones)",
        "sujeto": "ninguno",
        "cypher": """MATCH (:Estudiante)-[h:HA_CURSADO {estado: 'APROBADO'}]->(c:Curso)
RETURN c.codigo AS codigo, c.nombre AS nombre, count(h) AS aprobados
ORDER BY aprobados DESC, codigo
LIMIT 10""",
        "sql": """SELECT c.codigo, c.nombre, COUNT(*) AS aprobados
FROM matricula m JOIN curso c ON c.codigo = m.codigo_curso
WHERE m.estado = 'APROBADO'
GROUP BY c.codigo, c.nombre
ORDER BY aprobados DESC, c.codigo COLLATE "C"
LIMIT 10""",
        "sql_mat": None,
        "cols": ["codigo", "aprobados"],
    },
]

_NUEVOS = [
    {
        "id": "historial_estudiante",
        "titulo": "Ver las materias aprobadas de un estudiante",
        "tema": "Búsqueda simple",
        "pregunta": "¿Qué materias aprobó este estudiante, en qué periodo y con qué nota?",
        "sujeto": "estudiante",
        "cypher": """MATCH (e:Estudiante {id: $id})-[h:HA_CURSADO {estado: 'APROBADO'}]->(c:Curso)
RETURN c.codigo AS codigo, c.nombre AS nombre, h.periodo AS periodo, h.nota AS nota
ORDER BY codigo, periodo""",
        "sql": """SELECT c.codigo, c.nombre, m.periodo, m.nota::float8 AS nota
FROM matricula m JOIN curso c ON c.codigo = m.codigo_curso
WHERE m.id_estudiante = %(id)s AND m.estado = 'APROBADO'
ORDER BY c.codigo COLLATE "C", m.periodo COLLATE "C\"""",
        "sql_mat": None,
        "cols": ["codigo", "periodo", "nota"],
    },
    {
        "id": "companeros_1",
        "titulo": "Compañeros de clase (1 salto)",
        "tema": "Recorrer relaciones",
        "pregunta": "¿Con qué estudiantes ha coincidido en cursos, y en cuántos cursos coinciden? (un salto: estudiante → curso → estudiante)",
        "sujeto": "estudiante",
        "cypher": """MATCH (e:Estudiante {id: $id})-[:HA_CURSADO]->(c:Curso)<-[:HA_CURSADO]-(a:Estudiante)
WHERE a <> e
RETURN a.id AS codigo, a.nombre AS nombre, count(DISTINCT c) AS puntaje
ORDER BY puntaje DESC, codigo
LIMIT 20""",
        "sql": """SELECT s.id_estudiante AS codigo, s.nombre, COUNT(DISTINCT m2.codigo_curso)::float8 AS puntaje
FROM matricula m1
JOIN matricula m2 ON m2.codigo_curso = m1.codigo_curso AND m2.id_estudiante <> m1.id_estudiante
JOIN estudiante s ON s.id_estudiante = m2.id_estudiante
WHERE m1.id_estudiante = %(id)s
GROUP BY s.id_estudiante, s.nombre
ORDER BY puntaje DESC, s.id_estudiante COLLATE "C"
LIMIT 20""",
        "sql_mat": None,
        "cols": ["codigo", "puntaje"],
    },
]
ESCENARIOS = ESCENARIOS + _NUEVOS

# Metadatos para explicar cada prueba con palabras simples (nivel 1 = muy simple … 4 = recorrido profundo)
META = {
    "historial_estudiante": (1, "Buscar a una persona y listar sus filas relacionadas.",
                             "Es el caso más simple. PostgreSQL suele ganar o empatar: con un índice encuentra la fila directo."),
    "mas_aprobados": (1, "Contar y ordenar sobre TODAS las matrículas.",
                      "Es una agregación global: no sigue relaciones. Es el terreno natural de las bases relacionales."),
    "companeros_1": (2, "Seguir un salto: estudiante → curso → otros estudiantes.",
                     "Un JOIN en SQL, un salto en el grafo. Con pocos datos casi no hay diferencia."),
    "inscribibles": (2, "Aplicar reglas de negocio: no repetir cursos y exigir prerrequisitos.",
                     "Mezcla filtros y comprobaciones de relaciones; ambas bases lo resuelven bien."),
    "rec_intereses": (2, "Combinar intereses del estudiante con las áreas de cada curso.",
                      "Son dos tablas unidas y sumadas; no requiere recorridos largos."),
    "rec_historial": (3, "Recomendar cursos parecidos a los aprobados.",
                      "En el grafo ya existen las relaciones SIMILAR_A; en SQL hay que calcularlas (o guardarlas en curso_similar)."),
    "rec_otros_programas": (3, "Igual que la recomendación por historial, pero solo de otros programas.",
                            "Añade un filtro de pertenencia a programa sobre la misma idea de similitud."),
    "rec_similares": (3, "Encontrar estudiantes parecidos y ver qué aprobaron.",
                      "Recorre estudiante → curso → estudiante → curso: dos saltos largos que se multiplican."),
    "cadena_prerreq": (4, "Seguir la cadena de prerrequisitos hasta el final.",
                       "Es una consulta recursiva: en SQL necesita WITH RECURSIVE; en el grafo es un camino de longitud variable."),
    "companeros_2": (4, "Compañeros de compañeros: dos saltos.",
                     "Es el clásico «amigos de amigos». A más datos, los JOIN crecen mucho más rápido que el recorrido del grafo."),
}
NIVELES = {1: "Búsqueda simple", 2: "Una relación", 3: "Varias relaciones", 4: "Recorrido profundo"}
for _e in ESCENARIOS:
    _n, _que, _espera = META[_e["id"]]
    _e.update(nivel=_n, nivel_nombre=NIVELES[_n], que_mide=_que, que_esperar=_espera)
ESCENARIOS.sort(key=lambda e: (e["nivel"], e["titulo"]))
POR_ID = {e["id"]: e for e in ESCENARIOS}


def _num(v):
    try:
        return round(float(v), 4)
    except (TypeError, ValueError):
        return v


def equivalentes(filas_a: list[dict], filas_b: list[dict], cols: list[str]) -> bool:
    """¿Las dos bases devolvieron lo mismo? Compara las columnas clave en orden, con tolerancia numérica."""
    if len(filas_a) != len(filas_b):
        return False
    for x, y in zip(filas_a, filas_b):
        for c in cols:
            a, b = _num(x.get(c)), _num(y.get(c))
            if isinstance(a, float) and isinstance(b, float):
                if abs(a - b) > 1e-3:
                    return False
            elif a != b:
                return False
    return True
