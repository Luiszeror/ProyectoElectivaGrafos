"""Carga de datos: esquema de PostgreSQL, sincronización Neo4j -> PostgreSQL y siembra/volumen en Neo4j.

Neo4j es la base "viva" (la que usa el portal). PostgreSQL es una imitación del proyecto que se
llena copiando lo que hay en Neo4j, de modo que ambas contengan exactamente los mismos datos
y la comparación de rendimiento sea justa.
"""
import threading
import time
import uuid

import config
import dataset as ds
import db
import queries as Q

# ====================================================================== PostgreSQL: esquema (3FN)
PG_DDL = """
DROP TABLE IF EXISTS curso_similar, curso_sede, prerrequisito, curso_area, curso_programa, dictado,
    interes_estudiante, matricula, programa_sede, estudiante, curso, docente, programa, area, sede, facultad CASCADE;

CREATE TABLE facultad (id_facultad TEXT PRIMARY KEY, nombre TEXT NOT NULL);
CREATE TABLE sede     (id_sede TEXT PRIMARY KEY, nombre TEXT NOT NULL);
CREATE TABLE area     (id_area TEXT PRIMARY KEY, nombre TEXT NOT NULL);
CREATE TABLE docente  (id_docente TEXT PRIMARY KEY, nombre TEXT NOT NULL);
CREATE TABLE programa (
    id_programa TEXT PRIMARY KEY, nombre TEXT NOT NULL,
    id_facultad TEXT REFERENCES facultad(id_facultad));
CREATE TABLE curso (
    codigo TEXT PRIMARY KEY, nombre TEXT NOT NULL,
    tipo  TEXT NOT NULL CHECK (tipo  IN ('OBLIGATORIO','ELECTIVO')),
    nivel TEXT NOT NULL CHECK (nivel IN ('Básico','Intermedio','Avanzado')));
CREATE TABLE estudiante (
    id_estudiante TEXT PRIMARY KEY, nombre TEXT NOT NULL,
    semestre INT CHECK (semestre BETWEEN 1 AND 12),
    id_programa TEXT REFERENCES programa(id_programa),
    anio_ingreso INT);
CREATE TABLE matricula (
    id_estudiante TEXT NOT NULL REFERENCES estudiante(id_estudiante) ON DELETE CASCADE,
    codigo_curso  TEXT NOT NULL REFERENCES curso(codigo) ON DELETE CASCADE,
    periodo TEXT NOT NULL CHECK (periodo ~ '^[0-9]{4}-[0-9]$'),
    nota NUMERIC(2,1) CHECK (nota BETWEEN 0 AND 5),
    estado TEXT NOT NULL CHECK (estado IN ('APROBADO','REPROBADO','EN_CURSO')),
    PRIMARY KEY (id_estudiante, codigo_curso, periodo),
    CHECK ((estado = 'EN_CURSO' AND nota IS NULL)
        OR (estado = 'APROBADO'  AND nota >= 3.0)
        OR (estado = 'REPROBADO' AND nota < 3.0)));
CREATE TABLE interes_estudiante (
    id_estudiante TEXT REFERENCES estudiante(id_estudiante) ON DELETE CASCADE,
    id_area TEXT REFERENCES area(id_area) ON DELETE CASCADE,
    nivel INT CHECK (nivel BETWEEN 1 AND 5),
    PRIMARY KEY (id_estudiante, id_area));
CREATE TABLE dictado (
    id_docente TEXT REFERENCES docente(id_docente) ON DELETE CASCADE,
    codigo_curso TEXT REFERENCES curso(codigo) ON DELETE CASCADE,
    periodo TEXT NOT NULL, grupo INT NOT NULL DEFAULT 1,
    PRIMARY KEY (id_docente, codigo_curso, periodo, grupo));
CREATE TABLE curso_programa (
    codigo_curso TEXT REFERENCES curso(codigo) ON DELETE CASCADE,
    id_programa TEXT REFERENCES programa(id_programa) ON DELETE CASCADE,
    semestre_sugerido INT, es_obligatorio BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (codigo_curso, id_programa));
CREATE TABLE curso_area (
    codigo_curso TEXT REFERENCES curso(codigo) ON DELETE CASCADE,
    id_area TEXT REFERENCES area(id_area) ON DELETE CASCADE,
    peso NUMERIC(2,1) CHECK (peso BETWEEN 0 AND 1),
    PRIMARY KEY (codigo_curso, id_area));
CREATE TABLE prerrequisito (
    codigo_curso TEXT REFERENCES curso(codigo) ON DELETE CASCADE,
    codigo_requisito TEXT REFERENCES curso(codigo) ON DELETE CASCADE,
    tipo TEXT NOT NULL CHECK (tipo IN ('PRERREQUISITO','CORREQUISITO')),
    PRIMARY KEY (codigo_curso, codigo_requisito),
    CHECK (codigo_curso <> codigo_requisito));
CREATE TABLE curso_sede (
    codigo_curso TEXT REFERENCES curso(codigo) ON DELETE CASCADE,
    id_sede TEXT REFERENCES sede(id_sede) ON DELETE CASCADE,
    periodo TEXT NOT NULL, cupos INT NOT NULL CHECK (cupos >= 0),
    PRIMARY KEY (codigo_curso, id_sede, periodo));
CREATE TABLE programa_sede (
    id_programa TEXT REFERENCES programa(id_programa) ON DELETE CASCADE,
    id_sede TEXT REFERENCES sede(id_sede) ON DELETE CASCADE,
    PRIMARY KEY (id_programa, id_sede));
-- Relación derivada (equivalente a SIMILAR_A): se materializa para comparar "calculada" vs "precalculada".
CREATE TABLE curso_similar (
    codigo_a TEXT REFERENCES curso(codigo) ON DELETE CASCADE,
    codigo_b TEXT REFERENCES curso(codigo) ON DELETE CASCADE,
    peso INT NOT NULL, PRIMARY KEY (codigo_a, codigo_b));

CREATE INDEX idx_matricula_curso    ON matricula (codigo_curso, estado);
CREATE INDEX idx_curso_area_area    ON curso_area (id_area);
CREATE INDEX idx_prerreq_req        ON prerrequisito (codigo_requisito);
CREATE INDEX idx_interes_area       ON interes_estudiante (id_area);
CREATE INDEX idx_estudiante_programa ON estudiante (id_programa);
CREATE INDEX idx_curso_programa_prog ON curso_programa (id_programa);
CREATE INDEX idx_curso_sede_periodo ON curso_sede (periodo, codigo_curso);
CREATE INDEX idx_programa_facultad  ON programa (id_facultad);
"""

# tabla -> (columnas, claves del extractor Neo4j a..e en el mismo orden)
PG_TABLAS = {
    "facultad": ["id_facultad", "nombre"],
    "sede": ["id_sede", "nombre"],
    "area": ["id_area", "nombre"],
    "docente": ["id_docente", "nombre"],
    "curso": ["codigo", "nombre", "tipo", "nivel"],
    "programa": ["id_programa", "nombre", "id_facultad"],
    "estudiante": ["id_estudiante", "nombre", "semestre", "id_programa", "anio_ingreso"],
    "programa_sede": ["id_programa", "id_sede"],
    "curso_programa": ["codigo_curso", "id_programa", "semestre_sugerido", "es_obligatorio"],
    "curso_area": ["codigo_curso", "id_area", "peso"],
    "prerrequisito": ["codigo_curso", "codigo_requisito", "tipo"],
    "curso_sede": ["codigo_curso", "id_sede", "periodo", "cupos"],
    "dictado": ["id_docente", "codigo_curso", "periodo", "grupo"],
    "interes_estudiante": ["id_estudiante", "id_area", "nivel"],
    "matricula": ["id_estudiante", "codigo_curso", "periodo", "nota", "estado"],
}
ORDEN_CARGA = list(PG_TABLAS)  # respeta las llaves foráneas


def pg_crear_esquema() -> None:
    with db.pool().connection() as conn:
        conn.execute(PG_DDL)


def pg_copiar(tablas: dict[str, list[tuple]]) -> dict[str, int]:
    """Inserta filas con COPY (la forma más rápida de cargar en PostgreSQL)."""
    conteo = {}
    with db.pool().connection() as conn:
        for t in ORDEN_CARGA:
            filas = tablas.get(t, [])
            cols = PG_TABLAS[t]
            if filas:
                with conn.cursor() as cur, cur.copy(f"COPY {t} ({', '.join(cols)}) FROM STDIN") as cp:
                    for f in filas:
                        cp.write_row(f)
            conteo[t] = len(filas)
    return conteo


def pg_similar_y_analyze() -> int:
    """Materializa curso_similar con SQL y actualiza estadísticas del planificador (ANALYZE)."""
    with db.pool().connection() as conn:
        conn.execute("TRUNCATE curso_similar")
        n = conn.execute(
            """INSERT INTO curso_similar (codigo_a, codigo_b, peso)
               SELECT a.codigo_curso, b.codigo_curso, COUNT(*)
               FROM curso_area a JOIN curso_area b ON a.id_area = b.id_area AND a.codigo_curso <> b.codigo_curso
               GROUP BY a.codigo_curso, b.codigo_curso""").rowcount
    with db.pool().connection() as conn:
        conn.autocommit = True
        conn.execute("ANALYZE")
    return n


def extraer_de_neo() -> dict[str, list[tuple]]:
    """Lee de Neo4j todo lo necesario para reconstruir las tablas relacionales."""
    out = {}
    for tabla, cols in PG_TABLAS.items():
        rows = db.neo_read(Q.EXTRAER[tabla])
        letras = "abcde"[: len(cols)]
        fil = []
        for r in rows:
            f = tuple(r.get(l) for l in letras)
            if tabla == "matricula" and f[3] is not None:
                f = (*f[:3], round(float(f[3]), 1), f[4])
            if tabla == "curso_area" and f[2] is not None:
                f = (*f[:2], round(float(f[2]), 1))
            fil.append(f)
        out[tabla] = fil
    return out


def sincronizar_pg() -> dict:
    """Recrea PostgreSQL a partir del estado actual de Neo4j."""
    t0 = time.perf_counter()
    datos = extraer_de_neo()
    pg_crear_esquema()
    conteo = pg_copiar(datos)
    similares = pg_similar_y_analyze()
    return {"tablas": conteo, "curso_similar": similares, "segundos": round(time.perf_counter() - t0, 2)}


# ====================================================================== Neo4j: restricciones y siembra
NEO_CONSTRAINTS = [
    "CREATE CONSTRAINT est_id IF NOT EXISTS FOR (n:Estudiante) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT doc_id IF NOT EXISTS FOR (n:Docente) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT cur_cod IF NOT EXISTS FOR (n:Curso) REQUIRE n.codigo IS UNIQUE",
    "CREATE CONSTRAINT prog_cod IF NOT EXISTS FOR (n:Programa) REQUIRE n.codigo IS UNIQUE",
    "CREATE CONSTRAINT fac_cod IF NOT EXISTS FOR (n:Facultad) REQUIRE n.codigo IS UNIQUE",
    "CREATE CONSTRAINT sede_cod IF NOT EXISTS FOR (n:Sede) REQUIRE n.codigo IS UNIQUE",
    "CREATE CONSTRAINT area_cod IF NOT EXISTS FOR (n:Area) REQUIRE n.codigo IS UNIQUE",
]
NEO_INDEXES = [
    "CREATE INDEX hc_estado IF NOT EXISTS FOR ()-[r:HA_CURSADO]-() ON (r.estado)",
    "CREATE INDEX hc_periodo IF NOT EXISTS FOR ()-[r:HA_CURSADO]-() ON (r.periodo)",
]


def _nodo(label: str, clave: str, extra: str, sint: bool) -> str:
    flag = ", n.sintetico = true" if sint else ""
    return f"UNWIND $rows AS r MERGE (n:{label} {{{clave}: r.k}}) SET n.nombre = r.nombre{extra}{flag}"


def _statements(d: ds.Dataset, sint: bool) -> list[tuple[str, dict]]:
    S: list[tuple[str, dict]] = []
    S.append((_nodo("Facultad", "codigo", "", sint), {"rows": [{"k": a, "nombre": b} for a, b in d.facultad]}))
    S.append((_nodo("Sede", "codigo", "", sint), {"rows": [{"k": a, "nombre": b} for a, b in d.sede]}))
    S.append((_nodo("Area", "codigo", "", sint), {"rows": [{"k": a, "nombre": b} for a, b in d.area]}))
    S.append((_nodo("Docente", "id", "", sint), {"rows": [{"k": a, "nombre": b} for a, b in d.docente]}))
    S.append((_nodo("Programa", "codigo", "", sint), {"rows": [{"k": a, "nombre": b} for a, b, _ in d.programa]}))
    S.append((_nodo("Curso", "codigo", ", n.tipo = r.tipo, n.nivel = r.nivel", sint),
              {"rows": [{"k": a, "nombre": b, "tipo": c, "nivel": n} for a, b, c, n in d.curso]}))
    S.append((_nodo("Estudiante", "id", ", n.semestre = r.semestre", sint),
              {"rows": [{"k": a, "nombre": b, "semestre": s} for a, b, s, _, _ in d.estudiante]}))
    S.append(("UNWIND $rows AS r MATCH (p:Programa {codigo: r.a}), (f:Facultad {codigo: r.b}) MERGE (p)-[:PERTENECE_A]->(f)",
              {"rows": [{"a": a, "b": f} for a, _, f in d.programa if f]}))
    S.append(("UNWIND $rows AS r MATCH (p:Programa {codigo: r.a}), (s:Sede {codigo: r.b}) MERGE (p)-[:SE_OFRECE_EN]->(s)",
              {"rows": [{"a": a, "b": b} for a, b in d.programa_sede]}))
    S.append(("UNWIND $rows AS r MATCH (e:Estudiante {id: r.a}), (p:Programa {codigo: r.b}) "
              "MERGE (e)-[x:ESTUDIA_EN]->(p) SET x.anio_ingreso = r.anio",
              {"rows": [{"a": a, "b": p, "anio": y} for a, _, _, p, y in d.estudiante if p]}))
    S.append(("UNWIND $rows AS r MATCH (c:Curso {codigo: r.a}), (p:Programa {codigo: r.b}) "
              "MERGE (c)-[x:INCLUIDO_EN]->(p) SET x.semestre_sugerido = r.sem, x.es_obligatorio = r.ob",
              {"rows": [{"a": a, "b": b, "sem": s, "ob": o} for a, b, s, o in d.curso_programa]}))
    S.append(("UNWIND $rows AS r MATCH (c:Curso {codigo: r.a}), (x:Area {codigo: r.b}) "
              "MERGE (c)-[t:TRATA_DE]->(x) SET t.peso = r.peso",
              {"rows": [{"a": a, "b": b, "peso": p} for a, b, p in d.curso_area]}))
    S.append(("UNWIND $rows AS r MATCH (c:Curso {codigo: r.a}), (q:Curso {codigo: r.b}) "
              "MERGE (c)-[x:REQUIERE]->(q) SET x.tipo = r.tipo",
              {"rows": [{"a": a, "b": b, "tipo": t} for a, b, t in d.prerrequisito]}))
    S.append(("UNWIND $rows AS r MATCH (c:Curso {codigo: r.a}), (s:Sede {codigo: r.b}) "
              "MERGE (c)-[x:SE_DICTA_EN {periodo: r.periodo}]->(s) SET x.cupos = r.cupos",
              {"rows": [{"a": a, "b": b, "periodo": p, "cupos": n} for a, b, p, n in d.curso_sede]}))
    S.append(("UNWIND $rows AS r MATCH (d:Docente {id: r.a}), (c:Curso {codigo: r.b}) "
              "MERGE (d)-[x:DICTA {periodo: r.periodo, grupo: r.grupo}]->(c)",
              {"rows": [{"a": a, "b": b, "periodo": p, "grupo": g} for a, b, p, g in d.dictado]}))
    S.append(("UNWIND $rows AS r MATCH (e:Estudiante {id: r.a}), (x:Area {codigo: r.b}) "
              "MERGE (e)-[i:INTERESADO_EN]->(x) SET i.nivel = r.nivel",
              {"rows": [{"a": a, "b": b, "nivel": n} for a, b, n in d.interes_estudiante]}))
    S.append(("UNWIND $rows AS r MATCH (e:Estudiante {id: r.a}), (c:Curso {codigo: r.b}) "
              "MERGE (e)-[h:HA_CURSADO {periodo: r.periodo}]->(c) SET h.nota = r.nota, h.estado = r.estado",
              {"rows": [{"a": a, "b": b, "periodo": p, "nota": n, "estado": s} for a, b, p, n, s in d.matricula]}))
    return [(q, p) for q, p in S if p["rows"]]


def _lotes(stmts, tam=2000):
    for q, p in stmts:
        rows = p["rows"]
        for i in range(0, len(rows), tam):
            yield q, {"rows": rows[i:i + tam]}


def neo_preparar_esquema() -> None:
    for q in NEO_CONSTRAINTS + NEO_INDEXES:
        db.neo_write(q)


def neo_cargar(d: ds.Dataset, sintetico: bool, progreso=None) -> None:
    lotes = list(_lotes(_statements(d, sintetico)))
    for i, (q, p) in enumerate(lotes, 1):
        db.neo_write(q, **p)
        if progreso:
            progreso(i, len(lotes))


def neo_reconstruir_similares() -> None:
    db.neo_write(Q.SIM_BORRAR_TODAS)
    db.neo_write(Q.SIM_CONSTRUIR_TODAS)


def neo_limpiar_sinteticos() -> int:
    """Borra solo los nodos marcados como sintéticos (en lotes), sin tocar los datos reales."""
    total = 0
    while True:
        r = db.neo_write("MATCH (n) WHERE n.sintetico = true WITH n LIMIT 2000 DETACH DELETE n RETURN count(*) AS borrados")
        n = r[0]["borrados"] if r else 0
        total += n
        if n == 0:
            return total


def neo_resetear_base() -> None:
    """Borra todo lo del dominio y vuelve a sembrar el conjunto base."""
    while True:
        r = db.neo_write("MATCH (n) WITH n LIMIT 2000 DETACH DELETE n RETURN count(*) AS borrados")
        if not r or r[0]["borrados"] == 0:
            break
    neo_preparar_esquema()
    neo_cargar(ds.base(), False)
    neo_reconstruir_similares()


def conteos_neo() -> dict:
    nod = {r["etiqueta"]: r["total"] for r in db.neo_read(Q.CONTEO_ETIQUETAS)}
    rel = {r["tipo"]: r["total"] for r in db.neo_read(Q.CONTEO_RELACIONES)}
    return {"nodos": nod, "relaciones": rel, "total_nodos": sum(nod.values()), "total_relaciones": sum(rel.values())}


# ====================================================================== trabajos en segundo plano
JOBS: dict[str, dict] = {}
_JOB_LOCK = threading.Lock()


def lanzar(nombre: str, fn) -> str:
    """Ejecuta `fn(progreso)` en un hilo; `progreso(i, n, texto)` actualiza el avance."""
    with _JOB_LOCK:
        if any(j["estado"] == "corriendo" for j in JOBS.values()):
            raise RuntimeError("Ya hay un proceso de datos en ejecución. Espera a que termine.")
        jid = uuid.uuid4().hex[:8]
        JOBS[jid] = {"id": jid, "nombre": nombre, "estado": "corriendo", "pct": 0, "detalle": "Iniciando…",
                     "resultado": None, "error": None, "t0": time.time()}

    def progreso(i, n, texto=""):
        JOBS[jid]["pct"] = round(100 * i / max(n, 1))
        if texto:
            JOBS[jid]["detalle"] = texto

    def run():
        try:
            JOBS[jid]["resultado"] = fn(progreso)
            JOBS[jid]["estado"] = "listo"
            JOBS[jid]["pct"] = 100
            JOBS[jid]["detalle"] = "Terminado"
        except Exception as exc:  # noqa: BLE001
            JOBS[jid]["estado"] = "error"
            JOBS[jid]["error"] = getattr(exc, "detail", None) or str(exc)
        finally:
            JOBS[jid]["segundos"] = round(time.time() - JOBS[jid]["t0"], 1)

    threading.Thread(target=run, daemon=True).start()
    return jid


def tarea_generar(n_est: int, n_cur: int):
    def fn(progreso):
        est = ds.estimar(n_est, n_cur)
        actual = conteos_neo()
        if actual["total_nodos"] + est["nodos"] > config.AURA_MAX_NODOS or \
           actual["total_relaciones"] + est["relaciones"] > config.AURA_MAX_RELS:
            raise RuntimeError("Superaría el límite de Aura Free (200 mil nodos / 400 mil relaciones). Usa menos volumen.")
        progreso(0, 1, "Generando datos…")
        d = ds.generar(n_est, n_cur, periodo_actual=config.PERIODO_ACTUAL)
        problemas = ds.validar(d)
        if problemas:
            raise RuntimeError("El generador produjo datos inválidos: " + "; ".join(problemas[:3]))
        neo_limpiar_sinteticos()
        neo_preparar_esquema()
        neo_cargar(d, True, lambda i, n: progreso(i, n + 3, "Cargando en Neo4j…"))
        progreso(1, 3, "Calculando SIMILAR_A…")
        neo_reconstruir_similares()
        progreso(2, 3, "Sincronizando PostgreSQL…")
        sync = sincronizar_pg()
        return {"generado": d.contar(), "sync": sync}
    return fn


def tarea_limpiar():
    def fn(progreso):
        progreso(0, 3, "Borrando datos de prueba…")
        borrados = neo_limpiar_sinteticos()
        progreso(1, 3, "Recalculando SIMILAR_A…")
        neo_reconstruir_similares()
        progreso(2, 3, "Sincronizando PostgreSQL…")
        return {"borrados": borrados, "sync": sincronizar_pg()}
    return fn


def tarea_sync():
    def fn(progreso):
        progreso(0, 1, "Copiando de Neo4j a PostgreSQL…")
        return sincronizar_pg()
    return fn
