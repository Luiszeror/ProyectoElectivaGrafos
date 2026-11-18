"""API del administrador: docentes, cursos (con todas sus relaciones), catálogos y notas.

Todas las escrituras van a Neo4j (la base viva). PostgreSQL se actualiza solo con «Sincronizar».
"""
from fastapi import APIRouter, Depends

import catalog
import config
import db
import domain as dm
import queries as Q
from routers.auth import admin_actual

router = APIRouter(prefix="/api/admin", dependencies=[Depends(admin_actual)])


def _ids(query: str, **p) -> set:
    return {r["codigo"] for r in db.neo_read(query, todos=True, **p)}


# ------------------------------------------------------------------ docentes
@router.get("/docentes")
def docentes(todos: bool = False):
    filas = db.neo_read(Q.DOC_LISTA, todos=todos)
    for f in filas:
        f["cursos"] = [c for c in f["cursos"] if c]
    return {"periodo": config.PERIODO_ACTUAL, "docentes": filas}


@router.post("/docentes")
def docente_crear(body: dict):
    nombre = dm.texto(body.get("nombre"), "nombre", largo=60)
    did = f"D{db.neo_read(Q.DOC_MAX_ID)[0]['maximo'] + 1}"
    db.neo_write(Q.DOC_CREAR, id=did, nombre=nombre)
    catalog.invalidate()
    return {"id": did}


@router.put("/docentes/{did}")
def docente_editar(did: str, body: dict):
    if not db.neo_read(Q.DOC_EXISTE, id=did):
        dm.fallo("El docente no existe.", 404)
    db.neo_write(Q.DOC_ACTUALIZAR, id=did, nombre=dm.texto(body.get("nombre"), "nombre", largo=60))
    catalog.invalidate()
    return {"ok": True}


@router.delete("/docentes/{did}")
def docente_borrar(did: str):
    if not db.neo_read(Q.DOC_EXISTE, id=did):
        dm.fallo("El docente no existe.", 404)
    db.neo_write(Q.DOC_BORRAR, id=did)
    catalog.invalidate()
    return {"ok": True}


@router.post("/docentes/{did}/asignar")
def docente_asignar(did: str, body: dict):
    curso = dm.codigo(body.get("curso"), "curso")
    grupo = dm.entero(body.get("grupo") or 1, "grupo", 1, 20)
    if not db.neo_read(Q.DOC_EXISTE, id=did):
        dm.fallo("El docente no existe.", 404)
    if not db.neo_read(Q.CUR_EXISTE, codigo=curso):
        dm.fallo("El curso no existe.", 404)
    db.neo_write(Q.DOC_ASIGNAR, id=did, curso=curso, periodo=config.PERIODO_ACTUAL, grupo=grupo)
    catalog.invalidate()
    return {"ok": True}


@router.post("/docentes/{did}/desasignar")
def docente_desasignar(did: str, body: dict):
    db.neo_write(Q.DOC_DESASIGNAR, id=did, curso=dm.codigo(body.get("curso"), "curso"),
                 periodo=config.PERIODO_ACTUAL, grupo=dm.entero(body.get("grupo") or 1, "grupo", 1, 20))
    catalog.invalidate()
    return {"ok": True}


# ------------------------------------------------------------------ cursos
@router.get("/cursos")
def cursos(todos: bool = False):
    catalog.invalidate()
    return {"periodo": config.PERIODO_ACTUAL, "cursos": list(catalog.cursos(todos).values())}


def _validar_curso(body: dict, codigo: str, nuevo: bool) -> dict:
    nombre = dm.texto(body.get("nombre"), "nombre", largo=80)
    tipo = dm.opcion(body.get("tipo"), "tipo", dm.TIPOS_CURSO)
    nivel = dm.opcion(body.get("nivel"), "nivel", dm.NIVELES_CURSO)

    areas = [{"id": dm.texto(a.get("id"), "área"), "peso": dm.decimal(a.get("peso", 1), "peso", 0.1, 1)}
             for a in body.get("areas") or []]
    if not areas:
        dm.fallo("Un curso debe tratar al menos un área (así se calculan las recomendaciones).")
    programas = [{"id": dm.texto(p.get("id"), "programa"),
                  "semestre": dm.entero(p.get("semestre"), "semestre sugerido", 1, 12, req=False),
                  "obligatorio": bool(p.get("obligatorio"))} for p in body.get("programas") or []]
    requisitos = [{"id": dm.codigo(r.get("id"), "requisito"),
                   "tipo": dm.opcion(r.get("tipo") or "PRERREQUISITO", "tipo de requisito", dm.TIPOS_REQUIERE)}
                  for r in body.get("requisitos") or []]
    sedes = [{"id": dm.texto(s.get("id"), "sede"), "cupos": dm.entero(s.get("cupos"), "cupos", 0, 1000)}
             for s in body.get("sedes") or []]
    docentes = [{"id": dm.texto(d.get("id"), "docente"), "grupo": dm.entero(d.get("grupo") or 1, "grupo", 1, 20)}
                for d in body.get("docentes") or []]

    for lista, nombre_campo, existentes in (
        (areas, "área", _ids(Q.LISTA_AREAS)), (programas, "programa", _ids(Q.LISTA_PROGRAMAS)),
        (sedes, "sede", _ids(Q.LISTA_SEDES)),
        (requisitos, "requisito", {c for c in catalog.cursos(True)}),
        (docentes, "docente", {r["id"] for r in db.neo_read(Q.DOC_LISTA, todos=True)}),
    ):
        for it in lista:
            if it["id"] not in existentes:
                dm.fallo(f"{nombre_campo.capitalize()} «{it['id']}» no existe.")
        if len({it["id"] for it in lista}) != len(lista):
            dm.fallo(f"Hay {nombre_campo}s repetidos.")
    for r in requisitos:
        if r["id"] == codigo:
            dm.fallo("Un curso no puede ser requisito de sí mismo.")
        if not nuevo and r["tipo"] == "PRERREQUISITO" and db.neo_read(Q.CUR_CICLO, requisito=r["id"], curso=codigo)[0]["n"]:
            dm.fallo(f"Ciclo de prerrequisitos: {r['id']} ya depende (directa o indirectamente) de {codigo}.")
    return dict(nombre=nombre, tipo=tipo, nivel=nivel, areas=areas, programas=programas,
                requisitos=requisitos, sedes=sedes, docentes=docentes)


def _escribir_curso(codigo: str, v: dict, nuevo: bool):
    per = config.PERIODO_ACTUAL
    s: list[tuple[str, dict]] = []
    if nuevo:
        s.append((Q.CUR_CREAR, {"codigo": codigo, "nombre": v["nombre"], "tipo": v["tipo"], "nivel": v["nivel"]}))
    else:
        s.append((Q.CUR_ACTUALIZAR, {"codigo": codigo, "nombre": v["nombre"], "tipo": v["tipo"], "nivel": v["nivel"]}))
        for q in (Q.CUR_LIMPIAR_AREAS, Q.CUR_LIMPIAR_PROGRAMAS, Q.CUR_LIMPIAR_REQUISITOS):
            s.append((q, {"codigo": codigo}))
        for q in (Q.CUR_LIMPIAR_SEDES, Q.CUR_LIMPIAR_DOCENTES):
            s.append((q, {"codigo": codigo, "periodo": per}))
        s.append((Q.SIM_BORRAR_UNO, {"codigo": codigo}))
    for q, clave in ((Q.CUR_PONER_AREAS, "areas"), (Q.CUR_PONER_PROGRAMAS, "programas"),
                     (Q.CUR_PONER_REQUISITOS, "requisitos")):
        if v[clave]:
            s.append((q, {"codigo": codigo, "items": v[clave]}))
    for q, clave in ((Q.CUR_PONER_SEDES, "sedes"), (Q.CUR_PONER_DOCENTES, "docentes")):
        if v[clave]:
            s.append((q, {"codigo": codigo, "items": v[clave], "periodo": per}))
    s.append((Q.SIM_CONSTRUIR_UNO, {"codigo": codigo}))   # recalcula SIMILAR_A de este curso, en la misma transacción
    db.neo_tx(s)
    catalog.invalidate()


@router.post("/cursos")
def curso_crear(body: dict):
    codigo = dm.codigo(body.get("codigo"), "codigo") if body.get("codigo") else f"C{db.neo_read(Q.CUR_MAX_CODIGO)[0]['maximo'] + 1}"
    if db.neo_read(Q.CUR_EXISTE, codigo=codigo):
        dm.fallo(f"Ya existe el curso {codigo}.", 409)
    _escribir_curso(codigo, _validar_curso(body, codigo, True), True)
    return {"codigo": codigo}


@router.put("/cursos/{codigo}")
def curso_editar(codigo: str, body: dict):
    if not db.neo_read(Q.CUR_EXISTE, codigo=codigo):
        dm.fallo("El curso no existe.", 404)
    _escribir_curso(codigo, _validar_curso(body, codigo, False), False)
    return {"ok": True}


@router.delete("/cursos/{codigo}")
def curso_borrar(codigo: str, forzar: bool = False):
    if not db.neo_read(Q.CUR_EXISTE, codigo=codigo):
        dm.fallo("El curso no existe.", 404)
    uso = db.neo_read(Q.CUR_USO, codigo=codigo)[0]
    if (uso["matriculas"] or uso["dependientes"]) and not forzar:
        dm.fallo(f"El curso tiene {uso['matriculas']} matrícula(s) y {uso['dependientes']} curso(s) que lo requieren. "
                 "Si lo eliminas se pierde ese historial.", 409)
    db.neo_write(Q.CUR_BORRAR, codigo=codigo)
    catalog.invalidate()
    return {"ok": True}


# ------------------------------------------------------------------ catálogos
def _etiqueta(nombre: str) -> str:
    e = {"facultades": "Facultad", "programas": "Programa", "sedes": "Sede", "areas": "Area"}.get(nombre)
    if not e:
        dm.fallo("Catálogo desconocido.", 404)
    return e


@router.get("/catalogos")
def catalogos(todos: bool = False):
    return {
        "facultades": db.neo_read(Q.LISTA_FACULTADES, todos=todos),
        "programas": db.neo_read(Q.LISTA_PROGRAMAS, todos=todos),
        "sedes": db.neo_read(Q.LISTA_SEDES, todos=todos),
        "areas": db.neo_read(Q.LISTA_AREAS, todos=todos),
        "programa_sedes": db.neo_read(Q.PROGRAMA_SEDES_TODAS),
    }


@router.post("/catalogos/{cat}")
def catalogo_crear(cat: str, body: dict):
    e = _etiqueta(cat)
    codigo, nombre = dm.codigo(body.get("codigo"), "codigo"), dm.texto(body.get("nombre"), "nombre", largo=80)
    if db.neo_read(Q.CATALOGO_EXISTE[e], codigo=codigo):
        dm.fallo(f"Ya existe {codigo}.", 409)
    stm = [(Q.CATALOGO_CREAR[e], {"codigo": codigo, "nombre": nombre})]
    stm += _extras_programa(e, codigo, body)
    db.neo_tx(stm)
    catalog.invalidate()
    return {"ok": True}


def _extras_programa(e: str, codigo: str, body: dict) -> list:
    if e != "Programa":
        return []
    out = [(Q.PROG_LIMPIAR_FACULTAD, {"codigo": codigo}), (Q.PROG_LIMPIAR_SEDES, {"codigo": codigo})]
    if body.get("facultad"):
        if body["facultad"] not in _ids(Q.LISTA_FACULTADES):
            dm.fallo("La facultad no existe.")
        out.append((Q.PROG_PONER_FACULTAD, {"codigo": codigo, "facultad": body["facultad"]}))
    sedes = body.get("sedes") or []
    if not set(sedes) <= _ids(Q.LISTA_SEDES):
        dm.fallo("Alguna sede no existe.")
    if sedes:
        out.append((Q.PROG_PONER_SEDES, {"codigo": codigo, "sedes": sedes}))
    return out


@router.put("/catalogos/{cat}/{codigo}")
def catalogo_editar(cat: str, codigo: str, body: dict):
    e = _etiqueta(cat)
    if not db.neo_read(Q.CATALOGO_EXISTE[e], codigo=codigo):
        dm.fallo("No existe.", 404)
    stm = [(Q.CATALOGO_ACTUALIZAR[e], {"codigo": codigo, "nombre": dm.texto(body.get("nombre"), "nombre", largo=80)})]
    stm += _extras_programa(e, codigo, body)
    db.neo_tx(stm)
    catalog.invalidate()
    return {"ok": True}


@router.delete("/catalogos/{cat}/{codigo}")
def catalogo_borrar(cat: str, codigo: str):
    e = _etiqueta(cat)
    if not db.neo_read(Q.CATALOGO_EXISTE[e], codigo=codigo):
        dm.fallo("No existe.", 404)
    usos = db.neo_read(Q.CATALOGO_USO[e], codigo=codigo)[0]["usos"]
    if usos:
        dm.fallo(f"No se puede eliminar: tiene {usos} relación(es) con otros datos. Quítalas primero.", 409)
    db.neo_write(Q.CATALOGO_BORRAR[e], codigo=codigo)
    catalog.invalidate()
    return {"ok": True}


# ------------------------------------------------------------------ matrículas y notas
@router.get("/matriculas")
def matriculas(estado: str = "", curso: str = "", q: str = "", todos: bool = False):
    return db.neo_read(Q.MATRICULAS, estado=estado, curso=curso, q=q, todos=todos)


@router.put("/matriculas/nota")
def poner_nota(body: dict):
    est, curso = dm.texto(body.get("estudiante"), "estudiante"), dm.codigo(body.get("curso"), "curso")
    per, nota = dm.periodo(body.get("periodo")), dm.nota(body.get("nota"))
    r = db.neo_write(Q.MATRICULA_PONER_NOTA, est=est, curso=curso, periodo=per, nota=nota,
                     estado=dm.estado_por_nota(nota))
    if not r:
        dm.fallo("No existe esa matrícula.", 404)
    return {"ok": True, "estado": r[0]["estado"]}
