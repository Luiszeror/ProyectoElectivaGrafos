# Recomendador de cursos · Neo4j + PostgreSQL

Proyecto de Bases de Datos con **dos bases**: Neo4j (grafo, la base "viva" del portal) y PostgreSQL (copia relacional
del mismo proyecto, usada para comparar rendimiento y explicar el modelo).

## Qué incluye
- **Estudiante**: iniciar sesión o crear estudiante (sin contraseñas); ver su información, materias perdidas,
  obligatorias pendientes, inscribir/retirar cursos con las reglas de negocio (prerrequisitos, cupos, oferta del periodo,
  repetir lo perdido), intereses, recomendaciones (historial, intereses, otros programas, estudiantes similares),
  áreas fuertes/por explorar y su red en el grafo.
- **Administrador** (4 pestañas):
  1. *Comparación en vivo*: pantalla partida PostgreSQL | Neo4j, 10 preguntas de negocio (de «búsqueda simple» a «recorrido profundo») en Cypher y SQL, medición con
     calentamiento y repeticiones, verificación de que ambos devuelven lo mismo, planes de ejecución
     (PROFILE / EXPLAIN ANALYZE), modo "repetir en vivo", y generador de datos de volumen.
  2. *Profesores y materias*: CRUD de docentes, cursos (áreas, programas, requisitos, sedes/cupos, docentes),
     programas/sedes/áreas/facultades y notas. Sin ciclos de prerrequisitos; un curso necesita al menos un área.
  3. *Explorador del grafo*: vista general del grafo de Neo4j (doble clic expande vecinos, filtro por tipo de relación) y
     panel de Cypher de **solo lectura** (transacción de lectura en el servidor + bloqueo de CREATE/MERGE/DELETE/SET…);
     lo que devuelvas (nodos, relaciones, rutas) se dibuja en el grafo.
  4. *Modelos y estructuras*: pantalla partida con diagrama ER y de grafo, tablas/nodos, relaciones, llaves,
     restricciones e índices **leídos de las bases reales**.

## Puesta en marcha
```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                    # completa NEO4J_URI / NEO4J_PASSWORD (Aura)
docker compose up -d                                    # PostgreSQL 16 en localhost:5432 (o usa el tuyo y ajusta PG_DSN)
uvicorn app:app --reload                                # http://localhost:8000   (API: /docs)
```
1. Tu Aura ya tiene los datos del avance anterior. Si el esquema de IDs difiere, usa una base Aura vacía y
   en la interfaz de administrador pulsa **Sincronizar** después de cargar tus datos, o carga el conjunto base:
   `python -c "import loaders; loaders.neo_preparar_esquema(); import dataset; loaders.neo_cargar(dataset.base(), False); loaders.neo_reconstruir_similares()"`.
2. Entra como administrador → *Comparación en vivo* → **Sincronizar PostgreSQL** (copia Neo4j → PostgreSQL).
3. Repite *Sincronizar* cada vez que cambies datos en Neo4j y quieras compararlos.

## Cómo medir de forma justa
- **motor** = tiempo interno de cada base; **total** incluye la red. Aura está en la nube y PostgreSQL es local, así que el
  *total* de Neo4j incluye latencia de red: para comparar los motores usa *motor*.
- Se descarta una ejecución de calentamiento y se reportan mediana, mínimo y p95 de N repeticiones.
- PostgreSQL tiene índices y ANALYZE, y para recomendaciones se ofrecen dos variantes: SQL calculando la similitud al vuelo
  y SQL con la tabla materializada `curso_similar` (equivalente a las relaciones `SIMILAR_A` precalculadas).
- Con datos base (10 estudiantes) ambos responden en milisegundos y las diferencias son ruido; genera volumen
  (miles de estudiantes) en *Datos y volumen* para ver cómo crece cada uno. Los datos de volumen están marcados
  (`sintetico:true`), no aparecen en el portal y se eliminan con un botón. Respeta el tope de Aura Free.

## Pruebas
```bash
python selftest.py                  # TU Aura: EXPLAIN de las 121 consultas + comparación Neo4j vs PostgreSQL
PG_DSN=postgresql://usuario@host:5432/prueba python -m pytest tests -q    # API completa con Neo4j simulado
```
Las pruebas de `tests/` usan PostgreSQL real y un doble de Neo4j (no ejecuta Cypher); `selftest.py` es la que valida el
Cypher contra tu base real.

## Estructura
`app.py` · `routers/` (auth, student, manage, compare, models) · `queries.py` (todo el Cypher) · `scenarios.py` (Cypher y SQL
equivalentes) · `loaders.py` (DDL de PostgreSQL, sincronización, volumen) · `dataset.py` · `domain.py` (reglas) · `static/` (interfaz; `static/vendor/` trae vis-network 9.1.9, licencia MIT, para no depender de internet).


## Comparación justa (variables de justicia)
PostgreSQL corre en tu equipo y Aura en la nube; sin ajustes PostgreSQL gana solo por no tener red. En la pestaña
de comparación puedes: **igualar la red** (se mide la ida y vuelta a Aura y se le simula a PostgreSQL con una espera
real, que cuenta en el tiempo *total* pero no en el del *motor*), elegir qué tiempo decide (total o motor),
calentar antes de medir, alternar quién se ejecuta primero y usar `curso_similar` precalculada. Si la diferencia es
menor a 1,15× (o ambas tardan menos de 3 ms) se declara «empate técnico».
