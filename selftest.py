"""Autoprueba contra TU base: valida que todo el Cypher del proyecto sea correcto y que Neo4j y PostgreSQL
respondan lo mismo en cada escenario.

    python selftest.py

1) Para CADA consulta de queries.py ejecuta EXPLAIN (revisa sintaxis y esquema sin modificar datos).
2) Ejecuta los 8 escenarios en Neo4j y en PostgreSQL y compara resultados (necesita PostgreSQL sincronizado).
"""
import re
import sys

import config
import db
import queries as Q
import scenarios as S

DUMMY = {"tipos": ["HA_CURSADO"], "eid": "x", "limite": 10, "items": [], "rows": [], "sedes": [], "todos": True, "sintetico": False, "grupo": 1, "cupos": 10,
         "semestre": 1, "nivel": 1, "peso": 1.0, "nota": 3.0, "anio": 2026, "periodo": config.PERIODO_ACTUAL}


def todas_las_consultas():
    for nombre, valor in vars(Q).items():
        if nombre.startswith("_"):
            continue
        if isinstance(valor, str) and re.search(r"\b(MATCH|CREATE|RETURN|SHOW|MERGE)\b", valor):
            yield nombre, valor
        elif isinstance(valor, dict):
            for k, v in valor.items():
                if isinstance(v, str) and re.search(r"\b(MATCH|CREATE|RETURN|SHOW|MERGE)\b", v):
                    yield f"{nombre}[{k}]", v


def main() -> int:
    fallos = 0
    print("== 1) EXPLAIN de todas las consultas ==")
    for nombre, q in todas_las_consultas():
        params = {p: DUMMY.get(p, "x") for p in set(re.findall(r"\$(\w+)", q))}
        try:
            if q.lstrip().upper().startswith("SHOW"):
                db.neo_read(q)
            else:
                db.neo_read("EXPLAIN " + q, **params)
            print(f"  ok   {nombre}")
        except Exception as exc:  # noqa: BLE001
            fallos += 1
            print(f"  FALLA {nombre}: {str(exc).splitlines()[0][:160]}")
    print("\n== 2) Escenarios: Neo4j vs PostgreSQL ==")
    try:
        db.pg_run("SELECT 1")
        pg_ok = db.pg_run("SELECT count(*) AS n FROM curso")[0]["n"] > 0
    except Exception as exc:  # noqa: BLE001
        pg_ok = False
        print("  PostgreSQL no disponible:", getattr(exc, "detail", exc))
    if not pg_ok:
        print("  Sincroniza PostgreSQL desde la interfaz (Comparación > Sincronizar) y repite.")
    for e in S.ESCENARIOS:
        sujeto = {"estudiante": (db.neo_read(Q.MUESTRA_EST_BASE) or [{}])[0].get("id"),
                  "curso": (db.neo_read(Q.MUESTRA_CURSO_PROFUNDO, sintetico=False) or [{}])[0].get("id"), "ninguno": None}[e["sujeto"]]
        p = {"id": sujeto, "periodo": config.PERIODO_ACTUAL}
        try:
            neo = db.neo_read(e["cypher"], **p)
        except Exception as exc:  # noqa: BLE001
            fallos += 1
            print(f"  FALLA {e['id']} (Neo4j): {str(exc).splitlines()[0][:160]}")
            continue
        if not pg_ok:
            print(f"  ok   {e['id']}: Neo4j devolvió {len(neo)} filas")
            continue
        for var in [v for v in ("sql", "sql_mat") if e.get(v)]:
            pg = db.pg_run(e[var], p)
            igual = S.equivalentes(neo[:20], pg[:20], e["cols"])
            fallos += 0 if igual else 1
            print(f"  {'ok  ' if igual else 'DIFIERE'} {e['id']} [{var}] sujeto={sujeto}: Neo4j {len(neo)} filas, PostgreSQL {len(pg)} filas")
    print("\nResultado:", "TODO BIEN" if not fallos else f"{fallos} problema(s)")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
