"""Pruebas de la API de punta a punta: PostgreSQL REAL + doble de Neo4j.
Uso:  PG_DSN=postgresql://usuario@host:puerto/base python -m pytest tests -q
"""
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import fake_neo  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="module")
def c():
    fake_neo.instalar()
    import app
    return TestClient(app.app)


def login_est(c, eid):
    r = c.post("/api/auth/estudiante/entrar", json={"id": eid})
    assert r.status_code == 200, r.text
    return {"X-Token": r.json()["token"]}


def login_admin(c):
    return {"X-Token": c.post("/api/auth/admin/entrar", json={}).json()["token"]}


def esperar(c, h, jid, tope=60):
    for _ in range(tope * 10):
        j = c.get(f"/api/admin/datos/job/{jid}", headers=h).json()
        if j["estado"] != "corriendo":
            return j
        time.sleep(0.1)
    raise AssertionError("el proceso no terminó")


# ------------------------------------------------------------------ acceso
def test_info_y_login(c):
    i = c.get("/api/auth/info").json()
    assert i["periodo"] == "2026-2" and len(i["estudiantes_demo"]) == 10 and len(i["programas"]) == 2
    assert c.post("/api/auth/estudiante/entrar", json={"id": "E999"}).status_code == 404
    assert c.get("/api/estudiante/perfil").status_code == 401
    assert c.get("/api/admin/docentes").status_code == 401
    # un estudiante no entra a rutas de administrador
    assert c.get("/api/admin/docentes", headers=login_est(c, "E1")).status_code == 401


def test_crear_estudiante(c):
    r = c.post("/api/auth/estudiante/crear", json={"nombre": "Nuevo Demo", "semestre": 2, "programa": "P1"})
    assert r.status_code == 200 and r.json()["id"] == "E11"
    h = {"X-Token": r.json()["token"]}
    p = c.get("/api/estudiante/perfil", headers=h).json()
    assert p["perfil"]["programa"]["codigo"] == "P1" and p["historial"] == []
    assert c.post("/api/auth/estudiante/crear", json={"nombre": "", "semestre": 2, "programa": "P1"}).status_code == 422
    assert c.post("/api/auth/estudiante/crear", json={"nombre": "x", "semestre": 99, "programa": "P1"}).status_code == 422
    assert c.post("/api/auth/estudiante/crear", json={"nombre": "x", "semestre": 2, "programa": "ZZ"}).status_code == 422


# ------------------------------------------------------------------ estudiante
def test_perfil_ana(c):
    p = c.get("/api/estudiante/perfil", headers=login_est(c, "E1")).json()
    assert p["perfil"]["nombre"] == "Ana" and p["perfil"]["programa"]["nombre"] == "Ingeniería de Sistemas"
    assert p["resumen"]["aprobados"] == 3 and p["resumen"]["en_curso"] == 1
    assert {x["curso"] for x in p["pendientes_obligatorios"]} >= {"C302", "C205"}


def test_materias_perdidas(c):
    p = c.get("/api/estudiante/perfil", headers=login_est(c, "E2")).json()
    assert [x["curso"] for x in p["perdidas"]] == ["C102"] and p["perdidas"][0]["se_ofrece"] is True


def test_catalogo_reglas(c):
    h = login_est(c, "E2")   # Luis: perdió C102, aprobó C101 y C302
    cat = {x["codigo"]: x for x in c.get("/api/estudiante/catalogo", headers=h).json()["cursos"]}
    assert cat["C201"]["puede"] is True                       # prerrequisito C101 aprobado
    assert cat["C102"]["puede"] is True                       # perdido: se puede repetir
    assert cat["C101"]["puede"] is False and "aprobaste" in cat["C101"]["motivos"][0]
    assert cat["C301"]["puede"] is False and "C202" in cat["C301"]["motivos"][0]   # falta C202
    assert cat["C103"]["puede"] is False                      # requiere C102, que perdió


def test_inscribir_y_retirar(c):
    h = login_est(c, "E2")
    assert c.post("/api/estudiante/inscribir", json={"curso": "C301"}, headers=h).status_code == 409
    assert c.post("/api/estudiante/inscribir", json={"curso": "C201"}, headers=h).status_code == 200
    assert c.post("/api/estudiante/inscribir", json={"curso": "C201"}, headers=h).status_code == 409   # ya inscrito
    p = c.get("/api/estudiante/perfil", headers=h).json()
    assert p["resumen"]["en_curso"] == 1
    assert c.post("/api/estudiante/retirar", json={"curso": "C201"}, headers=h).status_code == 200
    assert c.post("/api/estudiante/retirar", json={"curso": "C201"}, headers=h).status_code == 404


def test_cupos_agotados(c):
    a = login_admin(c)
    assert c.post("/api/admin/cursos", json={
        "codigo": "C990", "nombre": "Cupo uno", "tipo": "ELECTIVO", "nivel": "Básico",
        "areas": [{"id": "A4", "peso": 1}], "sedes": [{"id": "S1", "cupos": 1}]}, headers=a).status_code == 200
    assert c.post("/api/estudiante/inscribir", json={"curso": "C990"}, headers=login_est(c, "E4")).status_code == 200
    r = c.post("/api/estudiante/inscribir", json={"curso": "C990"}, headers=login_est(c, "E9"))
    assert r.status_code == 409 and "cupos" in r.text
    c.delete("/api/admin/cursos/C990?forzar=true", headers=a)


def test_intereses_y_recomendaciones(c):
    h = login_est(c, "E4")
    assert c.put("/api/estudiante/intereses", json={"items": [{"area": "A1", "nivel": 5}, {"area": "A2", "nivel": 2}]},
                 headers=h).status_code == 200
    rec = c.get("/api/estudiante/recomendaciones", headers=h).json()
    assert set(rec) == {"por_historial", "por_intereses", "otros_programas", "estudiantes_similares",
                        "areas_fortalezas", "areas_explorar"}
    cods = [x["codigo"] for x in rec["por_intereses"]]
    assert cods and "C101" not in cods and "C102" not in cods          # no repite lo aprobado
    assert "C301" not in cods                                           # prerrequisitos faltantes
    assert c.put("/api/estudiante/intereses", json={"items": [{"area": "A1", "nivel": 9}]}, headers=h).status_code == 422


def test_red(c):
    r = c.get("/api/estudiante/red", headers=login_est(c, "E1")).json()
    assert r["nodos"] and r["aristas"] and any(n["tipo"] == "Estudiante" for n in r["nodos"])


# ------------------------------------------------------------------ administrador: gestión
def test_docentes_crud(c):
    a = login_admin(c)
    did = c.post("/api/admin/docentes", json={"nombre": "Prof Nuevo"}, headers=a).json()["id"]
    assert did == "D5"
    assert c.post(f"/api/admin/docentes/{did}/asignar", json={"curso": "C101", "grupo": 2}, headers=a).status_code == 200
    d = {x["id"]: x for x in c.get("/api/admin/docentes", headers=a).json()["docentes"]}
    assert d[did]["cursos"][0]["curso"] == "C101"
    assert c.put(f"/api/admin/docentes/{did}", json={"nombre": "Renombrado"}, headers=a).status_code == 200
    assert c.post("/api/admin/docentes/D5/asignar", json={"curso": "ZZZ"}, headers=a).status_code == 404
    assert c.delete(f"/api/admin/docentes/{did}", headers=a).status_code == 200
    assert c.post("/api/admin/docentes", json={"nombre": "  "}, headers=a).status_code == 422


def curso_body(**kw):
    b = {"nombre": "Curso X", "tipo": "ELECTIVO", "nivel": "Intermedio", "areas": [{"id": "A1", "peso": 0.8}],
         "programas": [{"id": "P1", "semestre": 5, "obligatorio": False}], "requisitos": [{"id": "C101", "tipo": "PRERREQUISITO"}],
         "sedes": [{"id": "S1", "cupos": 10}], "docentes": [{"id": "D1", "grupo": 1}]}
    b.update(kw)
    return b


def test_cursos_crud_y_reglas(c):
    a = login_admin(c)
    r = c.post("/api/admin/cursos", json=curso_body(), headers=a)
    assert r.status_code == 200, r.text
    cod = r.json()["codigo"]
    cat = {x["codigo"]: x for x in c.get("/api/admin/cursos", headers=a).json()["cursos"]}
    assert cat[cod]["prerreq"][0]["codigo"] == "C101" and cat[cod]["docentes"][0]["id"] == "D1"
    # reglas
    assert c.post("/api/admin/cursos", json=curso_body(areas=[]), headers=a).status_code == 422
    assert c.post("/api/admin/cursos", json=curso_body(tipo="OTRO"), headers=a).status_code == 422
    assert c.post("/api/admin/cursos", json=curso_body(areas=[{"id": "A99", "peso": 1}]), headers=a).status_code == 422
    assert c.post("/api/admin/cursos", json=curso_body(codigo="C101"), headers=a).status_code == 409
    assert c.post("/api/admin/cursos", json=curso_body(sedes=[{"id": "S1", "cupos": -3}]), headers=a).status_code == 422
    # ciclo: C101 no puede exigir al nuevo curso (que ya exige C101)
    r = c.put("/api/admin/cursos/C101", json=curso_body(nombre="Bases de Datos I", requisitos=[{"id": cod, "tipo": "PRERREQUISITO"}]), headers=a)
    assert r.status_code == 422 and "Ciclo" in r.text
    # se puede editar y se puede borrar
    assert c.put(f"/api/admin/cursos/{cod}", json=curso_body(nombre="Renombrado"), headers=a).status_code == 200
    # curso con matrículas: borrar exige forzar
    assert c.delete("/api/admin/cursos/C101", headers=a).status_code == 409
    assert c.delete(f"/api/admin/cursos/{cod}", headers=a).status_code == 200


def test_curso_nuevo_aparece_para_estudiante(c):
    a = login_admin(c)
    cod = c.post("/api/admin/cursos", json=curso_body(nombre="Curso visible", requisitos=[]), headers=a).json()["codigo"]
    cat = {x["codigo"]: x for x in c.get("/api/estudiante/catalogo", headers=login_est(c, "E4")).json()["cursos"]}
    assert cat[cod]["puede"] is True
    c.delete(f"/api/admin/cursos/{cod}", headers=a)


def test_catalogos(c):
    a = login_admin(c)
    assert c.post("/api/admin/catalogos/areas", json={"codigo": "A9", "nombre": "Robótica"}, headers=a).status_code == 200
    assert c.post("/api/admin/catalogos/areas", json={"codigo": "A9", "nombre": "Otra"}, headers=a).status_code == 409
    assert c.put("/api/admin/catalogos/areas/A9", json={"nombre": "Robótica 2"}, headers=a).status_code == 200
    assert c.delete("/api/admin/catalogos/areas/A9", headers=a).status_code == 200
    assert c.delete("/api/admin/catalogos/areas/A1", headers=a).status_code == 409        # en uso
    assert c.post("/api/admin/catalogos/programas", json={"codigo": "P9", "nombre": "Nuevo", "facultad": "F1", "sedes": ["S1"]},
                  headers=a).status_code == 200
    cat = c.get("/api/admin/catalogos", headers=a).json()
    assert {"codigo": "P9", "nombre": "Nuevo", "facultad": "F1"} in cat["programas"]
    assert {"programa": "P9", "sede": "S1"} in cat["programa_sedes"]
    assert c.post("/api/admin/catalogos/planetas", json={"codigo": "X1", "nombre": "x"}, headers=a).status_code == 404


def test_notas(c):
    a = login_admin(c)
    m = c.get("/api/admin/matriculas?estado=EN_CURSO&q=Ana", headers=a).json()
    assert m and m[0]["curso"] == "C103"
    body = {"estudiante": "E1", "curso": "C103", "periodo": "2026-2"}
    assert c.put("/api/admin/matriculas/nota", json={**body, "nota": 4.3}, headers=a).json()["estado"] == "APROBADO"
    assert c.put("/api/admin/matriculas/nota", json={**body, "nota": 2.0}, headers=a).json()["estado"] == "REPROBADO"
    assert c.put("/api/admin/matriculas/nota", json={**body, "nota": 7}, headers=a).status_code == 422
    assert c.put("/api/admin/matriculas/nota", json={**body, "curso": "C999", "nota": 3}, headers=a).status_code == 404


# ------------------------------------------------------------------ administrador: comparación
def test_estado_y_sincronizacion(c):
    a = login_admin(c)
    jid = c.post("/api/admin/datos/sincronizar", headers=a).json()["job"]
    j = esperar(c, a, jid)
    assert j["estado"] == "listo", j
    e = c.get("/api/admin/estado", headers=a).json()
    assert e["sincronizado"] is True and e["postgres"]["tablas"]["curso_similar"] > 0
    assert e["neo4j"]["total_nodos"] > 0


def test_comparacion_todos_los_escenarios(c):
    a = login_admin(c)
    esc = c.get("/api/admin/comparar/escenarios", headers=a).json()
    assert len(esc) == 10 and {e["nivel"] for e in esc} == {1, 2, 3, 4} and all(e["que_mide"] for e in esc)
    for e in esc:
        s = c.get("/api/admin/comparar/muestra", params={"sujeto": e["sujeto"], "alcance": "base"}, headers=a).json()["id"]
        for var in (["sql", "sql_mat"] if e["sql_mat"] else ["sql"]):
            r = c.post("/api/admin/comparar/ejecutar", json={"escenario": e["id"], "sujeto": s, "repeticiones": 3, "variante": var}, headers=a)
            assert r.status_code == 200, r.text
            r = r.json()
            assert r["equivalentes"] is True, (e["id"], var, r["neo4j"]["resultado"][:2], r["postgres"]["resultado"][:2])
            assert r["postgres"]["motor"]["mediana"] >= 0 and len(r["neo4j"]["muestras"]) == 3
    p = c.post("/api/admin/comparar/plan", json={"escenario": "rec_historial", "sujeto": "E5"}, headers=a).json()
    assert p["neo4j"] and any("Execution Time" in x for x in p["postgres"])
    assert c.post("/api/admin/comparar/ejecutar", json={"escenario": "nope"}, headers=a).status_code == 404
    assert c.post("/api/admin/comparar/ejecutar", json={"escenario": "rec_historial", "sujeto": "E1", "repeticiones": 99}, headers=a).status_code == 422


def test_volumen_y_limpieza(c):
    a = login_admin(c)
    assert c.post("/api/admin/datos/generar", json={"estudiantes": 5, "cursos": 60}, headers=a).status_code == 422
    jid = c.post("/api/admin/datos/generar", json={"estudiantes": 200, "cursos": 40}, headers=a).json()["job"]
    j = esperar(c, a, jid)
    assert j["estado"] == "listo", j
    # los datos de volumen no se ven en el portal de estudiantes
    assert len(c.get("/api/auth/info").json()["estudiantes_demo"]) <= 12
    assert all(not x["codigo"].startswith("SC") for x in c.get("/api/estudiante/catalogo", headers=login_est(c, "E1")).json()["cursos"])
    est = c.get("/api/admin/comparar/muestra", params={"sujeto": "estudiante", "alcance": "volumen"}, headers=a).json()["id"]
    assert est.startswith("SE")
    r = c.post("/api/admin/comparar/ejecutar", json={"escenario": "rec_historial", "sujeto": est, "repeticiones": 3}, headers=a).json()
    assert r["equivalentes"] is True and r["postgres"]["filas"] > 0
    curso = c.get("/api/admin/comparar/muestra", params={"sujeto": "curso", "alcance": "volumen"}, headers=a).json()["id"]
    r = c.post("/api/admin/comparar/ejecutar", json={"escenario": "cadena_prerreq", "sujeto": curso, "repeticiones": 2}, headers=a).json()
    assert r["equivalentes"] is True and r["postgres"]["filas"] > 0
    r = c.post("/api/admin/comparar/ejecutar", json={"escenario": "mas_aprobados", "repeticiones": 2}, headers=a).json()
    assert r["equivalentes"] is True
    # limpiar deja solo el conjunto base
    assert esperar(c, a, c.post("/api/admin/datos/limpiar", headers=a).json()["job"])["estado"] == "listo"
    e = c.get("/api/admin/estado", headers=a).json()
    assert e["postgres"]["tablas"]["estudiante"] == 11 and e["sincronizado"] is True      # 10 base + 1 creado en pruebas
    assert c.get("/api/admin/comparar/muestra", params={"sujeto": "estudiante", "alcance": "volumen"}, headers=a).status_code == 404


def test_un_solo_proceso_a_la_vez(c):
    a = login_admin(c)
    import loaders
    loaders.JOBS["x"] = {"id": "x", "estado": "corriendo"}
    try:
        assert c.post("/api/admin/datos/sincronizar", headers=a).status_code == 409
    finally:
        del loaders.JOBS["x"]


def test_modelos(c):
    a = login_admin(c)
    m = c.get("/api/admin/modelos", headers=a).json()
    nombres = {t["nombre"] for t in m["postgres"]["tablas"]}
    assert {"matricula", "curso_similar", "estudiante"} <= nombres
    mat = next(t for t in m["postgres"]["tablas"] if t["nombre"] == "matricula")
    assert any(r["tipo"] == "PRIMARY KEY" for r in mat["restricciones"]) and any("idx_matricula_curso" == i["nombre"] for i in mat["indices"])
    assert len(m["neo4j"]["nodos"]) == 7 and len(m["neo4j"]["relaciones"]) == 11
    assert m["ejemplo"]["neo4j"] and m["ejemplo"]["postgres"]


# ------------------------------------------------------------------ explorador del grafo
def test_explorador_general_y_vecindad(c):
    a = login_admin(c)
    g = c.get("/api/admin/grafo?limite=120", headers=a).json()
    assert g["nodos"] and g["aristas"] and len(g["aristas"]) <= 120
    assert all(x["tipo"] != "SIMILAR_A" for x in g["aristas"])                       # por defecto no satura con SIMILAR_A
    s = c.get("/api/admin/grafo?tipos=SIMILAR_A&limite=50", headers=a).json()
    assert s["aristas"] and all(x["tipo"] == "SIMILAR_A" for x in s["aristas"])
    v = c.get("/api/admin/grafo/vecindad", params={"eid": "Estudiante:E1"}, headers=a).json()
    assert v["aristas"] and any(n["id"] == "Estudiante:E1" for n in v["nodos"])
    assert c.get("/api/admin/grafo", headers=login_est(c, "E1")).status_code == 401
    assert c.get("/api/admin/grafo?limite=5", headers=a).status_code == 422


def test_cypher_libre_solo_lectura(c):
    a = login_admin(c)
    r = c.post("/api/admin/cypher", json={"query": "MATCH (n:Curso)-[r]->(m) RETURN n, r, m, 7 AS k LIMIT 5"}, headers=a)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["columnas"] == ["n", "r", "m", "k"] and len(j["grafo"]["nodos"]) == 2 and len(j["grafo"]["aristas"]) == 1
    for peligro in ("MATCH (n) DETACH DELETE n", "CREATE (:X)", "match (n) set n.a=1", "LOAD CSV FROM 'http://x' AS l RETURN l"):
        assert c.post("/api/admin/cypher", json={"query": peligro}, headers=a).status_code == 403, peligro
    # una palabra prohibida dentro de un texto entre comillas no bloquea
    assert c.post("/api/admin/cypher", json={"query": "MATCH (n) WHERE n.nombre = 'set create' RETURN n"}, headers=a).status_code == 200
    assert c.post("/api/admin/cypher", json={"query": "MATCH BOOM"}, headers=a).status_code == 400
    assert c.post("/api/admin/cypher", json={"query": "  "}, headers=a).status_code == 422


def test_comparacion_variables_de_justicia(c):
    a = login_admin(c)
    lat = c.get("/api/admin/comparar/latencia", headers=a).json()
    assert lat["red_ms"] >= 0
    base = {"escenario": "mas_aprobados", "repeticiones": 4}
    sin = c.post("/api/admin/comparar/ejecutar", json={**base, "red_pg": "ninguna"}, headers=a).json()
    con = c.post("/api/admin/comparar/ejecutar", json={**base, "red_pg": "manual", "red_pg_ms": 40}, headers=a).json()
    assert sin["justicia"]["red_pg_ms"] == 0 and con["justicia"]["red_pg_ms"] == 40
    # la red simulada se suma al tiempo total de PostgreSQL pero no al del motor
    assert con["postgres"]["total"]["mediana"] >= 40 and con["postgres"]["motor"]["mediana"] < 40
    assert sin["postgres"]["total"]["mediana"] < 40
    assert con["veredicto"]["ganador"] in ("neo4j", "postgres", "empate") and con["equivalentes"] is True
    m = c.post("/api/admin/comparar/ejecutar", json={**base, "metrica": "motor", "intercalar": False, "calentar": False}, headers=a).json()
    assert m["justicia"]["metrica"] == "motor" and m["justicia"]["calentar"] is False and len(m["neo4j"]["muestras"]) == 4
    assert c.post("/api/admin/comparar/ejecutar", json={**base, "red_pg": "manual", "red_pg_ms": 99999}, headers=a).status_code == 422


def test_modelos_por_mitades(c):
    a = login_admin(c)
    pg = c.get("/api/admin/modelos/postgres", headers=a).json()
    ne = c.get("/api/admin/modelos/neo4j", headers=a).json()
    ej = c.get("/api/admin/modelos/ejemplo", headers=a).json()
    assert len(pg["tablas"]) >= 15 and len(ne["nodos"]) == 7 and ne["relaciones"] and "error" not in ej
    todo = c.get("/api/admin/modelos", headers=a).json()
    assert set(todo) == {"postgres", "neo4j", "ejemplo"}
