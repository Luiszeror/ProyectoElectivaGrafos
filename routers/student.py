"""API del portal del estudiante: perfil, catálogo con reglas de inscripción, recomendaciones y red."""
from fastapi import APIRouter, Depends

import catalog
import config
import db
import domain as dm
import queries as Q
from routers.auth import estudiante_actual

router = APIRouter(prefix="/api/estudiante")


def _historial(eid: str) -> list[dict]:
    return db.neo_read(Q.HISTORIAL, id=eid)


def _estados(hist: list[dict]) -> tuple[dict, set, set]:
    por_curso: dict[str, list[str]] = {}
    for h in hist:
        por_curso.setdefault(h["curso"], []).append(h["estado"])
    estado = {c: dm.estado_actual(v) for c, v in por_curso.items()}
    aprobados = {c for c, e in estado.items() if e == "APROBADO"}
    en_curso = {c for c, e in estado.items() if e == "EN_CURSO"}
    return estado, aprobados, en_curso


@router.get("/perfil")
def perfil(s: dict = Depends(estudiante_actual)):
    eid = s["id"]
    filas = db.neo_read(Q.PERFIL, id=eid)
    if not filas:
        dm.fallo("El estudiante ya no existe.", 404)
    p = filas[0]
    hist = _historial(eid)
    estado, aprobados, en_curso = _estados(hist)
    notas = [h["nota"] for h in hist if h["nota"] is not None]
    cat = catalog.cursos()
    sedes_oferta = {c for c, v in cat.items() if v["sedes"]}

    perdidas = []
    for c, e in estado.items():
        if e == "REPROBADO":
            intentos = [h for h in hist if h["curso"] == c]
            perdidas.append({"curso": c, "nombre": intentos[0]["nombre"], "intentos": len(intentos),
                             "ultima_nota": intentos[-1]["nota"], "se_ofrece": c in sedes_oferta})
    pendientes, programa = [], p["programa"]
    obligatorios = db.neo_read(Q.PROGRAMA_OBLIGATORIOS, programa=programa) if programa else []
    for o in obligatorios:
        if o["curso"] not in aprobados:
            pendientes.append({**o, "estado": estado.get(o["curso"])})
    return {
        "perfil": {"id": p["id"], "nombre": p["nombre"], "semestre": p["semestre"], "anio_ingreso": p["anio_ingreso"],
                   "programa": {"codigo": programa, "nombre": p["programa_nombre"]} if programa else None,
                   "facultad": {"codigo": p["facultad"], "nombre": p["facultad_nombre"]} if p["facultad"] else None,
                   "sedes": db.neo_read(Q.PROGRAMA_SEDES, programa=programa) if programa else []},
        "periodo_actual": config.PERIODO_ACTUAL,
        "historial": hist,
        "intereses": db.neo_read(Q.INTERESES, id=eid),
        "resumen": {"aprobados": len(aprobados), "en_curso": len(en_curso), "perdidas": len(perdidas),
                    "promedio": round(sum(notas) / len(notas), 2) if notas else None,
                    "obligatorios_total": len(obligatorios),
                    "obligatorios_aprobados": len(obligatorios) - len(pendientes)},
        "perdidas": perdidas,
        "pendientes_obligatorios": pendientes,
    }


@router.get("/catalogo")
def catalogo(q: str = "", s: dict = Depends(estudiante_actual)):
    hist = _historial(s["id"])
    estado, aprobados, en_curso = _estados(hist)
    ocup = catalog.ocupacion()
    out = []
    ql = q.strip().lower()
    for c in catalog.cursos().values():
        if ql and ql not in c["nombre"].lower() and ql not in c["codigo"].lower():
            continue
        ev = dm.evaluar_inscripcion(c, estado.get(c["codigo"]), aprobados, en_curso,
                                    ocup.get(c["codigo"], 0), config.PERIODO_ACTUAL)
        out.append({**c, "estado": estado.get(c["codigo"]), **ev})
    return {"periodo": config.PERIODO_ACTUAL, "cursos": out}


def _inscripcion_valida(eid: str, curso: str) -> dict:
    c = catalog.cursos().get(curso)
    if not c:
        dm.fallo("El curso no existe.", 404)
    estado, aprobados, en_curso = _estados(_historial(eid))
    ocup = catalog.ocupacion()
    ev = dm.evaluar_inscripcion(c, estado.get(curso), aprobados, en_curso, ocup.get(curso, 0), config.PERIODO_ACTUAL)
    return ev


@router.post("/inscribir")
def inscribir(body: dict, s: dict = Depends(estudiante_actual)):
    curso = dm.codigo(body.get("curso"), "curso")
    ev = _inscripcion_valida(s["id"], curso)
    if not ev["puede"]:
        dm.fallo(" ".join(ev["motivos"]), 409)
    db.neo_write(Q.INSCRIBIR, id=s["id"], curso=curso, periodo=config.PERIODO_ACTUAL)
    return {"ok": True}


@router.post("/retirar")
def retirar(body: dict, s: dict = Depends(estudiante_actual)):
    curso = dm.codigo(body.get("curso"), "curso")
    r = db.neo_write(Q.RETIRAR, id=s["id"], curso=curso, periodo=config.PERIODO_ACTUAL)
    if not r or not r[0]["borradas"]:
        dm.fallo("No estás inscrito en ese curso este periodo.", 404)
    return {"ok": True}


@router.put("/intereses")
def guardar_intereses(body: dict, s: dict = Depends(estudiante_actual)):
    items, vistos = [], set()
    for it in body.get("items") or []:
        area = dm.texto(it.get("area"), "area")
        nivel = dm.entero(it.get("nivel"), "nivel", 1, 5)
        if area not in vistos:
            vistos.add(area)
            items.append({"area": area, "nivel": nivel})
    db.neo_tx([(Q.INTERESES_BORRAR, {"id": s["id"]}), (Q.INTERESES_GUARDAR, {"id": s["id"], "items": items})])
    return {"ok": True, "total": len(items)}


@router.get("/areas")
def areas(s: dict = Depends(estudiante_actual)):
    return db.neo_read(Q.LISTA_AREAS, todos=False)


@router.get("/recomendaciones")
def recomendaciones(s: dict = Depends(estudiante_actual)):
    p = {"id": s["id"]}
    return {
        "por_historial": db.neo_read(Q.REC_HISTORIAL, **p),
        "por_intereses": db.neo_read(Q.REC_INTERESES, **p),
        "otros_programas": db.neo_read(Q.REC_OTROS_PROGRAMAS, **p),
        "estudiantes_similares": db.neo_read(Q.REC_SIMILARES, **p),
        "areas_fortalezas": db.neo_read(Q.AREAS_FORTALEZAS, **p),
        "areas_explorar": db.neo_read(Q.AREAS_EXPLORAR, **p),
    }


@router.get("/red")
def red(s: dict = Depends(estudiante_actual)):
    nodos, aristas = {}, {}
    for r in db.neo_read(Q.RED_ESTUDIANTE, id=s["id"], limite=150):
        for k, lab, props in (("aid", "al", "ap"), ("bid", "bl", "bp")):
            if r[k] not in nodos:
                pr = r[props]
                nodos[r[k]] = {"id": r[k], "tipo": r[lab],
                               "nombre": pr.get("nombre") or pr.get("id") or pr.get("codigo")}
        aristas[r["rid"]] = {"id": r["rid"], "de": r["aid"], "a": r["bid"], "tipo": r["tipo"], "props": r["rp"]}
    return {"nodos": list(nodos.values()), "aristas": list(aristas.values())}
