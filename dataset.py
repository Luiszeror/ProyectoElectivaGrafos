"""Datos sintéticos: el conjunto base (15 cursos, 10 estudiantes) y un generador de volumen.

El conjunto base conserva EXACTAMENTE los datos del avance anterior (E1-E3, C101-C304, A1-A5,
P1-P2, S1-S2, D1-D2) y agrega lo necesario para llegar a ~10 estudiantes y ~15 cursos.
Todo se describe como listas de tuplas, iguales a las tablas del modelo relacional.
"""
import math
import random
from dataclasses import dataclass, field

PERIODO_ACTUAL_DEFAULT = "2026-2"
PERIODOS_PASADOS = ["2021-2", "2022-1", "2022-2", "2023-1", "2023-2", "2024-1", "2024-2", "2025-1", "2025-2", "2026-1"]
NIVEL_IDX = {"Básico": 0, "Intermedio": 1, "Avanzado": 2}


@dataclass
class Dataset:
    facultad: list = field(default_factory=list)          # (id, nombre)
    sede: list = field(default_factory=list)               # (id, nombre)
    area: list = field(default_factory=list)               # (id, nombre)
    docente: list = field(default_factory=list)            # (id, nombre)
    programa: list = field(default_factory=list)           # (id, nombre, id_facultad)
    curso: list = field(default_factory=list)              # (codigo, nombre, tipo, nivel)
    estudiante: list = field(default_factory=list)         # (id, nombre, semestre, id_programa, anio_ingreso)
    programa_sede: list = field(default_factory=list)      # (id_programa, id_sede)
    curso_programa: list = field(default_factory=list)     # (curso, programa, semestre_sugerido, es_obligatorio)
    curso_area: list = field(default_factory=list)         # (curso, area, peso)
    prerrequisito: list = field(default_factory=list)      # (curso, requisito, tipo)
    curso_sede: list = field(default_factory=list)         # (curso, sede, periodo, cupos)
    dictado: list = field(default_factory=list)            # (docente, curso, periodo, grupo)
    interes_estudiante: list = field(default_factory=list) # (estudiante, area, nivel)
    matricula: list = field(default_factory=list)          # (estudiante, curso, periodo, nota, estado)

    def tablas(self) -> dict:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}

    def contar(self) -> dict:
        return {k: len(v) for k, v in self.tablas().items()}


def derivar_similar(curso_area: list) -> dict:
    """SIMILAR_A: dos cursos son similares si comparten áreas; el peso es cuántas comparten.

    Devuelve {(a, b): peso} con AMBOS sentidos, igual que las dos relaciones del grafo.
    """
    por_area: dict[str, list[str]] = {}
    for curso, area, _ in curso_area:
        por_area.setdefault(area, []).append(curso)
    pares: dict[tuple, int] = {}
    for cursos in por_area.values():
        cursos = sorted(set(cursos))
        for i, a in enumerate(cursos):
            for b in cursos[i + 1:]:
                pares[(a, b)] = pares.get((a, b), 0) + 1
    out = {}
    for (a, b), n in pares.items():
        out[(a, b)] = n
        out[(b, a)] = n
    return out


# ================================================================== conjunto base
def base() -> Dataset:
    d = Dataset()
    d.facultad = [("F1", "Ingeniería"), ("F2", "Ciencias")]
    d.programa = [("P1", "Ingeniería de Sistemas", "F1"), ("P2", "Matemáticas", "F2")]
    d.sede = [("S1", "Sede Norte"), ("S2", "Sede Centro")]
    d.programa_sede = [("P1", "S1"), ("P1", "S2"), ("P2", "S2")]
    d.area = [("A1", "Bases de datos"), ("A2", "Inteligencia artificial"), ("A3", "Redes"),
              ("A4", "Programación"), ("A5", "Estadística")]
    d.docente = [("D1", "Docente Uno"), ("D2", "Docente Dos"), ("D3", "Docente Tres"), ("D4", "Docente Cuatro")]
    d.curso = [
        ("C101", "Bases de Datos I", "OBLIGATORIO", "Básico"),
        ("C102", "Programación I", "OBLIGATORIO", "Básico"),
        ("C103", "Algoritmos y Estructuras de Datos", "OBLIGATORIO", "Básico"),
        ("C201", "Bases de Datos II", "OBLIGATORIO", "Intermedio"),
        ("C202", "Minería de Datos", "ELECTIVO", "Intermedio"),
        ("C203", "Estadística I", "OBLIGATORIO", "Básico"),
        ("C204", "Probabilidad", "OBLIGATORIO", "Intermedio"),
        ("C205", "Ingeniería de Software", "OBLIGATORIO", "Intermedio"),
        ("C206", "Visualización de Datos", "ELECTIVO", "Intermedio"),
        ("C301", "Aprendizaje Automático", "ELECTIVO", "Avanzado"),
        ("C302", "Redes I", "OBLIGATORIO", "Básico"),
        ("C303", "Seguridad Informática", "ELECTIVO", "Intermedio"),
        ("C304", "Bases de Datos NoSQL", "ELECTIVO", "Avanzado"),
        ("C305", "Redes II", "OBLIGATORIO", "Intermedio"),
        ("C306", "Computación en la Nube", "ELECTIVO", "Avanzado"),
    ]
    d.curso_area = [
        ("C101", "A1", 1.0), ("C102", "A4", 1.0), ("C103", "A4", 1.0), ("C201", "A1", 1.0),
        ("C202", "A1", 0.7), ("C202", "A2", 0.6), ("C203", "A5", 1.0), ("C204", "A5", 1.0),
        ("C205", "A4", 0.8), ("C206", "A5", 0.6), ("C206", "A1", 0.5),
        ("C301", "A2", 1.0), ("C301", "A5", 0.5), ("C302", "A3", 1.0),
        ("C303", "A3", 0.8), ("C303", "A4", 0.4), ("C304", "A1", 0.9),
        ("C305", "A3", 1.0), ("C306", "A3", 0.6), ("C306", "A1", 0.5),
    ]
    P = "PRERREQUISITO"
    d.prerrequisito = [
        ("C201", "C101", P), ("C202", "C101", P), ("C301", "C202", P), ("C303", "C302", P), ("C304", "C201", P),
        ("C103", "C102", P), ("C204", "C203", P), ("C205", "C102", P), ("C206", "C203", P),
        ("C305", "C302", P), ("C306", "C305", P),
    ]
    d.curso_programa = [
        ("C101", "P1", 1, True), ("C102", "P1", 1, True), ("C201", "P1", 3, True), ("C302", "P1", 2, True),
        ("C303", "P1", 6, False), ("C304", "P1", 7, False), ("C301", "P1", 8, False),
        ("C202", "P2", 6, False), ("C203", "P2", 1, True), ("C301", "P2", 8, False), ("C101", "P2", 2, False),
        ("C103", "P1", 2, True), ("C205", "P1", 4, True), ("C305", "P1", 5, False), ("C306", "P1", 8, False),
        ("C206", "P1", 6, False), ("C204", "P2", 3, True), ("C206", "P2", 5, False),
    ]
    p = PERIODO_ACTUAL_DEFAULT
    d.dictado = [
        ("D1", "C101", p, 1), ("D1", "C201", p, 1), ("D1", "C304", p, 1),
        ("D2", "C202", p, 1), ("D2", "C301", p, 1), ("D2", "C302", p, 1),
        ("D3", "C102", p, 1), ("D3", "C103", p, 1), ("D3", "C205", p, 1), ("D3", "C303", p, 1),
        ("D4", "C203", p, 1), ("D4", "C204", p, 1), ("D4", "C206", p, 1),
        ("D2", "C305", p, 1), ("D2", "C306", p, 1),
    ]
    d.curso_sede = [
        ("C101", "S1", p, 30), ("C101", "S2", p, 25), ("C202", "S2", p, 20), ("C304", "S1", p, 15),
        ("C301", "S2", p, 20), ("C102", "S1", p, 40), ("C102", "S2", p, 30), ("C103", "S1", p, 30),
        ("C201", "S1", p, 30), ("C203", "S2", p, 35), ("C204", "S2", p, 30), ("C205", "S1", p, 25),
        ("C206", "S2", p, 20), ("C302", "S1", p, 30), ("C303", "S1", p, 20), ("C305", "S2", p, 25),
        ("C306", "S1", p, 15),
    ]
    d.estudiante = [
        ("E1", "Ana", 5, "P1", 2023), ("E2", "Luis", 3, "P1", 2024), ("E3", "Marta", 4, "P2", 2024),
        ("E4", "Sofía", 2, "P1", 2026), ("E5", "Carlos", 6, "P1", 2022), ("E6", "Valentina", 5, "P2", 2023),
        ("E7", "Andrés", 4, "P1", 2024), ("E8", "Camila", 7, "P1", 2022), ("E9", "Julián", 1, "P2", 2026),
        ("E10", "Laura", 3, "P1", 2025),
    ]
    A, R, EC = "APROBADO", "REPROBADO", "EN_CURSO"
    d.matricula = [
        # --- datos originales del avance anterior
        ("E1", "C101", "2025-1", 4.5, A), ("E1", "C102", "2025-1", 4.0, A), ("E1", "C201", "2025-2", 4.2, A),
        ("E2", "C101", "2025-2", 3.5, A), ("E2", "C302", "2025-2", 3.0, A), ("E2", "C102", "2026-1", 2.5, R),
        ("E3", "C203", "2025-1", 4.8, A), ("E3", "C101", "2025-2", 4.0, A),
        # --- nuevos
        ("E1", "C103", p, None, EC),
        ("E3", "C204", "2026-1", 4.2, A),
        ("E4", "C101", "2026-1", 3.8, A), ("E4", "C102", "2026-1", 4.1, A),
        ("E5", "C101", "2023-1", 3.2, A), ("E5", "C102", "2023-1", 3.6, A), ("E5", "C302", "2023-2", 4.0, A),
        ("E5", "C201", "2024-1", 3.4, A), ("E5", "C103", "2024-1", 3.9, A), ("E5", "C305", "2024-2", 3.1, A),
        ("E5", "C205", "2024-2", 2.8, R), ("E5", "C303", "2025-1", 4.3, A), ("E5", "C304", "2025-1", 3.0, A),
        ("E5", "C205", "2025-2", 3.5, A), ("E5", "C306", p, None, EC),
        ("E6", "C203", "2024-1", 4.5, A), ("E6", "C101", "2024-1", 4.0, A), ("E6", "C204", "2024-2", 4.1, A),
        ("E6", "C206", "2025-1", 3.9, A), ("E6", "C202", "2025-1", 3.7, A), ("E6", "C301", "2025-2", 4.4, A),
        ("E7", "C101", "2024-2", 2.5, R), ("E7", "C102", "2024-2", 4.4, A), ("E7", "C101", "2025-1", 3.4, A),
        ("E7", "C302", "2025-1", 3.9, A), ("E7", "C201", "2025-2", 2.9, R), ("E7", "C201", p, None, EC),
        ("E8", "C101", "2023-2", 4.6, A), ("E8", "C102", "2023-2", 4.2, A), ("E8", "C201", "2024-1", 4.4, A),
        ("E8", "C302", "2024-1", 3.8, A), ("E8", "C103", "2024-2", 4.0, A), ("E8", "C205", "2025-1", 4.1, A),
        ("E8", "C202", "2025-2", 4.5, A), ("E8", "C304", "2025-2", 4.0, A), ("E8", "C303", "2026-1", 3.3, A),
        ("E8", "C301", p, None, EC),
        ("E9", "C203", "2026-1", 2.4, R),
        ("E10", "C101", "2025-1", 3.9, A), ("E10", "C102", "2025-1", 3.0, A), ("E10", "C302", "2025-2", 3.6, A),
        ("E10", "C201", p, None, EC),
    ]
    d.interes_estudiante = [
        ("E1", "A2", 5), ("E2", "A3", 4), ("E3", "A1", 3), ("E4", "A4", 4), ("E5", "A3", 5), ("E5", "A1", 3),
        ("E6", "A2", 5), ("E6", "A5", 4), ("E7", "A1", 4), ("E8", "A2", 5), ("E8", "A1", 4),
        ("E9", "A5", 3), ("E10", "A3", 3), ("E10", "A4", 4),
    ]
    return d


# ================================================================== generador de volumen
def estimar(n_est: int, n_cur: int) -> dict:
    """Cuántos nodos y relaciones aproximados crea el generador (para respetar el límite de Aura Free)."""
    n_docentes = n_cur // 4 + 2
    nodos = n_est + n_cur + n_docentes + 3 + 6 + 4 + 12
    rels = n_est * 19 + n_cur * 14 + n_cur * 8   # matrículas+intereses+programa, curso-*, SIMILAR_A
    return {"nodos": nodos, "relaciones": rels}


def generar(n_est: int, n_cur: int, semilla: int = 7, periodo_actual: str = PERIODO_ACTUAL_DEFAULT) -> Dataset:
    """Genera una "isla" de datos de prueba (prefijo S, marcada como sintética).

    No se mezcla con el conjunto base: usa sus propias áreas, programas, sedes, docentes, cursos
    y estudiantes, de modo que el portal de los estudiantes reales no se ve afectado.
    """
    rnd = random.Random(semilla)
    d = Dataset()
    d.facultad = [(f"SF{i}", f"Facultad de prueba {i}") for i in range(1, 4)]
    d.sede = [(f"SS{i}", f"Sede de prueba {i}") for i in range(1, 5)]
    d.area = [(f"SA{i:02d}", f"Área de prueba {i:02d}") for i in range(1, 13)]
    d.programa = [(f"SP{i}", f"Programa de prueba {i}", f"SF{(i - 1) % 3 + 1}") for i in range(1, 7)]
    for prog, _, _ in d.programa:
        for sede in rnd.sample([s for s, _ in d.sede], rnd.randint(1, 2)):
            d.programa_sede.append((prog, sede))
    d.docente = [(f"SD{i:03d}", f"Docente de prueba {i}") for i in range(1, n_cur // 4 + 3)]

    # --- cursos: 40 % básicos, 35 % intermedios, 25 % avanzados (en ese orden, para que los prerrequisitos sean acíclicos)
    niveles = ["Básico"] * round(n_cur * 0.40) + ["Intermedio"] * round(n_cur * 0.35)
    niveles += ["Avanzado"] * (n_cur - len(niveles))
    codigos = [f"SC{i:04d}" for i in range(1, n_cur + 1)]
    areas_de: dict[str, list[str]] = {}
    por_nivel: dict[str, list[str]] = {"Básico": [], "Intermedio": [], "Avanzado": []}
    for cod, nivel in zip(codigos, niveles):
        d.curso.append((cod, f"Curso de prueba {cod[2:]}", rnd.choice(["OBLIGATORIO", "ELECTIVO"]), nivel))
        ars = rnd.sample([a for a, _ in d.area], rnd.randint(1, 3))
        areas_de[cod] = ars
        for a in ars:
            d.curso_area.append((cod, a, rnd.choice([0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0])))
        por_nivel[nivel].append(cod)
    previo = {"Intermedio": "Básico", "Avanzado": "Intermedio"}
    for cod, nivel in zip(codigos, niveles):
        if nivel in previo:
            pool = por_nivel[previo[nivel]]
            afines = [c for c in pool if set(areas_de[c]) & set(areas_de[cod])] or pool
            req = rnd.sample(afines, min(len(afines), 2 if rnd.random() < 0.2 else 1))
            for q in req:
                d.prerrequisito.append((cod, q, "PRERREQUISITO"))
        for prog in rnd.sample([p for p, _, _ in d.programa], rnd.randint(1, 3)):
            sem = {"Básico": rnd.randint(1, 3), "Intermedio": rnd.randint(3, 6), "Avanzado": rnd.randint(6, 9)}[nivel]
            d.curso_programa.append((cod, prog, sem, rnd.random() < 0.5))
        d.dictado.append((rnd.choice(d.docente)[0], cod, periodo_actual, 1))
        for sede in rnd.sample([s for s, _ in d.sede], rnd.randint(1, 2)):
            d.curso_sede.append((cod, sede, periodo_actual, 400))

    prereqs_de: dict[str, list[str]] = {}
    for c, q, _ in d.prerrequisito:
        prereqs_de.setdefault(c, []).append(q)
    nivel_de = {c: NIVEL_IDX[n] for c, _, _, n in d.curso}
    programas = [p for p, _, _ in d.programa]
    areas = [a for a, _ in d.area]

    # --- estudiantes con historial simulado que respeta prerrequisitos
    for i in range(1, n_est + 1):
        eid = f"SE{i:05d}"
        sem = min(10, max(1, int(rnd.triangular(1, 10, 5))))
        prog = rnd.choice(programas)
        d.estudiante.append((eid, f"Estudiante de prueba {i}", sem, prog, 2026 - math.ceil(sem / 2)))
        for a in rnd.sample(areas, rnd.randint(1, 3)):
            d.interes_estudiante.append((eid, a, rnd.randint(1, 5)))

        aprobados: set[str] = set()
        perdidos: list[str] = []
        periodos = PERIODOS_PASADOS[-(sem - 1):] if sem > 1 else []
        for per in periodos:
            k = rnd.randint(3, 5)
            cand = [c for c in codigos if c not in aprobados and all(q in aprobados for q in prereqs_de.get(c, []))]
            if not cand:
                break
            cand.sort(key=lambda c: (nivel_de[c], rnd.random()))
            elegidos = [c for c in perdidos if c in cand and rnd.random() < 0.7][:2]
            resto = [c for c in cand[: 3 * k] if c not in elegidos]
            elegidos += rnd.sample(resto, min(len(resto), k - len(elegidos)))
            nuevos: set[str] = set()
            for c in elegidos:
                n = round(min(5.0, max(0.0, rnd.gauss(3.6, 0.8))), 1)
                if n >= 3.0:
                    d.matricula.append((eid, c, per, n, "APROBADO"))
                    nuevos.add(c)
                    if c in perdidos:
                        perdidos.remove(c)
                else:
                    d.matricula.append((eid, c, per, n, "REPROBADO"))
                    if c not in perdidos:
                        perdidos.append(c)
            aprobados |= nuevos          # se aprueba al final del periodo: valen desde el siguiente
        if rnd.random() < 0.7:
            cand = [c for c in codigos if c not in aprobados and all(q in aprobados for q in prereqs_de.get(c, []))]
            cand.sort(key=lambda c: (nivel_de[c], rnd.random()))
            for c in rnd.sample(cand[:12], min(len(cand[:12]), rnd.randint(3, 4))):
                d.matricula.append((eid, c, periodo_actual, None, "EN_CURSO"))
    return d


# ================================================================== validación de reglas
def validar(d: Dataset) -> list[str]:
    """Revisa que un conjunto de datos cumpla las reglas del diccionario de datos. Devuelve los problemas."""
    errs: list[str] = []
    claves = {
        "facultad": {x[0] for x in d.facultad}, "sede": {x[0] for x in d.sede}, "area": {x[0] for x in d.area},
        "docente": {x[0] for x in d.docente}, "programa": {x[0] for x in d.programa},
        "curso": {x[0] for x in d.curso}, "estudiante": {x[0] for x in d.estudiante},
    }
    for tabla, rows in d.tablas().items():
        if tabla in claves and len({r[0] for r in rows}) != len(rows):
            errs.append(f"{tabla}: llaves repetidas")
    for c, q, _ in d.prerrequisito:
        if c == q:
            errs.append(f"prerrequisito: {c} se exige a sí mismo")
        if c not in claves["curso"] or q not in claves["curso"]:
            errs.append(f"prerrequisito {c}->{q}: curso inexistente")
    for e, c, per, nota, est in d.matricula:
        if e not in claves["estudiante"] or c not in claves["curso"]:
            errs.append(f"matricula {e}/{c}: referencia inexistente")
        if est == "EN_CURSO" and nota is not None:
            errs.append(f"matricula {e}/{c}/{per}: EN_CURSO no lleva nota")
        if est == "APROBADO" and not (nota is not None and nota >= 3.0):
            errs.append(f"matricula {e}/{c}/{per}: APROBADO exige nota >= 3.0")
        if est == "REPROBADO" and not (nota is not None and 0 <= nota < 3.0):
            errs.append(f"matricula {e}/{c}/{per}: REPROBADO exige nota < 3.0")
    reqs: dict[str, list[str]] = {}
    for c, q, t in d.prerrequisito:
        if t == "PRERREQUISITO":
            reqs.setdefault(c, []).append(q)
    aprobado_en: dict[tuple, list[str]] = {}
    for e, c, per, _, est in d.matricula:
        if est == "APROBADO":
            aprobado_en.setdefault((e, c), []).append(per)
    vistos = set()
    for e, c, per, _, est in d.matricula:
        if (e, c, per) in vistos:
            errs.append(f"matricula {e}/{c}/{per}: repetida")
        vistos.add((e, c, per))
        for q in reqs.get(c, []):
            if not any(p < per for p in aprobado_en.get((e, q), [])):
                errs.append(f"matricula {e}/{c}/{per}: no tenía aprobado el prerrequisito {q}")
    return errs
