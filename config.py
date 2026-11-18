"""Configuración leída de variables de entorno (.env)."""
import os

from dotenv import load_dotenv

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER") or os.getenv("NEO4J_USERNAME") or "neo4j"
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE") or None

PG_DSN = os.getenv("PG_DSN", "postgresql://postgres:postgres@localhost:5432/uni")

PERIODO_ACTUAL = os.getenv("PERIODO_ACTUAL", "2026-2")
ADMIN_PIN = os.getenv("ADMIN_PIN", "")

# Límites del plan gratuito de Neo4j Aura (con margen de seguridad)
AURA_MAX_NODOS = 190_000
AURA_MAX_RELS = 380_000
