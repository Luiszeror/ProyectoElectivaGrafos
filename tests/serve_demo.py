"""Levanta la app con PostgreSQL real y Neo4j simulado (para ver la interfaz sin Aura).
Uso: PG_DSN=... python tests/serve_demo.py 8765"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import fake_neo
import uvicorn

fake_neo.instalar()
import app  # noqa: E402

if __name__ == "__main__":
    uvicorn.run(app.app, host="127.0.0.1", port=int(sys.argv[1]) if len(sys.argv) > 1 else 8765, log_level="warning")
