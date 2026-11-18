"""Implementación de referencia en Python puro de cada escenario (sin bases de datos).

Sirve para probar que el SQL (y, con un doble de Neo4j, el flujo completo) devuelven lo correcto.
"""
from collections import defaultdict

import dataset as ds


class Ref:
    def __init__(self, d: ds.Dataset, periodo: str):
        self.d, self.periodo = d, periodo
        self.nombre_curso = {c[0]: c[1] for c in d.curso}
        self.nombre_est = {e[0]: e[1] for e in d.estudiante}
        self.prog_est = {e[0]: e[3] for e in d.estudiante}
        self.sim = ds.derivar_similar(d.curso_area)
        self.mat = defaultdict(list)
        for e, c, p, n, s in d.matricula:
            self.mat[e].append((c, p, n, s))
        self.reqs = defaultdict(list)
        for c, q, t in d.prerrequisito:
            if t == "PRERREQUISITO":
                self.reqs[c].append(q)

    def aprobados(self, e):
        return {c for c, _, _, s in self.mat[e] if s == "APROBADO"}

    def _valido(self, e, rec):
        if any(c == rec and s in ("APROBADO", "EN_CURSO") for c, _, _, s in self.mat[e]):
            return False
        ap = self.aprobados(e)
        return all(q in ap for q in self.reqs[rec])

    @staticmethod
    def _top(puntos, n=20):
        return sorted(puntos.items(), key=lambda kv: (-kv[1], kv[0]))[:n]

    def _rows(self, items, extra=None):
        return [{"codigo": k, "nombre": self.nombre_curso.get(k), "puntaje": float(v)} for k, v in items]

    def rec_historial(self, e, otros_programas=False):
        if otros_programas:
            p = self.prog_est.get(e)
            if p is None:
                return []
            en_p = {c for c, pp, _, _ in self.d.curso_programa if pp == p}
        pts = defaultdict(float)
        for base in self.aprobados(e):
            for (a, b), w in self.sim.items():
                if a == base and self._valido(e, b) and (not otros_programas or b not in en_p):
                    pts[b] += w
        return self._rows(self._top(pts))

    def rec_intereses(self, e):
        pts = defaultdict(float)
        for ee, area, nivel in self.d.interes_estudiante:
            if ee != e:
                continue
            for c, a, peso in self.d.curso_area:
                if a == area and self._valido(e, c):
                    pts[c] += nivel * peso
        return self._rows(self._top(pts))

    def rec_similares(self, e):
        mine = self.aprobados(e)
        pts = defaultdict(float)
        for otro in self.mat:
            if otro == e:
                continue
            comp = len(mine & self.aprobados(otro))
            if not comp:
                continue
            for c, _, _, s in self.mat[otro]:
                if s == "APROBADO" and self._valido(e, c):
                    pts[c] += comp
        return self._rows(self._top(pts))

    def inscribibles(self, e):
        if e not in self.nombre_est:
            return []
        ofrecidos = {c for c, _, p, _ in self.d.curso_sede if p == self.periodo}
        return [{"codigo": c, "nombre": self.nombre_curso[c]} for c in sorted(ofrecidos) if self._valido(e, c)]

    def cadena_prerreq(self, c):
        prof, frontera, n = {}, [c], 0
        while frontera and n < 10:
            n += 1
            sig = []
            for x in frontera:
                for q in self.reqs[x]:
                    if q not in prof:
                        prof[q] = n
                    sig.append(q)
            frontera = sig
        return [{"codigo": k, "nombre": self.nombre_curso[k], "profundidad": v}
                for k, v in sorted(prof.items(), key=lambda kv: (kv[1], kv[0]))]

    def companeros_2(self, e):
        cursos_de = defaultdict(set)
        for ee, c, *_ in self.d.matricula:
            cursos_de[ee].add(c)
        est_de = defaultdict(set)
        for ee, cs in cursos_de.items():
            for c in cs:
                est_de[c].add(ee)
        directos = {x for c in cursos_de[e] for x in est_de[c]} - {e}
        pts = defaultdict(float)
        for a in directos:
            for b in {x for c in cursos_de[a] for x in est_de[c]} - {e} - directos:
                pts[b] += 1
        return [{"codigo": k, "nombre": self.nombre_est[k], "puntaje": v} for k, v in self._top(pts)]

    def mas_aprobados(self):
        n = defaultdict(int)
        for _, c, _, _, s in self.d.matricula:
            if s == "APROBADO":
                n[c] += 1
        return [{"codigo": k, "nombre": self.nombre_curso[k], "aprobados": v} for k, v in self._top(n, 10)]

    def ejecutar(self, esc_id, sujeto):
        return {
            "rec_historial": lambda: self.rec_historial(sujeto),
            "rec_intereses": lambda: self.rec_intereses(sujeto),
            "rec_otros_programas": lambda: self.rec_historial(sujeto, True),
            "rec_similares": lambda: self.rec_similares(sujeto),
            "inscribibles": lambda: self.inscribibles(sujeto),
            "cadena_prerreq": lambda: self.cadena_prerreq(sujeto),
            "companeros_2": lambda: self.companeros_2(sujeto),
            "mas_aprobados": lambda: self.mas_aprobados(),
        }[esc_id]()
