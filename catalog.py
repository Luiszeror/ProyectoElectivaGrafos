"""Catálogo de cursos en memoria (con caché corta) leído de Neo4j.

Se invalida cada vez que el administrador cambia cursos, docentes, áreas, etc.
"""
import threading
import time

import config
import db
import queries as Q

TTL = 30
_lock = threading.Lock()
_cache: dict = {}


def invalidate() -> None:
    with _lock:
        _cache.clear()


def cursos(todos: bool = False) -> dict[str, dict]:
    """{codigo: curso} con áreas, programas, sedes (periodo actual), prerrequisitos y docentes."""
    with _lock:
        hit = _cache.get(todos)
        if hit and time.time() - hit[0] < TTL:
            return hit[1]
    p = {"todos": todos, "periodo": config.PERIODO_ACTUAL}
    base = {r["codigo"]: {**r, "areas": [], "programas": [], "sedes": [], "prerreq": [], "docentes": []}
            for r in db.neo_read(Q.CAT_CURSOS, **p)}
    def poner(query, clave, mapa):
        for r in db.neo_read(query, **p):
            c = base.get(r["curso"])
            if c is not None:
                c[clave].append(mapa(r))
    poner(Q.CAT_AREAS, "areas", lambda r: {"codigo": r["area"], "nombre": r["nombre"], "peso": r["peso"]})
    poner(Q.CAT_PROGRAMAS, "programas", lambda r: {"codigo": r["programa"], "nombre": r["nombre"],
                                                   "semestre": r["semestre"], "obligatorio": r["obligatorio"]})
    poner(Q.CAT_SEDES, "sedes", lambda r: {"codigo": r["sede"], "nombre": r["nombre"], "cupos": r["cupos"]})
    poner(Q.CAT_PRERREQ, "prerreq", lambda r: {"codigo": r["requisito"], "nombre": r["nombre"], "tipo": r["tipo"]})
    poner(Q.CAT_DOCENTES, "docentes", lambda r: {"id": r["docente"], "nombre": r["nombre"], "grupo": r["grupo"]})
    with _lock:
        _cache[todos] = (time.time(), base)
    return base


def ocupacion() -> dict[str, int]:
    return {r["curso"]: r["ocupados"] for r in db.neo_read(Q.OCUPACION, periodo=config.PERIODO_ACTUAL)}
