"""Pestaña de comparación: ejecuta la misma pregunta en Neo4j y en PostgreSQL y mide ambos."""
from typing import Optional
import statistics

from fastapi import APIRouter, Depends

import config
import dataset as ds
import db
import domain as dm
import loaders
import queries as Q
import scenarios as S
from routers.auth import admin_actual

router = APIRouter(prefix="/api/admin", dependencies=[Depends(admin_actual)])


# ------------------------------------------------------------------ escenarios y muestras
@router.get("/comparar/escenarios")
def escenarios():
    claves = ("id", "titulo", "tema", "pregunta", "sujeto", "cypher", "sql", "sql_mat", "cols",
              "nivel", "nivel_nombre", "que_mide", "que_esperar")
    return [{k: e[k] for k in claves} for e in S.ESCENARIOS]


@router.get("/comparar/muestra")
def muestra(sujeto: str = "estudiante", alcance: str = "base", modo: str = "tipico"):
    sint = alcance == "volumen"
    if sujeto == "ninguno":
        return {"id": None}
    if sujeto == "curso":
        r = db.neo_read(Q.MUESTRA_CURSO_PROFUNDO, sintetico=sint)
    elif modo == "azar":
        r = db.neo_read(Q.MUESTRA_EST_AZAR, sintetico=sint)
    else:
        r = db.neo_read(Q.MUESTRA_EST_VOLUMEN if sint else Q.MUESTRA_EST_BASE)
    if not r:
        dm.fallo("No hay datos de ese alcance. Genera datos de volumen en «Datos y volumen».", 404)
    return {"id": r[0]["id"]}


# ------------------------------------------------------------------ ejecución con medición
def _stats(xs: list[float]) -> dict:
    xs = sorted(xs)
    return {"min": round(xs[0], 3), "mediana": round(statistics.median(xs), 3), "media": round(statistics.fmean(xs), 3),
            "max": round(xs[-1], 3), "p95": round(xs[min(len(xs) - 1, int(len(xs) * 0.95))], 3)}


def _resumir(ultimo: dict, motor: list, total: list) -> dict:
    return {"motor": _stats(motor), "total": _stats(total), "muestras": [round(x, 3) for x in total],
            "muestras_motor": [round(x, 3) for x in motor],
            "filas": len(ultimo["rows"]), "resultado": ultimo["rows"][:20]}


def _medir_ambas(fn_neo, fn_pg, reps: int, calentar: bool, intercalar: bool) -> tuple:
    """Mide las dos bases en las MISMAS condiciones.

    - calentar: una ejecución previa que no cuenta (llena cachés y planes) en cada base.
    - intercalar: en cada repetición alterna quién va primero (N, P, P, N, …) para que cualquier
      variación del equipo (CPU, red, otras tareas) afecte por igual a las dos.
    """
    if calentar:
        fn_neo()
        fn_pg()
    mn, tn, mp, tp, un, up = [], [], [], [], None, None
    for i in range(reps):
        orden = ("n", "p") if (not intercalar or i % 2 == 0) else ("p", "n")
        for quien in orden:
            if quien == "n":
                un = fn_neo()
                mn.append(un["motor_ms"]); tn.append(un["total_ms"])
            else:
                up = fn_pg()
                mp.append(up["motor_ms"]); tp.append(up["total_ms"])
    return _resumir(un, mn, tn), _resumir(up, mp, tp)


_RTT = {"t": 0.0, "v": None}


def _latencia_neo(forzar: bool = False) -> dict:
    """Ida y vuelta de red hasta Neo4j: tiempo visto desde la app menos el tiempo que dice el motor."""
    import time
    if not forzar and _RTT["v"] and time.time() - _RTT["t"] < 60:
        return _RTT["v"]
    dif, tot = [], []
    db.neo_timed("RETURN 1 AS x", {})
    for _ in range(7):
        r = db.neo_timed("RETURN 1 AS x", {})
        dif.append(max(r["total_ms"] - r["motor_ms"], 0.0)); tot.append(r["total_ms"])
    v = {"red_ms": round(statistics.median(dif), 1), "consulta_vacia_ms": round(statistics.median(tot), 1)}
    _RTT.update(t=time.time(), v=v)
    return v


@router.get("/comparar/latencia")
def latencia():
    return _latencia_neo(forzar=True)


def _params(esc: dict, sujeto) -> dict:
    return {"id": sujeto, "periodo": config.PERIODO_ACTUAL}


def _escenario(eid: str) -> dict:
    e = S.POR_ID.get(eid)
    if not e:
        dm.fallo("Escenario desconocido.", 404)
    return e


@router.post("/comparar/ejecutar")
def ejecutar(body: dict):
    esc = _escenario(body.get("escenario"))
    reps = dm.entero(body.get("repeticiones") or 5, "repeticiones", 1, 30)
    variante = "sql_mat" if body.get("variante") == "sql_mat" and esc["sql_mat"] else "sql"
    sujeto = body.get("sujeto") if esc["sujeto"] != "ninguno" else None
    if esc["sujeto"] != "ninguno":
        sujeto = dm.texto(sujeto, "sujeto", largo=20)
    # ---- variables de justicia
    metrica = "motor" if body.get("metrica") == "motor" else "total"
    red_modo = body.get("red_pg") if body.get("red_pg") in ("ninguna", "igualar", "manual") else "igualar"
    calentar = body.get("calentar") is not False
    intercalar = body.get("intercalar") is not False
    if red_modo == "igualar":
        red_ms = _latencia_neo()["red_ms"]
    elif red_modo == "manual":
        red_ms = float(dm.entero(body.get("red_pg_ms") or 0, "red_pg_ms", 0, 1000))
    else:
        red_ms = 0.0
    p = _params(esc, sujeto)
    neo, pg = _medir_ambas(lambda: db.neo_timed(esc["cypher"], p), lambda: db.pg_timed(esc[variante], p, red_ms),
                           reps, calentar, intercalar)
    iguales = S.equivalentes(neo["resultado"], pg["resultado"], esc["cols"])
    tn, tp = neo[metrica]["mediana"], pg[metrica]["mediana"]
    gana = "neo4j" if tn < tp else "postgres" if tp < tn else "empate"
    razon = round(max(tn, tp) / max(min(tn, tp), 0.001), 2)
    return {"escenario": esc["id"], "sujeto": sujeto, "variante": variante, "repeticiones": reps,
            "neo4j": neo, "postgres": pg, "equivalentes": iguales,
            "veredicto": {"metrica": metrica, "ganador": gana, "veces": razon,
                          "empate_tecnico": razon < 1.15 or max(tn, tp) < 3.0},
            "justicia": {"metrica": metrica, "red_pg": red_modo, "red_pg_ms": red_ms, "calentar": calentar,
                         "intercalar": intercalar, "variante": variante, "repeticiones": reps,
                         "datos": "volumen" if body.get("alcance") == "volumen" else "base"},
            "nota_tiempos": ("«Motor» es el tiempo que la base tarda en resolver la consulta; «Total» es lo que "
                             "espera la aplicación (motor + red). Neo4j Aura está en la nube, PostgreSQL es local"
                             + (f", por eso se le sumaron {red_ms:g} ms simulados de red." if red_ms else "."))}


# ------------------------------------------------------------------ planes de ejecución
def _aplanar(op: dict, nivel: int = 0, out: Optional[list] = None) -> list[str]:
    out = [] if out is None else out
    if not op:
        return out
    args = op.get("args") or {}
    out.append("  " * nivel + f"{op.get('operatorType') or op.get('operator_type')}"
               f"  filas={args.get('Rows', args.get('rows', '?'))}  dbHits={args.get('DbHits', args.get('db_hits', '?'))}")
    for h in op.get("children") or []:
        _aplanar(h, nivel + 1, out)
    return out


@router.post("/comparar/plan")
def plan(body: dict):
    esc = _escenario(body.get("escenario"))
    variante = "sql_mat" if body.get("variante") == "sql_mat" and esc["sql_mat"] else "sql"
    sujeto = body.get("sujeto") if esc["sujeto"] != "ninguno" else None
    p = _params(esc, sujeto)
    return {"neo4j": _aplanar(db.neo_profile(esc["cypher"], p)), "postgres": db.pg_explain(esc[variante], p)}


# ------------------------------------------------------------------ estado de las bases
def _pg_conteos() -> dict:
    out = {}
    for t in loaders.PG_TABLAS:
        out[t] = db.pg_run(f"SELECT count(*) AS n FROM {t}")[0]["n"]
    out["curso_similar"] = db.pg_run("SELECT count(*) AS n FROM curso_similar")[0]["n"]
    return out


@router.get("/estado")
def estado():
    resp = {"periodo": config.PERIODO_ACTUAL, "aura": {"max_nodos": config.AURA_MAX_NODOS, "max_relaciones": config.AURA_MAX_RELS}}
    try:
        resp["neo4j"] = {"version": db.neo_version(), **loaders.conteos_neo()}
    except Exception as exc:  # noqa: BLE001
        resp["neo4j"] = {"error": getattr(exc, "detail", None) or str(exc)}
    try:
        resp["postgres"] = {"version": db.pg_version(), "tablas": _pg_conteos()}
    except Exception as exc:  # noqa: BLE001
        resp["postgres"] = {"error": getattr(exc, "detail", None) or str(exc)}
    n, p = resp["neo4j"], resp["postgres"]
    if "error" not in n and "error" not in p:
        t = p["tablas"]
        resp["sincronizado"] = (n["nodos"].get("Estudiante", 0) == t["estudiante"]
                                and n["nodos"].get("Curso", 0) == t["curso"]
                                and n["relaciones"].get("HA_CURSADO", 0) == t["matricula"])
    else:
        resp["sincronizado"] = False
    return resp


# ------------------------------------------------------------------ datos y volumen
@router.get("/datos/estimar")
def estimar(estudiantes: int = 1000, cursos: int = 60):
    return ds.estimar(estudiantes, cursos)


def _lanzar(nombre, fn):
    try:
        return {"job": loaders.lanzar(nombre, fn)}
    except RuntimeError as exc:
        dm.fallo(str(exc), 409)


@router.post("/datos/generar")
def generar(body: dict):
    n_est = dm.entero(body.get("estudiantes"), "estudiantes", 10, 15000)
    n_cur = dm.entero(body.get("cursos"), "cursos", 10, 400)
    return _lanzar("Generar datos de volumen", loaders.tarea_generar(n_est, n_cur))


@router.post("/datos/limpiar")
def limpiar():
    return _lanzar("Eliminar datos de volumen", loaders.tarea_limpiar())


@router.post("/datos/sincronizar")
def sincronizar():
    return _lanzar("Sincronizar PostgreSQL", loaders.tarea_sync())


@router.get("/datos/job/{jid}")
def job(jid: str):
    j = loaders.JOBS.get(jid)
    if not j:
        dm.fallo("Proceso desconocido.", 404)
    return j
