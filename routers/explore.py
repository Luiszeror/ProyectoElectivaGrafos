"""Explorador del grafo (administrador): vista general, expansión de vecindad y Cypher de solo lectura."""
import re

from fastapi import APIRouter, Depends

import db
import domain as dm
import queries as Q
from routers.auth import admin_actual

router = APIRouter(prefix="/api/admin", dependencies=[Depends(admin_actual)])

TIPOS = list(dm.RELACIONES)
_PROHIBIDAS = re.compile(r"\b(CREATE|MERGE|DELETE|DETACH|SET|REMOVE|DROP|LOAD\s+CSV|FOREACH|GRANT|DENY|REVOKE|ALTER|RENAME)\b", re.I)


def _red(filas: list[dict]) -> dict:
    nodos, aristas = {}, {}
    for r in filas:
        for k, lab, props in (("aid", "al", "ap"), ("bid", "bl", "bp")):
            if r[k] not in nodos:
                pr = r[props]
                nodos[r[k]] = {"id": r[k], "tipo": r[lab], "nombre": pr.get("nombre") or pr.get("id") or pr.get("codigo"), "props": pr}
        aristas[r["rid"]] = {"id": r["rid"], "de": r["aid"], "a": r["bid"], "tipo": r["tipo"], "props": r["rp"]}
    return {"nodos": list(nodos.values()), "aristas": list(aristas.values())}


def _tipos(txt: str) -> list[str]:
    elegidos = [t for t in (txt or "").split(",") if t in TIPOS]
    return elegidos or [t for t in TIPOS if t != "SIMILAR_A"]


@router.get("/grafo")
def grafo(limite: int = 150, tipos: str = "", todos: bool = False):
    limite = dm.entero(limite, "limite", 10, 500)
    return {"tipos": TIPOS, **_red(db.neo_read(Q.GRAFO_GENERAL, limite=limite, tipos=_tipos(tipos), todos=todos))}


@router.get("/grafo/vecindad")
def vecindad(eid: str, tipos: str = "", limite: int = 60):
    return _red(db.neo_read(Q.GRAFO_VECINDAD, eid=eid, tipos=_tipos(tipos), limite=dm.entero(limite, "limite", 5, 200)))


def _grafo_de(filas: list[list]) -> dict:
    """Extrae nodos y aristas de nodos, relaciones y rutas que aparezcan en el resultado, para dibujarlos."""
    nodos, aristas = {}, {}

    def nodo(n):
        pr = n["props"]
        nodos[n["id"]] = {"id": n["id"], "tipo": (n["etiquetas"] or ["?"])[0], "nombre": pr.get("nombre") or pr.get("id") or pr.get("codigo"), "props": pr}

    def visita(v):
        if isinstance(v, dict):
            t = v.get("_tipo")
            if t == "nodo":
                nodo(v)
            elif t == "relacion":
                aristas[v["id"]] = {"id": v["id"], "de": v["de"], "a": v["a"], "tipo": v["tipo"], "props": v["props"]}
            elif t == "ruta":
                [visita(x) for x in v["nodos"] + v["relaciones"]]
            else:
                [visita(x) for x in v.values()]
        elif isinstance(v, list):
            [visita(x) for x in v]
    visita(filas)
    aristas = {k: a for k, a in aristas.items() if a["de"] in nodos and a["a"] in nodos}
    return {"nodos": list(nodos.values()), "aristas": list(aristas.values())}


@router.post("/cypher")
def cypher(body: dict):
    q = dm.texto(body.get("query"), "consulta", largo=4000)
    if _PROHIBIDAS.search(re.sub(r"'[^']*'|\"[^\"]*\"", "''", q)):
        dm.fallo("Este panel es solo de lectura: no se permiten CREATE, MERGE, DELETE, SET, REMOVE, DROP ni LOAD CSV.", 403)
    try:
        r = db.neo_leer_libre(q, {}, limite=200)
    except Exception as exc:  # noqa: BLE001
        dm.fallo(f"Neo4j rechazó la consulta: {getattr(exc, 'message', None) or str(exc)}", 400)
    return {**r, "grafo": _grafo_de(r["filas"])}
