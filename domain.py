"""Reglas de negocio y validaciones compartidas (sin acceso a bases de datos).

Todo lo que el sistema "sabe" sobre cómo funciona la universidad vive aquí:
dominios del diccionario de datos, nota de aprobación y reglas de inscripción.
"""
from typing import Optional
import re

from fastapi import HTTPException

NOTA_APROBACION = 3.0
NOTA_MIN, NOTA_MAX = 0.0, 5.0
TIPOS_CURSO = ["OBLIGATORIO", "ELECTIVO"]
NIVELES_CURSO = ["Básico", "Intermedio", "Avanzado"]
TIPOS_REQUIERE = ["PRERREQUISITO", "CORREQUISITO"]
ESTADOS = ["APROBADO", "REPROBADO", "EN_CURSO"]
_PERIODO = re.compile(r"^\d{4}-\d$")
_CODIGO = re.compile(r"^[A-Za-z0-9_-]{2,12}$")


# ---------------------------------------------------------------- validación de entradas
def fallo(msg: str, code: int = 422):
    raise HTTPException(code, msg)


def texto(v, campo: str, *, req: bool = True, largo: int = 80) -> Optional[str]:
    v = "" if v is None else str(v).strip()
    if not v:
        if req:
            fallo(f"'{campo}' es obligatorio")
        return None
    if len(v) > largo:
        fallo(f"'{campo}' admite como máximo {largo} caracteres")
    return v


def codigo(v, campo: str = "codigo") -> str:
    v = texto(v, campo)
    if not _CODIGO.match(v):
        fallo(f"'{campo}' debe tener 2 a 12 caracteres: letras, números, guion o guion bajo")
    return v


def entero(v, campo: str, lo: int, hi: int, *, req: bool = True) -> Optional[int]:
    if v is None or v == "":
        if req:
            fallo(f"'{campo}' es obligatorio")
        return None
    try:
        n = int(v)
    except (TypeError, ValueError):
        fallo(f"'{campo}' debe ser un número entero")
    if not lo <= n <= hi:
        fallo(f"'{campo}' debe estar entre {lo} y {hi}")
    return n


def decimal(v, campo: str, lo: float, hi: float, *, req: bool = True) -> Optional[float]:
    if v is None or v == "":
        if req:
            fallo(f"'{campo}' es obligatorio")
        return None
    try:
        n = float(v)
    except (TypeError, ValueError):
        fallo(f"'{campo}' debe ser un número")
    if not lo <= n <= hi:
        fallo(f"'{campo}' debe estar entre {lo} y {hi}")
    return round(n, 2)


def opcion(v, campo: str, opciones: list[str]) -> str:
    if v not in opciones:
        fallo(f"'{campo}' debe ser uno de: {', '.join(opciones)}")
    return v


def periodo(v, campo: str = "periodo") -> str:
    v = texto(v, campo)
    if not _PERIODO.match(v):
        fallo(f"'{campo}' debe tener formato AAAA-S, por ejemplo 2026-2")
    return v


def nota(v, campo: str = "nota") -> float:
    return round(decimal(v, campo, NOTA_MIN, NOTA_MAX), 1)


# ---------------------------------------------------------------- reglas académicas
def estado_por_nota(n: float) -> str:
    """Se aprueba con 3.0 o más."""
    return "APROBADO" if n >= NOTA_APROBACION else "REPROBADO"


def estado_actual(estados: list[str]) -> Optional[str]:
    """Estado vigente de un curso para un estudiante, mirando todos sus intentos.

    Aprobado manda sobre todo; si está cursándolo, EN_CURSO; si solo tiene intentos
    perdidos, REPROBADO (puede repetirlo); si nunca lo intentó, None.
    """
    for e in ("APROBADO", "EN_CURSO", "REPROBADO"):
        if e in estados:
            return e
    return None


def evaluar_inscripcion(curso: dict, estado: Optional[str], aprobados: set, en_curso: set,
                        ocupados: int, periodo_actual: str) -> dict:
    """Decide si un estudiante puede inscribir un curso este periodo y por qué sí o no.

    Reglas: (1) no repetir lo aprobado ni lo que ya cursa; (2) debe ofrecerse en el periodo;
    (3) debe haber cupos; (4) prerrequisitos aprobados; (5) correquisitos aprobados o en curso.
    """
    motivos: list[str] = []
    if estado == "APROBADO":
        motivos.append("Ya aprobaste este curso.")
    elif estado == "EN_CURSO":
        motivos.append("Ya estás inscrito en este curso.")

    sedes = curso.get("sedes") or []
    if not sedes:
        motivos.append(f"No se ofrece en el periodo {periodo_actual}.")
    elif sum(s.get("cupos") or 0 for s in sedes) - ocupados <= 0:
        motivos.append("No quedan cupos disponibles.")

    requisitos = []
    for r in curso.get("prerreq") or []:
        if r["tipo"] == "CORREQUISITO":
            cumplido = r["codigo"] in aprobados or r["codigo"] in en_curso
            if not cumplido:
                motivos.append(f"Requiere correquisito: {r['nombre']} ({r['codigo']}). Inscríbelo primero.")
        else:
            cumplido = r["codigo"] in aprobados
            if not cumplido:
                motivos.append(f"Falta aprobar el prerrequisito: {r['nombre']} ({r['codigo']}).")
        requisitos.append({**r, "cumplido": cumplido})

    return {"puede": not motivos, "motivos": motivos, "requisitos": requisitos,
            "cupos_libres": max(0, sum(s.get("cupos") or 0 for s in sedes) - ocupados) if sedes else 0}


# ---------------------------------------------------------------- esquema lógico (para la UI de modelos)
NODOS = {
    "Estudiante": {"clave": "id", "props": ["nombre", "semestre"], "tabla": "estudiante", "pk": "id_estudiante"},
    "Docente": {"clave": "id", "props": ["nombre"], "tabla": "docente", "pk": "id_docente"},
    "Curso": {"clave": "codigo", "props": ["nombre", "tipo", "nivel"], "tabla": "curso", "pk": "codigo"},
    "Programa": {"clave": "codigo", "props": ["nombre"], "tabla": "programa", "pk": "id_programa"},
    "Facultad": {"clave": "codigo", "props": ["nombre"], "tabla": "facultad", "pk": "id_facultad"},
    "Sede": {"clave": "codigo", "props": ["nombre"], "tabla": "sede", "pk": "id_sede"},
    "Area": {"clave": "codigo", "props": ["nombre"], "tabla": "area", "pk": "id_area"},
}

RELACIONES = {
    "HA_CURSADO": {"de": "Estudiante", "a": "Curso", "props": ["periodo", "nota", "estado"], "mult": "N:M",
                   "origen": "tabla MATRICULA"},
    "ESTUDIA_EN": {"de": "Estudiante", "a": "Programa", "props": ["anio_ingreso"], "mult": "N:1",
                   "origen": "FK ESTUDIANTE.id_programa"},
    "INTERESADO_EN": {"de": "Estudiante", "a": "Area", "props": ["nivel"], "mult": "N:M",
                      "origen": "tabla INTERES_ESTUDIANTE"},
    "DICTA": {"de": "Docente", "a": "Curso", "props": ["periodo", "grupo"], "mult": "N:M", "origen": "tabla DICTADO"},
    "INCLUIDO_EN": {"de": "Curso", "a": "Programa", "props": ["semestre_sugerido", "es_obligatorio"], "mult": "N:M",
                    "origen": "tabla CURSO_PROGRAMA"},
    "TRATA_DE": {"de": "Curso", "a": "Area", "props": ["peso"], "mult": "N:M", "origen": "tabla CURSO_AREA"},
    "REQUIERE": {"de": "Curso", "a": "Curso", "props": ["tipo"], "mult": "N:M", "origen": "tabla PRERREQUISITO"},
    "SIMILAR_A": {"de": "Curso", "a": "Curso", "props": ["peso", "criterio"], "mult": "N:M",
                  "origen": "Derivada (se calcula)", "derivada": True},
    "SE_DICTA_EN": {"de": "Curso", "a": "Sede", "props": ["periodo", "cupos"], "mult": "N:M",
                    "origen": "tabla CURSO_SEDE"},
    "PERTENECE_A": {"de": "Programa", "a": "Facultad", "props": [], "mult": "N:1", "origen": "FK PROGRAMA.id_facultad"},
    "SE_OFRECE_EN": {"de": "Programa", "a": "Sede", "props": [], "mult": "N:M", "origen": "tabla PROGRAMA_SEDE"},
}
