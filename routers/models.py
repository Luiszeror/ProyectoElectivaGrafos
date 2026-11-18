"""Pestaña «Modelos»: estructura REAL de cada base, leída de las propias bases (no de un texto fijo)."""
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


def _neo_modelo() -> dict:
    conteo = loaders.conteos_neo()
    muestras = {}
    for etiqueta, q in Q.NEO_MUESTRA_NODO.items():
        r = db.neo_read(q)
        muestras[etiqueta] = r[0]["props"] if r else None
    rels = {}
    for tipo in dm.RELACIONES:
        r = db.neo_read(Q.NEO_MUESTRA_REL, tipo=tipo)
        rels[tipo] = r[0]["props"] if r else None
    nodos = [{"etiqueta": k, **v, "total": conteo["nodos"].get(k, 0), "ejemplo": muestras.get(k)}
             for k, v in dm.NODOS.items()]
    relaciones = [{"tipo": k, **v, "total": conteo["relaciones"].get(k, 0), "ejemplo": rels.get(k)}
                  for k, v in dm.RELACIONES.items()]
    return {"nodos": nodos, "relaciones": relaciones,
            "restricciones": db.neo_read(Q.NEO_CONSTRAINTS), "indices": db.neo_read(Q.NEO_INDEXES),
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


@router.get("/modelos")
def modelos():
    out: dict = {}
    for clave, fn in (("postgres", _pg_modelo), ("neo4j", _neo_modelo), ("ejemplo", _ejemplo_matricula)):
        try:
            out[clave] = fn()
        except Exception as exc:  # noqa: BLE001
            out[clave] = {"error": getattr(exc, "detail", None) or str(exc)}
    return out
