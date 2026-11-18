"""Pestaña «Modelos»: estructura REAL de cada base, leída de las propias bases (no de un texto fijo)."""
from concurrent.futures import ThreadPoolExecutor
from typing import Optional
from fastapi import APIRouter, Depends

import db
import domain as dm
import loaders
import queries as Q
from routers.auth import admin_actual

router = APIRouter(prefix="/api/admin", dependencies=[Depends(admin_actual)])


def _pg_modelo() -> dict:
    cols = db.pg_run("""SELECT table_name, column_name, data_type, is_nullable, column_default, ordinal_position
                        FROM information_schema.columns WHERE table_schema = 'public'
                        ORDER BY table_name, ordinal_position""")
    cons = db.pg_run("""SELECT c.relname AS tabla, k.conname AS nombre, k.contype AS tipo,
                               pg_get_constraintdef(k.oid) AS definicion
                        FROM pg_constraint k JOIN pg_class c ON c.oid = k.conrelid
                        JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = 'public'
                        ORDER BY c.relname, k.contype, k.conname""")
    idx = db.pg_run("SELECT tablename AS tabla, indexname AS nombre, indexdef AS definicion "
                    "FROM pg_indexes WHERE schemaname = 'public' ORDER BY tablename, indexname")
    filas = {r["relname"]: int(r["n_live_tup"]) for r in db.pg_run(
        "SELECT relname, n_live_tup FROM pg_stat_user_tables")}
    tablas: dict[str, dict] = {}
    for c in cols:
        t = tablas.setdefault(c["table_name"], {"nombre": c["table_name"], "columnas": [], "restricciones": [],
                                                "indices": [], "filas": filas.get(c["table_name"], 0)})
        t["columnas"].append({"nombre": c["column_name"], "tipo": c["data_type"], "nulo": c["is_nullable"] == "YES",
                              "defecto": c["column_default"]})
    tipos = {"p": "PRIMARY KEY", "f": "FOREIGN KEY", "c": "CHECK", "u": "UNIQUE"}
    for k in cons:
        if k["tabla"] in tablas:
            tablas[k["tabla"]]["restricciones"].append({"nombre": k["nombre"], "tipo": tipos.get(k["tipo"], k["tipo"]),
                                                        "definicion": k["definicion"]})
    for i in idx:
        if i["tabla"] in tablas:
            tablas[i["tabla"]]["indices"].append({"nombre": i["nombre"], "definicion": i["definicion"]})
    return {"tablas": list(tablas.values()), "ddl": loaders.PG_DDL.strip()}


def _una(q: str, **params):
    r = db.neo_read(q, **params)
    return r[0]["props"] if r else None


def _neo_modelo() -> dict:
    """Todas las lecturas a Neo4j (una por nodo/relación) viajan hasta Aura: se lanzan EN PARALELO."""
    tareas = {"conteo": loaders.conteos_neo, "restricciones": lambda: db.neo_read(Q.NEO_CONSTRAINTS),
              "indices": lambda: db.neo_read(Q.NEO_INDEXES)}
    for etiqueta, q in Q.NEO_MUESTRA_NODO.items():
        tareas["n:" + etiqueta] = (lambda q=q: _una(q))
    for tipo in dm.RELACIONES:
        tareas["r:" + tipo] = (lambda t=tipo: _una(Q.neo_muestra_rel(t)))
    with ThreadPoolExecutor(max_workers=8) as ex:
        futuros = {k: ex.submit(f) for k, f in tareas.items()}
        res = {k: f.result(timeout=40) for k, f in futuros.items()}
    conteo = res["conteo"]
    nodos = [{"etiqueta": k, **v, "total": conteo["nodos"].get(k, 0), "ejemplo": res["n:" + k]} for k, v in dm.NODOS.items()]
    relaciones = [{"tipo": k, **v, "total": conteo["relaciones"].get(k, 0), "ejemplo": res["r:" + k]}
                  for k, v in dm.RELACIONES.items()]
    return {"nodos": nodos, "relaciones": relaciones, "restricciones": res["restricciones"], "indices": res["indices"],
            "cypher_esquema": "\n".join(loaders.NEO_CONSTRAINTS + loaders.NEO_INDEXES)}


def _ejemplo_matricula() -> Optional[dict]:
    r = db.neo_read(Q.NEO_MATRICULA_REAL)
    if not r:
        return None
    est, curso = r[0]["estudiante"], r[0]["curso"]
    neo = db.neo_read(Q.NEO_EJEMPLO_MATRICULA, est=est, curso=curso)
    pg = db.pg_run("SELECT * FROM matricula WHERE id_estudiante = %(e)s AND codigo_curso = %(c)s", {"e": est, "c": curso})
    for f in pg:
        if f.get("nota") is not None:
            f["nota"] = float(f["nota"])
    return {"estudiante": est, "curso": curso, "neo4j": neo[0] if neo else None, "postgres": pg}


def _seguro(fn):
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001
        return {"error": getattr(exc, "detail", None) or str(exc)}


# Cada mitad se pide por separado: una base lenta o caída no bloquea a la otra.
@router.get("/modelos/postgres")
def modelo_postgres():
    return _seguro(_pg_modelo)


@router.get("/modelos/neo4j")
def modelo_neo4j():
    return _seguro(_neo_modelo)


@router.get("/modelos/ejemplo")
def modelo_ejemplo():
    return _seguro(_ejemplo_matricula) or {"error": "Aún no hay una matrícula aprobada para mostrar de ejemplo."}


@router.get("/modelos")
def modelos():
    """Compatibilidad: las dos mitades juntas (la interfaz usa los tres endpoints anteriores)."""
    return {"postgres": modelo_postgres(), "neo4j": modelo_neo4j(), "ejemplo": modelo_ejemplo()}
