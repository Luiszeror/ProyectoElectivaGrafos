"""Acceso: estudiante (iniciar sesión / crear) y administrador. Sin contraseñas: es una demostración."""
from typing import Optional
import secrets
from datetime import date

from fastapi import APIRouter, Header

import config
import db
import domain as dm
import queries as Q

router = APIRouter(prefix="/api/auth")
SESIONES: dict[str, dict] = {}


def _nueva(rol: str, **datos) -> dict:
    token = secrets.token_urlsafe(16)
    SESIONES[token] = {"rol": rol, **datos}
    return {"token": token, "rol": rol, **datos}


def sesion(token: Optional[str], rol: str) -> dict:
    s = SESIONES.get(token or "")
    if not s or s["rol"] != rol:
        dm.fallo("Sesión no válida. Vuelve a iniciar sesión.", 401)
    return s


def estudiante_actual(x_token: Optional[str] = Header(default=None)) -> dict:
    return sesion(x_token, "estudiante")


def admin_actual(x_token: Optional[str] = Header(default=None)) -> dict:
    return sesion(x_token, "admin")


@router.get("/info")
def info():
    return {
        "periodo": config.PERIODO_ACTUAL,
        "admin_pin": bool(config.ADMIN_PIN),
        "programas": db.neo_read(Q.LISTA_PROGRAMAS, todos=False),
        "estudiantes_demo": db.neo_read(Q.EST_DEMO),
    }


@router.post("/estudiante/entrar")
def entrar(body: dict):
    eid = dm.texto(body.get("id"), "id", largo=20).upper()
    r = db.neo_read(Q.EST_POR_ID, id=eid)
    if not r:
        dm.fallo(f"No existe el estudiante {eid}. Puedes crearlo con «Crear estudiante».", 404)
    return _nueva("estudiante", id=r[0]["id"], nombre=r[0]["nombre"])


@router.post("/estudiante/crear")
def crear(body: dict):
    nombre = dm.texto(body.get("nombre"), "nombre", largo=60)
    semestre = dm.entero(body.get("semestre"), "semestre", 1, 12)
    programa = dm.texto(body.get("programa"), "programa")
    if not any(p["codigo"] == programa for p in db.neo_read(Q.LISTA_PROGRAMAS, todos=False)):
        dm.fallo("El programa elegido no existe.")
    eid = f"E{db.neo_read(Q.EST_MAX_ID)[0]['maximo'] + 1}"
    anio = date.today().year - (semestre - 1) // 2
    db.neo_write(Q.EST_CREAR, id=eid, nombre=nombre, semestre=semestre, programa=programa, anio=anio)
    return _nueva("estudiante", id=eid, nombre=nombre, nuevo=True)


@router.post("/admin/entrar")
def admin(body: dict):
    if config.ADMIN_PIN and str(body.get("pin", "")) != config.ADMIN_PIN:
        dm.fallo("PIN de administrador incorrecto.", 401)
    return _nueva("admin", nombre="Administrador")


@router.post("/salir")
def salir(x_token: Optional[str] = Header(default=None)):
    SESIONES.pop(x_token or "", None)
    return {"ok": True}
