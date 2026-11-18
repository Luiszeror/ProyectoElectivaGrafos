"""Acceso a las dos bases de datos.

Los routers siempre llaman `db.neo_read(...)`, `db.pg_run(...)`, etc. a través del módulo
(no con `from db import ...`), de modo que las pruebas puedan reemplazarlas.
"""
from typing import Optional, Union
import threading
import time

import psycopg
from psycopg import conninfo as pg_conninfo
from psycopg import sql as pg_sql
from fastapi import HTTPException
from neo4j import GraphDatabase, RoutingControl
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

import config

_lock = threading.Lock()
_driver = None
_pool = None


# ------------------------------------------------------------------ Neo4j
def driver():
    global _driver
    with _lock:
        if _driver is None:
            if not config.NEO4J_URI or not config.NEO4J_PASSWORD:
                raise HTTPException(503, "Faltan NEO4J_URI y NEO4J_PASSWORD. Revisa tu archivo .env")
            _driver = GraphDatabase.driver(config.NEO4J_URI, auth=(config.NEO4J_USER, config.NEO4J_PASSWORD))
        return _driver


def neo_read(query: str, **params) -> list[dict]:
    records, _, _ = driver().execute_query(
        query, params, database_=config.NEO4J_DATABASE, routing_=RoutingControl.READ
    )
    return [r.data() for r in records]


def neo_write(query: str, **params) -> list[dict]:
    records, _, _ = driver().execute_query(
        query, params, database_=config.NEO4J_DATABASE, routing_=RoutingControl.WRITE
    )
    return [r.data() for r in records]


def neo_tx(statements: list[tuple[str, dict]]) -> None:
    """Ejecuta varias sentencias en UNA sola transacción de escritura (todo o nada)."""

    def work(tx):
        for query, params in statements:
            tx.run(query, params).consume()

    with driver().session(database=config.NEO4J_DATABASE) as session:
        session.execute_write(work)


def neo_timed(query: str, params: dict) -> dict:
    """Ejecuta una lectura y devuelve filas + tiempos.

    motor_ms: tiempo que Neo4j informa (primer resultado + consumo).
    total_ms: tiempo visto desde esta aplicación (incluye la red hasta Aura).
    """
    drv = driver()
    t0 = time.perf_counter()
    result = drv.execute_query(query, params, database_=config.NEO4J_DATABASE, routing_=RoutingControl.READ)
    total = (time.perf_counter() - t0) * 1000
    summary = result.summary
    motor = (summary.result_available_after or 0) + (summary.result_consumed_after or 0)
    return {"rows": [r.data() for r in result.records], "motor_ms": float(motor), "total_ms": total}


def neo_profile(query: str, params: dict) -> dict:
    """Ejecuta PROFILE y devuelve el árbol de operadores (como diccionario)."""
    result = driver().execute_query(
        "PROFILE " + query, params, database_=config.NEO4J_DATABASE, routing_=RoutingControl.READ
    )
    return result.summary.profile or {}


def _plano(v):
    """Convierte lo que devuelve el driver (nodos, relaciones, rutas, fechas…) en JSON simple."""
    from neo4j.graph import Node, Path, Relationship
    if isinstance(v, Node):
        return {"_tipo": "nodo", "id": v.element_id, "etiquetas": list(v.labels), "props": {k: _plano(x) for k, x in v.items()}}
    if isinstance(v, Relationship):
        return {"_tipo": "relacion", "id": v.element_id, "tipo": v.type, "de": v.start_node.element_id,
                "a": v.end_node.element_id, "props": {k: _plano(x) for k, x in v.items()}}
    if isinstance(v, Path):
        return {"_tipo": "ruta", "nodos": [_plano(n) for n in v.nodes], "relaciones": [_plano(r) for r in v.relationships]}
    if isinstance(v, (list, tuple)):
        return [_plano(x) for x in v]
    if isinstance(v, dict):
        return {k: _plano(x) for k, x in v.items()}
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    return str(v)


def neo_leer_libre(query: str, params: dict, limite: int = 200, timeout: float = 10.0) -> dict:
    """Ejecuta Cypher escrito por el administrador en una transacción de SOLO LECTURA (el servidor rechaza escrituras)."""
    from neo4j import unit_of_work

    @unit_of_work(timeout=timeout)
    def trabajo(tx):
        res = tx.run(query, params)
        filas = [r.values() for _, r in zip(range(limite + 1), res)]
        return res.keys(), filas

    t0 = time.perf_counter()
    with driver().session(database=config.NEO4J_DATABASE, default_access_mode="r") as s:
        claves, filas = s.execute_read(trabajo)
    ms = (time.perf_counter() - t0) * 1000
    return {"columnas": list(claves), "filas": [[_plano(x) for x in f] for f in filas[:limite]],
            "truncado": len(filas) > limite, "ms": ms}


def neo_version() -> str:
    rows = neo_read("CALL dbms.components() YIELD name, versions, edition RETURN name, versions[0] AS version, edition")
    return f"{rows[0]['name']} {rows[0]['version']} ({rows[0]['edition']})" if rows else "Neo4j"


# ------------------------------------------------------------------ PostgreSQL
def _ensure_database() -> None:
    """Si la base indicada en PG_DSN no existe, intenta crearla (best effort)."""
    info = pg_conninfo.conninfo_to_dict(config.PG_DSN)
    nombre = info.get("dbname") or "uni"
    admin = dict(info, dbname="postgres")
    with psycopg.connect(**admin, autocommit=True) as conn:
        existe = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (nombre,)).fetchone()
        if not existe:
            conn.execute(pg_sql.SQL("CREATE DATABASE {}").format(pg_sql.Identifier(nombre)))


def pool() -> ConnectionPool:
    global _pool
    with _lock:
        if _pool is None:
            try:
                p = ConnectionPool(config.PG_DSN, min_size=1, max_size=6, open=False, kwargs={"connect_timeout": 5})
                p.open(wait=True, timeout=6)
            except Exception:
                try:
                    _ensure_database()
                    p = ConnectionPool(config.PG_DSN, min_size=1, max_size=6, open=False, kwargs={"connect_timeout": 5})
                    p.open(wait=True, timeout=6)
                except Exception as exc:
                    raise HTTPException(
                        503,
                        "No se pudo conectar a PostgreSQL. Revisa PG_DSN en .env y que el servidor esté "
                        f"encendido (por ejemplo: docker compose up -d). Detalle: {exc}",
                    )
            _pool = p
        return _pool


def pg_run(sql: str, params: Optional[Union[dict, tuple]] = None) -> list[dict]:
    with pool().connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, params)
        return cur.fetchall() if cur.description else []


def pg_exec(sql: str, params: Optional[Union[dict, tuple]] = None) -> None:
    with pool().connection() as conn:
        conn.execute(sql, params)


def pg_timed(sql: str, params: dict) -> dict:
    """Ejecuta una lectura en PostgreSQL. La base es local: no hay red de por medio."""
    p = pool()
    with p.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        t0 = time.perf_counter()
        cur.execute(sql, params)
        rows = cur.fetchall()
        ms = (time.perf_counter() - t0) * 1000
    return {"rows": rows, "motor_ms": ms, "total_ms": ms}


def pg_explain(sql: str, params: dict) -> list[str]:
    """EXPLAIN ANALYZE con parámetros incrustados del lado del cliente (EXPLAIN no admite $1)."""
    with pool().connection() as conn, psycopg.ClientCursor(conn) as cur:
        cur.execute("EXPLAIN (ANALYZE, BUFFERS) " + sql, params)
        return [r[0] for r in cur.fetchall()]


def pg_version() -> str:
    rows = pg_run("SELECT version() AS v")
    return " ".join(rows[0]["v"].split()[:2]) if rows else "PostgreSQL"
