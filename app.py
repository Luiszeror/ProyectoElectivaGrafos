"""Sistema de recomendación de cursos: Neo4j (grafo) + PostgreSQL (relacional).

Arranque:  uvicorn app:app --reload
Documentación automática de la API:  http://localhost:8000/docs
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from routers import auth, compare, explore, manage, models, student

app = FastAPI(title="Recomendación de cursos · Neo4j + PostgreSQL", version="2.0")
for r in (auth.router, student.router, manage.router, compare.router, models.router, explore.router):
    app.include_router(r)

STATIC = Path(__file__).parent / "static"


@app.get("/api/salud")
def salud():
    return {"ok": True}


@app.get("/")
def inicio():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
