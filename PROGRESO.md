# Progreso SaludCopilot

## Estado actual
- **Branch:** `feature/mis-cambios`
- **Ultimo commit:** `feat: implement PASOs 10-25 — API endpoints, WhatsApp bot, CV worker, and ML pipeline`
- **Ultimo paso completado:** PASO 26 (Dashboard: Inicialización y layout) — ya existía
- **Siguiente paso:** PASO 27 (Dashboard: Mock data, MetricCard y AreaTable)
- **CV Worker:** Funcional con cámara real, ventana redimensionable (`QT_QPA_PLATFORM=xcb python main.py`)

---

## Fixes aplicados antes de PASO 9

| Fix | Problema | Solucion |
|-----|----------|----------|
| Docker port conflict | Puerto 5432 ocupado por PostgreSQL local | `docker-compose.yml` → `ports: "5433:5432"` |
| Alembic driver | `psycopg2` no instalado en contenedor | Cambiado a `psycopg` (v3), agregado `psycopg[binary]==3.2.3` en requirements.txt |

---

## Seed data (UUIDs activos en la DB)

```
CLINIC_ID=1db93003-d50e-4f56-80d0-8b994b98eaa8

AREA_LABORATORIO_ID=f68c2295-9053-4304-bbf7-f70dcd917853
AREA_ULTRASONIDO_ID=bc09ede9-6f4d-4314-b681-5da0547ee513
AREA_RAYOS_X_ID=55fae6ed-af60-4f9d-aca6-8e1619df6d86
AREA_ELECTROCARDIOGRAMA_ID=879d301c-ff14-4512-921d-f496e9ec198e
AREA_PAPANICOLAOU_ID=faab0f80-e5d1-4470-9fca-7ee5a6e7d77a
AREA_DENSITOMETRIA_ID=a645f546-2351-4c1d-aae9-f8b8919edd7a
AREA_TOMOGRAFIA_ID=d58be12a-36cd-442e-bce2-bf63aef724bb
```

---

## Como levantar el proyecto

```bash
# 1. Levantar servicios
docker compose up --build

# 2. Correr migraciones
docker exec saludcopilot_api alembic upgrade head

# 3. Verificar API
curl http://localhost:8000/docs

# 4. Si la DB esta vacia, correr seed desde el contenedor
#    (ver seccion Seed data arriba para los UUIDs generados)
```

---

## Prueba rapida de WebSocket (PASO 12)

```bash
# Conectar al WebSocket (con websocat o wscat)
websocat ws://localhost:8000/ws/dashboard/1db93003-d50e-4f56-80d0-8b994b98eaa8

# En otra terminal, disparar un evento de occupancy:
curl -X POST "http://localhost:8000/api/v1/areas/f68c2295-9053-4304-bbf7-f70dcd917853/occupancy" \
  -H "Content-Type: application/json" \
  -d '{"people_count": 5, "timestamp": "2026-04-07T10:00:00Z"}'

# En la terminal del WebSocket debería llegar:
# {"event":"wait_time_updated","data":{"estimated_minutes":30,"people_count":5}}
```

---

## Prueba rapida de endpoints PASO 11

```bash
# Wait time estimate para Laboratorio
curl http://localhost:8000/api/v1/areas/f68c2295-9053-4304-bbf7-f70dcd917853/wait-time-estimate

# Listar areas activas de la clinica
curl "http://localhost:8000/api/v1/areas/?clinic_id=1db93003-d50e-4f56-80d0-8b994b98eaa8"
```

---

## Prueba rapida del endpoint advance-step (PASO 10)

```bash
# Requiere una visita activa con steps. Usar visit_id de un check-in previo:
curl -X POST "http://localhost:8000/api/v1/visits/{VISIT_ID}/advance-step" \
  -H "Content-Type: application/json"

# Respuesta esperada:
# {
#   "visit_id": "...",
#   "visit_status": "pending",
#   "completed_step": {"order": 1, "area_name": "Laboratorio", "status": "completed", "actual_wait_minutes": 0},
#   "next_step": {"order": 2, "area_name": "Ultrasonido", "status": "in_progress", "actual_wait_minutes": null}
# }
```

---

## Prueba rapida del endpoint de occupancy (PASO 9)

```bash
curl -X POST "http://localhost:8000/api/v1/areas/f68c2295-9053-4304-bbf7-f70dcd917853/occupancy" \
  -H "Content-Type: application/json" \
  -d '{"people_count": 5, "timestamp": "2026-04-07T10:00:00Z"}'

# Respuesta esperada: {"wait_time_estimate_minutes":30}
```

---

## Notas

- El puerto de PostgreSQL en el host es **5433** (no 5432) para evitar conflicto con PostgreSQL local
- Los contenedores internamente siguen usando puerto 5432 — el `DATABASE_URL` de la API no cambia
- Los pasos a implementar estan en `PROMPTS_CODING.md`
- La arquitectura y contratos estan en `docs/ARQUITECTURA.md`
