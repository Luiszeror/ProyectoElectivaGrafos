"""Doble de Neo4j para pruebas: responde a las consultas del proyecto (por su texto exacto) con un
estado en memoria. NO ejecuta Cypher: sirve para probar la lógica de la API y la interfaz sin Aura.
La validez del Cypher real se comprueba con selftest.py contra tu base Aura."""
from typing import Optional
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
import dataset as ds
import db
import loaders
import queries as Q
import reference
import scenarios as S


def _k(x):
    return (len(x), x)


class Fake:
    def __init__(self):
        self.d = ds.base()
        self.sint: set[str] = set()
        self.h = {}
        self._build()

    # ---------------------------------------------------------------- utilidades
    def _build(self):
        pass

    def ref(self):
        return reference.Ref(self.d, config.PERIODO_ACTUAL)

    def vis(self, key, todos):
        return todos or key not in self.sint

    def curso(self, cod):
        return next((c for c in self.d.curso if c[0] == cod), None)

    def nom(self, tabla, key):
        for r in getattr(self.d, tabla):
            if r[0] == key:
                return r[1]

    def listar(self, tabla, todos):
        return [{"codigo": r[0], "nombre": r[1]} for r in sorted(getattr(self.d, tabla), key=lambda r: _k(r[0]))
                if self.vis(r[0], todos)]

    def marcar(self, d: ds.Dataset):
        for t in ("facultad", "sede", "area", "docente", "programa", "curso", "estudiante"):
            self.sint |= {r[0] for r in getattr(d, t)}

    # ---------------------------------------------------------------- Neo4j simulado
    def run(self, q: str, p: dict):
        d = self.d
        todos = p.get("todos", True)
        per = p.get("periodo")
        eid = p.get("id")
        if q == Q.PING:
            return [{"ok": 1}]
        if q == Q.CONTEO_ETIQUETAS:
            return [{"etiqueta": k, "total": len(getattr(d, t))} for k, t in
                    (("Facultad", "facultad"), ("Sede", "sede"), ("Area", "area"), ("Docente", "docente"),
                     ("Programa", "programa"), ("Curso", "curso"), ("Estudiante", "estudiante"))]
        if q == Q.CONTEO_RELACIONES:
            sim = len(ds.derivar_similar(d.curso_area))
            return [{"tipo": k, "total": n} for k, n in (
                ("HA_CURSADO", len(d.matricula)), ("TRATA_DE", len(d.curso_area)), ("REQUIERE", len(d.prerrequisito)),
                ("INCLUIDO_EN", len(d.curso_programa)), ("SE_DICTA_EN", len(d.curso_sede)), ("DICTA", len(d.dictado)),
                ("INTERESADO_EN", len(d.interes_estudiante)), ("SE_OFRECE_EN", len(d.programa_sede)),
                ("ESTUDIA_EN", sum(1 for e in d.estudiante if e[3])), ("PERTENECE_A", len(d.programa)),
                ("SIMILAR_A", sim))]
        # --- acceso
        if q == Q.EST_POR_ID:
            return [{"id": e[0], "nombre": e[1]} for e in d.estudiante if e[0] == eid]
        if q == Q.EST_DEMO:
            return [{"id": e[0], "nombre": e[1]} for e in sorted(d.estudiante, key=lambda e: _k(e[0]))
                    if e[0] not in self.sint][:24]
        if q == Q.EST_MAX_ID:
            ns = [int(e[0][1:]) for e in d.estudiante if e[0][0] == "E" and e[0][1:].isdigit()]
            return [{"maximo": max(ns or [0])}]
        if q == Q.EST_CREAR:
            d.estudiante.append((eid, p["nombre"], p["semestre"], p["programa"], p["anio"]))
            return [{"id": eid}]
        if q == Q.LISTA_PROGRAMAS:
            return [{"codigo": r[0], "nombre": r[1], "facultad": r[2]} for r in sorted(d.programa, key=lambda r: _k(r[0]))
                    if self.vis(r[0], todos)]
        for qq, t in ((Q.LISTA_AREAS, "area"), (Q.LISTA_SEDES, "sede"), (Q.LISTA_FACULTADES, "facultad")):
            if q == qq:
                return self.listar(t, todos)
        if q == Q.PROGRAMA_SEDES_TODAS:
            return [{"programa": a, "sede": b} for a, b in d.programa_sede]
        # --- perfil
        if q == Q.PERFIL:
            e = next((e for e in d.estudiante if e[0] == eid), None)
            if not e:
                return []
            prog = next((x for x in d.programa if x[0] == e[3]), None)
            fac = next((f for f in d.facultad if prog and f[0] == prog[2]), None)
            return [{"id": e[0], "nombre": e[1], "semestre": e[2], "anio_ingreso": e[4] if prog else None,
                     "programa": prog and prog[0], "programa_nombre": prog and prog[1],
                     "facultad": fac and fac[0], "facultad_nombre": fac and fac[1]}]
        if q == Q.PROGRAMA_SEDES:
            return [{"codigo": s, "nombre": self.nom("sede", s)} for pr, s in sorted(d.programa_sede)
                    if pr == p["programa"]]
        if q == Q.PROGRAMA_OBLIGATORIOS:
            return [{"curso": c, "nombre": self.curso(c)[1], "semestre": s}
                    for c, pr, s, ob in sorted(d.curso_programa, key=lambda r: (r[2] or 0, r[0]))
                    if pr == p["programa"] and ob]
        if q == Q.HISTORIAL:
            return [{"curso": c, "nombre": self.curso(c)[1], "tipo": self.curso(c)[2], "nivel": self.curso(c)[3],
                     "periodo": pe, "nota": n, "estado": s}
                    for e, c, pe, n, s in sorted(d.matricula, key=lambda r: (r[2], r[1])) if e == eid]
        if q == Q.INTERESES:
            return [{"area": a, "nombre": self.nom("area", a), "nivel": n}
                    for e, a, n in sorted(d.interes_estudiante, key=lambda r: (-r[2], r[1])) if e == eid]
        if q == Q.INTERESES_BORRAR:
            d.interes_estudiante = [r for r in d.interes_estudiante if r[0] != eid]
            return []
        if q == Q.INTERESES_GUARDAR:
            d.interes_estudiante = [r for r in d.interes_estudiante if not (r[0] == eid and r[1] in {i["area"] for i in p["items"]})]
            d.interes_estudiante += [(eid, i["area"], i["nivel"]) for i in p["items"]]
            return []
        # --- catálogo
        if q == Q.CAT_CURSOS:
            return [{"codigo": c[0], "nombre": c[1], "tipo": c[2], "nivel": c[3], "sintetico": c[0] in self.sint}
                    for c in sorted(d.curso) if self.vis(c[0], todos)]
        if q == Q.CAT_AREAS:
            return [{"curso": c, "area": a, "nombre": self.nom("area", a), "peso": w} for c, a, w in d.curso_area
                    if self.vis(c, todos)]
        if q == Q.CAT_PROGRAMAS:
            return [{"curso": c, "programa": pr, "nombre": self.nom("programa", pr), "semestre": s, "obligatorio": o}
                    for c, pr, s, o in d.curso_programa if self.vis(c, todos)]
        if q == Q.CAT_SEDES:
            return [{"curso": c, "sede": s, "nombre": self.nom("sede", s), "cupos": n} for c, s, pe, n in d.curso_sede
                    if pe == per and self.vis(c, todos)]
        if q == Q.CAT_PRERREQ:
            return [{"curso": c, "requisito": r, "nombre": self.curso(r)[1], "tipo": t} for c, r, t in d.prerrequisito
                    if self.vis(c, todos)]
        if q == Q.CAT_DOCENTES:
            return [{"curso": c, "docente": dd, "nombre": self.nom("docente", dd), "grupo": g}
                    for dd, c, pe, g in d.dictado if pe == per and self.vis(c, todos)]
        if q == Q.OCUPACION:
            n: dict = {}
            for e, c, pe, _, s in d.matricula:
                if s == "EN_CURSO" and pe == per:
                    n[c] = n.get(c, 0) + 1
            return [{"curso": c, "ocupados": v} for c, v in n.items()]
        if q == Q.INSCRIBIR:
            cupos = sum(x[3] for x in d.curso_sede if x[0] == p["curso"] and x[2] == per)
            ocup = sum(1 for m in d.matricula if m[1] == p["curso"] and m[2] == per and m[4] == "EN_CURSO")
            if cupos - ocup <= 0:
                return [{"inscrito": False}]
            d.matricula = [m for m in d.matricula if not (m[0] == eid and m[1] == p["curso"] and m[2] == per)]
            d.matricula.append((eid, p["curso"], per, None, "EN_CURSO"))
            return [{"inscrito": True}]
        if q == Q.RETIRAR:
            antes = len(d.matricula)
            d.matricula = [m for m in d.matricula if not (m[0] == eid and m[1] == p["curso"] and m[2] == per and m[4] == "EN_CURSO")]
            return [{"borradas": antes - len(d.matricula)}]
        # --- recomendaciones
        r = self.ref()
        for qq, fn in ((Q.REC_HISTORIAL, lambda: r.rec_historial(eid)), (Q.REC_OTROS_PROGRAMAS, lambda: r.rec_historial(eid, True)),
                       (Q.REC_INTERESES, lambda: r.rec_intereses(eid)), (Q.REC_SIMILARES, lambda: r.rec_similares(eid))):
            if q == qq:
                return [{**x, "porque": [] if qq != Q.REC_SIMILARES else 1} for x in fn()]
        if q == Q.AREAS_FORTALEZAS:
            n: dict = {}
            for e, c, pe, nota, s in d.matricula:
                if e == eid and s == "APROBADO":
                    for cc, a, _ in d.curso_area:
                        if cc == c:
                            n.setdefault(a, []).append(nota)
            return [{"area": a, "nombre": self.nom("area", a), "cursos": len(v), "promedio": sum(v) / len(v)}
                    for a, v in sorted(n.items(), key=lambda kv: (-len(kv[1]), kv[0]))]
        if q == Q.AREAS_EXPLORAR:
            return [{"area": "A5", "nombre": self.nom("area", "A5"), "cursos_puente": 1, "desde": ["Bases de datos"]}]
        if q == Q.RED_ESTUDIANTE:
            rows = []
            def nodo(lab, key, tabla):
                nm = self.nom(tabla, key)
                return f"{lab}:{key}", lab, ({"id": key, "nombre": nm} if lab == "Estudiante" else {"codigo": key, "nombre": nm})
            ai, al, ap = nodo("Estudiante", eid, "estudiante")
            for e, c, pe, n, s in d.matricula:
                if e == eid:
                    bi, bl, bp = nodo("Curso", c, "curso")
                    rows.append({"rid": f"h{c}{pe}", "tipo": "HA_CURSADO", "rp": {"periodo": pe, "estado": s}, "aid": ai, "al": al,
                                 "ap": ap, "bid": bi, "bl": bl, "bp": bp})
                    for cc, a, w in d.curso_area:
                        if cc == c:
                            xi, xl, xp = nodo("Area", a, "area")
                            rows.append({"rid": f"t{c}{a}", "tipo": "TRATA_DE", "rp": {"peso": w}, "aid": bi, "al": bl, "ap": bp,
                                         "bid": xi, "bl": xl, "bp": xp})
            return rows[: p["limite"]]
        # --- docentes
        if q == Q.DOC_LISTA:
            out = []
            for dd in sorted(d.docente, key=lambda r: _k(r[0])):
                if self.vis(dd[0], todos):
                    out.append({"id": dd[0], "nombre": dd[1], "cursos": [
                        {"curso": c, "nombre": self.curso(c)[1], "periodo": pe, "grupo": g}
                        for x, c, pe, g in d.dictado if x == dd[0]]})
            return out[:300]
        if q == Q.DOC_MAX_ID:
            return [{"maximo": max([int(x[0][1:]) for x in d.docente if x[0][0] == "D" and x[0][1:].isdigit()] or [0])}]
        if q == Q.DOC_EXISTE:
            return [{"id": x[0]} for x in d.docente if x[0] == eid]
        if q == Q.DOC_CREAR:
            d.docente.append((eid, p["nombre"]))
            return [{"id": eid}]
        if q == Q.DOC_ACTUALIZAR:
            d.docente = [(x[0], p["nombre"]) if x[0] == eid else x for x in d.docente]
            return [{"id": eid}]
        if q == Q.DOC_BORRAR:
            d.docente = [x for x in d.docente if x[0] != eid]
            d.dictado = [x for x in d.dictado if x[0] != eid]
            return []
        if q == Q.DOC_ASIGNAR:
            t = (eid, p["curso"], per, p["grupo"])
            if t not in d.dictado:
                d.dictado.append(t)
            return [{"id": eid}]
        if q == Q.DOC_DESASIGNAR:
            d.dictado = [x for x in d.dictado if x != (eid, p["curso"], per, p["grupo"])]
            return []
        # --- cursos
        cod = p.get("codigo")
        if q == Q.CUR_MAX_CODIGO:
            return [{"maximo": max([int(c[0][1:]) for c in d.curso if c[0][0] == "C" and c[0][1:].isdigit()] or [0])}]
        if q == Q.CUR_EXISTE:
            return [{"codigo": c[0]} for c in d.curso if c[0] == cod]
        if q == Q.CUR_CREAR:
            d.curso.append((cod, p["nombre"], p["tipo"], p["nivel"]))
            return []
        if q == Q.CUR_ACTUALIZAR:
            d.curso = [(cod, p["nombre"], p["tipo"], p["nivel"]) if c[0] == cod else c for c in d.curso]
            return []
        if q == Q.CUR_LIMPIAR_AREAS:
            d.curso_area = [x for x in d.curso_area if x[0] != cod]
            return []
        if q == Q.CUR_LIMPIAR_PROGRAMAS:
            d.curso_programa = [x for x in d.curso_programa if x[0] != cod]
            return []
        if q == Q.CUR_LIMPIAR_REQUISITOS:
            d.prerrequisito = [x for x in d.prerrequisito if x[0] != cod]
            return []
        if q == Q.CUR_LIMPIAR_SEDES:
            d.curso_sede = [x for x in d.curso_sede if not (x[0] == cod and x[2] == per)]
            return []
        if q == Q.CUR_LIMPIAR_DOCENTES:
            d.dictado = [x for x in d.dictado if not (x[1] == cod and x[2] == per)]
            return []
        if q == Q.CUR_PONER_AREAS:
            d.curso_area += [(cod, i["id"], i["peso"]) for i in p["items"]]
            return []
        if q == Q.CUR_PONER_PROGRAMAS:
            d.curso_programa += [(cod, i["id"], i["semestre"], i["obligatorio"]) for i in p["items"]]
            return []
        if q == Q.CUR_PONER_REQUISITOS:
            d.prerrequisito += [(cod, i["id"], i["tipo"]) for i in p["items"]]
            return []
        if q == Q.CUR_PONER_SEDES:
            d.curso_sede += [(cod, i["id"], per, i["cupos"]) for i in p["items"]]
            return []
        if q == Q.CUR_PONER_DOCENTES:
            d.dictado += [(i["id"], cod, per, i["grupo"]) for i in p["items"]]
            return []
        if q == Q.CUR_CICLO:
            # ¿hay camino requisito -> ... -> curso siguiendo PRERREQUISITO?
            ady = {}
            for c, r_, t in d.prerrequisito:
                if t == "PRERREQUISITO":
                    ady.setdefault(c, []).append(r_)
            vistos, pila = set(), [p["requisito"]]
            while pila:
                x = pila.pop()
                for y in ady.get(x, []):
                    if y == p["curso"]:
                        return [{"n": 1}]
                    if y not in vistos:
                        vistos.add(y)
                        pila.append(y)
            return [{"n": 0}]
        if q == Q.CUR_USO:
            return [{"matriculas": sum(1 for m in d.matricula if m[1] == cod),
                     "dependientes": len({c for c, r_, _ in d.prerrequisito if r_ == cod})}]
        if q == Q.CUR_BORRAR:
            d.curso = [c for c in d.curso if c[0] != cod]
            for t, i in (("curso_area", 0), ("curso_programa", 0), ("curso_sede", 0), ("matricula", 1), ("dictado", 1)):
                setattr(d, t, [x for x in getattr(d, t) if x[i] != cod])
            d.prerrequisito = [x for x in d.prerrequisito if cod not in (x[0], x[1])]
            return []
        if q in (Q.SIM_BORRAR_UNO, Q.SIM_CONSTRUIR_UNO, Q.SIM_BORRAR_TODAS):
            return []
        if q == Q.SIM_CONSTRUIR_TODAS:
            return [{"pares": len(ds.derivar_similar(d.curso_area)) // 2}]
        # --- catálogos
        for e, tabla in (("Facultad", "facultad"), ("Programa", "programa"), ("Sede", "sede"), ("Area", "area")):
            if q == Q.CATALOGO_EXISTE[e]:
                return [{"codigo": r[0]} for r in getattr(d, tabla) if r[0] == cod]
            if q == Q.CATALOGO_CREAR[e]:
                getattr(d, tabla).append((cod, p["nombre"], None) if e == "Programa" else (cod, p["nombre"]))
                return []
            if q == Q.CATALOGO_ACTUALIZAR[e]:
                setattr(d, tabla, [(cod, p["nombre"], *r[2:]) if r[0] == cod else r for r in getattr(d, tabla)])
                return []
            if q == Q.CATALOGO_USO[e]:
                return [{"usos": self.usos(e, cod)}]
            if q == Q.CATALOGO_BORRAR[e]:
                setattr(d, tabla, [r for r in getattr(d, tabla) if r[0] != cod])
                return []
        if q == Q.PROG_LIMPIAR_FACULTAD:
            d.programa = [(x[0], x[1], None) if x[0] == cod else x for x in d.programa]
            return []
        if q == Q.PROG_PONER_FACULTAD:
            d.programa = [(x[0], x[1], p["facultad"]) if x[0] == cod else x for x in d.programa]
            return []
        if q == Q.PROG_LIMPIAR_SEDES:
            d.programa_sede = [x for x in d.programa_sede if x[0] != cod]
            return []
        if q == Q.PROG_PONER_SEDES:
            d.programa_sede += [(cod, s) for s in p["sedes"]]
            return []
        # --- matrículas
        if q == Q.MATRICULAS:
            out = []
            for e, c, pe, n, s in sorted(d.matricula, key=lambda m: (m[2], m[0]), reverse=True):
                nom = self.nom("estudiante", e)
                if (p["estado"] in ("", s) and p["curso"] in ("", c) and self.vis(e, p["todos"])
                        and (not p["q"] or p["q"].lower() in nom.lower() or p["q"].lower() in e.lower())):
                    out.append({"estudiante": e, "nombre": nom, "curso": c, "curso_nombre": self.curso(c)[1],
                                "periodo": pe, "estado": s, "nota": n})
            return out[:200]
        if q == Q.MATRICULA_PONER_NOTA:
            hit = [m for m in d.matricula if m[0] == p["est"] and m[1] == p["curso"] and m[2] == p["periodo"]]
            if not hit:
                return []
            d.matricula = [(m[0], m[1], m[2], p["nota"], p["estado"]) if m in hit else m for m in d.matricula]
            return [{"estado": p["estado"]}]
        # --- introspección
        if q == Q.NEO_CONSTRAINTS:
            return [{"name": n, "type": "UNIQUENESS", "entityType": "NODE", "labelsOrTypes": [l], "properties": [pp]}
                    for n, l, pp in (("est_id", "Estudiante", "id"), ("cur_cod", "Curso", "codigo"))]
        if q == Q.NEO_INDEXES:
            return [{"name": "est_id", "type": "RANGE", "entityType": "NODE", "labelsOrTypes": ["Estudiante"],
                     "properties": ["id"], "state": "ONLINE"},
                    # Neo4j crea siempre estos dos índices internos y devuelve null en etiquetas y propiedades
                    {"name": "index_343aff4e", "type": "LOOKUP", "entityType": "NODE", "labelsOrTypes": None,
                     "properties": None, "state": "ONLINE"},
                    {"name": "index_f7700477", "type": "LOOKUP", "entityType": "RELATIONSHIP", "labelsOrTypes": None,
                     "properties": None, "state": "ONLINE"}]
        for et, qq in Q.NEO_MUESTRA_NODO.items():
            if q == qq:
                tabla = {"Estudiante": d.estudiante, "Docente": d.docente, "Curso": d.curso, "Programa": d.programa,
                         "Facultad": d.facultad, "Sede": d.sede, "Area": d.area}[et]
                return [{"props": {"id": tabla[0][0], "nombre": tabla[0][1]}}] if tabla else []
        if q.startswith("MATCH (a)-[r:`"):
            return [{"props": {}, "de": "Estudiante", "a": "Curso"}]
        if q == Q.NEO_MATRICULA_REAL:
            m = next((m for m in d.matricula if m[4] == "APROBADO" and m[0] not in self.sint), None)
            return [{"estudiante": m[0], "curso": m[1]}] if m else []
        if q == Q.NEO_EJEMPLO_MATRICULA:
            m = next((m for m in d.matricula if m[0] == p["est"] and m[1] == p["curso"]), None)
            return [{"estudiante": m[0], "curso": m[1], "relacion": {"periodo": m[2], "nota": m[3], "estado": m[4]}}] if m else []
        # --- muestras de comparación
        cuenta: dict = {}
        for m in d.matricula:
            cuenta[m[0]] = cuenta.get(m[0], 0) + 1
        if q in (Q.MUESTRA_EST_BASE, Q.MUESTRA_EST_VOLUMEN):
            vol = q == Q.MUESTRA_EST_VOLUMEN
            c = sorted(((-n, e) for e, n in cuenta.items() if (e in self.sint) == vol))
            return [{"id": c[0][1], "n": -c[0][0]}] if c else []
        if q == Q.MUESTRA_EST_AZAR:
            c = sorted(e[0] for e in d.estudiante if (e[0] in self.sint) == p["sintetico"])
            return [{"id": c[len(c) // 2]}] if c else []
        if q == Q.MUESTRA_CURSO_PROFUNDO:
            best = None
            rf = self.ref()
            for c in sorted(x[0] for x in d.curso if (x[0] in self.sint) == p["sintetico"]):
                prof = max([x["profundidad"] for x in rf.cadena_prerreq(c)] or [0])
                if prof and (best is None or prof > best[0]):
                    best = (prof, c)
            return [{"id": best[1], "prof": best[0]}] if best else []
        # --- extracción para PostgreSQL
        for tabla, qq in Q.EXTRAER.items():
            if q == qq:
                return [dict(zip("abcde", row)) for row in self.extraer(tabla)]
        # --- explorador del grafo
        if q in (Q.GRAFO_GENERAL, Q.GRAFO_VECINDAD):
            filas = []
            for tipo, a, b, rp in self.aristas():
                if tipo not in p["tipos"] or (q == Q.GRAFO_GENERAL and not self.vis(a[1], p["todos"])):
                    continue
                if q == Q.GRAFO_VECINDAD and p["eid"] not in (f"{a[0]}:{a[1]}", f"{b[0]}:{b[1]}"):
                    continue
                def nodo(x):
                    nm = self.nom(x[2], x[1])
                    return (f"{x[0]}:{x[1]}", x[0], {"id": x[1], "nombre": nm} if x[0] == "Estudiante" else {"codigo": x[1], "nombre": nm})
                (ai, al, ap), (bi, bl, bp) = nodo(a), nodo(b)
                filas.append({"rid": f"{tipo}:{a[1]}:{b[1]}:{rp.get('periodo', '')}", "tipo": tipo, "rp": rp, "aid": ai, "al": al, "ap": ap,
                              "bid": bi, "bl": bl, "bp": bp})
            return filas[: p["limite"]]
        if q.strip() == "RETURN 1 AS x":
            return [{"x": 1}]
        # --- escenarios de comparación
        for esc in S.ESCENARIOS:
            if q == esc["cypher"]:
                return self.ref().ejecutar(esc["id"], eid)
        raise AssertionError(f"Consulta no reconocida por el doble de Neo4j:\n{q[:200]}")

    def aristas(self):
        d = self.d
        for e, c, pe, n, st in d.matricula:
            yield "HA_CURSADO", ("Estudiante", e, "estudiante"), ("Curso", c, "curso"), {"periodo": pe, "estado": st}
        for c, a, w in d.curso_area:
            yield "TRATA_DE", ("Curso", c, "curso"), ("Area", a, "area"), {"peso": w}
        for c, r, t in d.prerrequisito:
            yield "REQUIERE", ("Curso", c, "curso"), ("Curso", r, "curso"), {"tipo": t}
        for (a, b), w in ds.derivar_similar(d.curso_area).items():
            yield "SIMILAR_A", ("Curso", a, "curso"), ("Curso", b, "curso"), {"peso": w}

    def usos(self, e, cod):
        d = self.d
        if e == "Facultad":
            return sum(1 for x in d.programa if x[2] == cod)
        if e == "Programa":
            return (sum(1 for x in d.estudiante if x[3] == cod) + sum(1 for x in d.curso_programa if x[1] == cod)
                    + sum(1 for x in d.programa_sede if x[0] == cod) + sum(1 for x in d.programa if x[0] == cod and x[2]))
        if e == "Sede":
            return sum(1 for x in d.curso_sede if x[1] == cod) + sum(1 for x in d.programa_sede if x[1] == cod)
        return sum(1 for x in d.curso_area if x[1] == cod) + sum(1 for x in d.interes_estudiante if x[1] == cod)

    def extraer(self, t):
        d = self.d
        if t == "estudiante":
            return [(e[0], e[1], e[2], e[3], e[4] if e[3] else None) for e in d.estudiante]
        if t == "programa":
            return list(d.programa)
        return list(getattr(d, t))


FAKE: Optional[Fake] = None


def instalar(estado: Optional[Fake] = None) -> Fake:
    """Reemplaza las funciones de Neo4j de `db` y `loaders` por el doble."""
    global FAKE
    FAKE = estado or Fake()
    f = FAKE
    db.neo_read = lambda _q, **p: copy.deepcopy(f.run(_q, p))
    db.neo_write = lambda _q, **p: copy.deepcopy(f.run(_q, p))
    def tx(stm):
        snap = copy.deepcopy(f.d)
        try:
            for q, p in stm:
                f.run(q, p)
        except Exception:
            f.d = snap
            raise
    db.neo_tx = tx
    db.neo_timed = lambda q, p: {"rows": copy.deepcopy(f.run(q, p)), "motor_ms": 0.4, "total_ms": 38.0}
    db.neo_profile = lambda q, p: {"operatorType": "ProduceResults@neo4j", "args": {"Rows": 3, "DbHits": 0},
                                   "children": [{"operatorType": "Expand(All)", "args": {"Rows": 3, "DbHits": 12}, "children": []}]}
    def libre(q, params, limite=200, timeout=10.0):
        if "BOOM" in q:
            raise ValueError("Variable `x` not defined")
        n = {"_tipo": "nodo", "id": "Curso:C101", "etiquetas": ["Curso"], "props": {"codigo": "C101", "nombre": "Bases de Datos I"}}
        m = {"_tipo": "nodo", "id": "Area:A1", "etiquetas": ["Area"], "props": {"codigo": "A1", "nombre": "Bases de datos"}}
        r = {"_tipo": "relacion", "id": "r1", "tipo": "TRATA_DE", "de": "Curso:C101", "a": "Area:A1", "props": {"peso": 1.0}}
        return {"columnas": ["n", "r", "m", "k"], "filas": [[n, r, m, 7]], "truncado": False, "ms": 1.5}
    db.neo_leer_libre = libre
    db.neo_version = lambda: "Neo4j 5.x (fake)"
    # operaciones de carga: se aplican directamente sobre el estado
    def cargar(d, sintetico, progreso=None):
        for t in f.d.tablas():
            getattr(f.d, t).extend(getattr(d, t))
        if sintetico:
            f.marcar(d)
        if progreso:
            progreso(1, 1)
    loaders.neo_preparar_esquema = lambda: None
    loaders.neo_cargar = cargar
    loaders.neo_reconstruir_similares = lambda: None
    def limpiar():
        n = len(f.sint)
        d = f.d
        for t, i in (("facultad", 0), ("sede", 0), ("area", 0), ("docente", 0), ("programa", 0), ("curso", 0), ("estudiante", 0)):
            setattr(d, t, [x for x in getattr(d, t) if x[0] not in f.sint])
        d.programa_sede = [x for x in d.programa_sede if x[0] not in f.sint and x[1] not in f.sint]
        d.curso_programa = [x for x in d.curso_programa if x[0] not in f.sint and x[1] not in f.sint]
        d.curso_area = [x for x in d.curso_area if x[0] not in f.sint and x[1] not in f.sint]
        d.prerrequisito = [x for x in d.prerrequisito if x[0] not in f.sint and x[1] not in f.sint]
        d.curso_sede = [x for x in d.curso_sede if x[0] not in f.sint and x[1] not in f.sint]
        d.dictado = [x for x in d.dictado if x[0] not in f.sint and x[1] not in f.sint]
        d.interes_estudiante = [x for x in d.interes_estudiante if x[0] not in f.sint and x[1] not in f.sint]
        d.matricula = [x for x in d.matricula if x[0] not in f.sint and x[1] not in f.sint]
        f.sint.clear()
        return n
    loaders.neo_limpiar_sinteticos = limpiar
    return f
