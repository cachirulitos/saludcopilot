# SaludCopilot

Motor de orquestacion clinica para Salud Digna.
Genius Arena Hackathon 2026 - Equipo Cachirulitos

---

## Que es esto

Sistema que guia a pacientes de Salud Digna durante su visita via WhatsApp.
Calcula el orden optimo de estudios medicos, predice tiempos de espera con
vision computacional + ML, y da un dashboard en tiempo real al staff operativo.

---

## Estructura del monorepo

```
saludcopilot/
├── apps/
│   ├── api/          -> Backend FastAPI - logica de negocio, DB, WebSocket
│   ├── bot/          -> Chatbot WhatsApp + Gemini LLM
│   ├── dashboard/    -> Panel operativo Next.js
│   └── cv/           -> Vision computacional YOLOv8 (conteo de personas)
├── packages/
│   └── rules_engine/ -> Motor de reglas clinicas (modulo aislado, sin deps externas)
├── ml/               -> Modelo predictivo de tiempos de espera (RandomForest)
├── scripts/          -> Utilidades de desarrollo
└── docker-compose.yml
```

**Regla clave:** solo la API escribe a PostgreSQL. Ningun otro modulo toca la DB directamente.

---

## Setup local paso a paso

### Requisitos

- Docker Desktop
- Python 3.12+
- Node.js 20+
- pnpm 8+

### 1. Clonar y configurar variables de entorno

```bash
git clone <url-del-repo>
cd saludcopilot
cp .env.example .env
```

Edita `.env` con tus credenciales (ver seccion "Variables de entorno" abajo).

### 2. Levantar servicios (API + DB + Redis)

```bash
docker compose up --build
```

Esto levanta PostgreSQL, Redis y la API en http://localhost:8000.

### 3. Aplicar migraciones (primera vez)

```bash
docker exec saludcopilot_api alembic upgrade head
```

Esto crea las 9 tablas: `patients`, `clinics`, `clinical_areas`, `visits`,
`visit_steps`, `notifications`, `clinical_rules`, `wait_time_estimates`, `patient_events`.

### 4. Instalar el motor de reglas

```bash
pip install -e packages/rules_engine
```

### 5. Verificar que funciona

- API health: http://localhost:8000/health
- API docs (Swagger): http://localhost:8000/docs
- Dashboard: http://localhost:3000

---

## CV Worker (Vision Computacional)

El CV Worker usa YOLOv8 para detectar personas en una camara y publica el conteo
a la API, que calcula tiempos de espera y actualiza el dashboard en tiempo real.

### Setup del CV Worker

```bash
cd apps/cv

# Crear entorno virtual
python -m venv .venv
source .venv/bin/activate   # Linux/Mac
# .venv\Scripts\activate    # Windows

# Instalar dependencias
pip install -r requirements.txt
```

### Configurar .env del CV Worker

Crea `apps/cv/.env`:

```env
API_BASE_URL=http://localhost:8000
INTERNAL_CV_TOKEN=saludcopilot-internal-token-change-in-prod
CAMERA_INDEX=0
CAPTURE_INTERVAL_SECONDS=5
YOLO_MODEL_NAME=yolov8n.pt
CONFIDENCE_THRESHOLD=0.4
CAMERA_TO_AREA_MAPPING={"0":"f68c2295-9053-4304-bbf7-f70dcd917853"}
```

- `CAMERA_INDEX`: indice de la camara (0 = webcam principal)
- `CAMERA_TO_AREA_MAPPING`: JSON que mapea indice de camara al UUID del area clinica
- Los UUIDs de areas los encuentras en la seccion "Seed data" de PROGRESO.md

### Ejecutar el CV Worker

**IMPORTANTE:** Docker compose debe estar corriendo primero (`docker compose up`).

```bash
cd apps/cv
source .venv/bin/activate

# Con ventana de preview (Linux con Wayland/GNOME):
QT_QPA_PLATFORM=xcb python main.py

# Sin ventana (headless / servidores):
python main.py --no-window

# Modo demo (sin camara fisica, datos simulados):
python main.py --demo
```

La ventana de preview es redimensionable. Presiona `q` para salir.

**Output esperado:**
```
SaludCopilot CV Worker iniciado. Modo: CAMARA REAL
Area f68c2295-...: 1 personas | Espera est: 18 min
Area f68c2295-...: 2 personas | Espera est: 18 min
```

---

## Bot WhatsApp

### Setup del Bot

```bash
cd apps/bot

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Configurar .env del Bot

Crea `apps/bot/.env` (o usa el `.env` raiz):

```env
WHATSAPP_TOKEN=<tu-token-de-meta-cloud-api>
WHATSAPP_PHONE_ID=<tu-phone-id-de-meta>
WHATSAPP_VERIFY_TOKEN=saludcopilot_verify
LLM_API_KEY=<tu-api-key-de-google-gemini>
REDIS_URL=redis://localhost:6379/0
API_BASE_URL=http://localhost:8000
INTERNAL_BOT_TOKEN=saludcopilot-internal-token-change-in-prod
```

- `LLM_API_KEY`: API key de Google Gemini (gratis en https://aistudio.google.com/apikey)
- `WHATSAPP_TOKEN` y `WHATSAPP_PHONE_ID`: se obtienen desde Meta for Developers

### Ejecutar el Bot

```bash
cd apps/bot
source .venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

---

## ML Pipeline (Modelo Predictivo)

### Setup del ML

```bash
cd ml

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Datos necesarios

Coloca estos CSVs en `ml/data/`:

| Archivo | Contenido |
|---|---|
| `ventas.csv` | Historial de servicios (FechaServicio, TipoEstudio, ClinicaId, etc.) |
| `promedios_espera.csv` | Promedios historicos de espera por area |
| `consultorios.csv` | Capacidad simultanea por area/clinica |

### Entrenar el modelo

```bash
cd ml/src
python train.py
```

Genera artefactos en `ml/artifacts/`: `model.pkl` y `encodings.pkl`.

---

## Dashboard (Next.js)

```bash
cd apps/dashboard
pnpm install
pnpm dev
```

Abre http://localhost:3000

---

## Endpoints de la API

| Prefijo | Modulo | Estado |
|---|---|---|
| `/api/v1/patients` | Pacientes | Stub |
| `/api/v1/visits/check-in` | Check-in con secuencia optima | Funcional |
| `/api/v1/visits/{id}/context` | Contexto de visita para bot | Funcional |
| `/api/v1/visits/{id}/advance-step` | Avanzar paso de visita | Funcional |
| `/api/v1/areas/{id}/occupancy` | Actualizar ocupacion (CV) | Funcional |
| `/api/v1/areas/{id}/wait-time-estimate` | Estimacion de espera | Funcional |
| `/api/v1/areas/?clinic_id=` | Listar areas de clinica | Funcional |
| `/ws/dashboard/{clinic_id}` | WebSocket tiempo real | Funcional |
| `/health` | Health check | Funcional |

---

## Motor de reglas (packages/rules_engine)

Modulo aislado que calcula el orden optimo de estudios. No importa nada de la API.

**Reglas implementadas:**
- R-00: Urgentes primero, luego con cita, luego sin cita
- R-01: Papanicolaou antes que ultrasonido transvaginal
- R-02: En combinacion VPH + Pap + cultivo vaginal, Pap primero
- R-03: Densitometria antes que tomografia o resonancia
- R-04: Laboratorio con ayuno antes que ultrasonido
- R-05: Estudios sin preparacion antes que con preparacion

```bash
pytest packages/rules_engine/tests/ -v
# 14 tests, todos pasan
```

---

## Variables de entorno

Todas van en `.env` en la raiz del proyecto (o en `.env` dentro de cada app).
**NUNCA commitear el archivo .env** — esta en `.gitignore`.

| Variable | Para que | Donde obtenerla |
|---|---|---|
| `DATABASE_URL` | Conexion a PostgreSQL | Ya configurada en docker-compose |
| `REDIS_URL` | Conexion a Redis | Ya configurada en docker-compose |
| `SECRET_KEY` | JWT y seguridad | `openssl rand -hex 32` |
| `LLM_API_KEY` | API key de Google Gemini | https://aistudio.google.com/apikey (gratis) |
| `WHATSAPP_TOKEN` | Token de WhatsApp Cloud API | Meta for Developers |
| `WHATSAPP_PHONE_ID` | Phone ID de WhatsApp | Meta for Developers |
| `CAMERA_TO_AREA_MAPPING` | Mapeo camara -> area | JSON: `{"0":"<UUID-del-area>"}` |

---

## Seed data (UUIDs en la DB)

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

## Pruebas rapidas

### Probar el endpoint de occupancy (CV -> API)

```bash
curl -X POST "http://localhost:8000/api/v1/areas/f68c2295-9053-4304-bbf7-f70dcd917853/occupancy" \
  -H "Content-Type: application/json" \
  -d '{"people_count": 5, "timestamp": "2026-04-07T10:00:00Z"}'
# Respuesta: {"wait_time_estimate_minutes":30}
```

### Probar WebSocket del dashboard

```bash
# Terminal 1 — conectar
websocat ws://localhost:8000/ws/dashboard/1db93003-d50e-4f56-80d0-8b994b98eaa8

# Terminal 2 — disparar evento
curl -X POST "http://localhost:8000/api/v1/areas/f68c2295-9053-4304-bbf7-f70dcd917853/occupancy" \
  -H "Content-Type: application/json" \
  -d '{"people_count": 5, "timestamp": "2026-04-07T10:00:00Z"}'
# En terminal 1 llega: {"event":"wait_time_updated","data":{...}}
```

### Probar wait time estimate

```bash
curl http://localhost:8000/api/v1/areas/f68c2295-9053-4304-bbf7-f70dcd917853/wait-time-estimate
```

---

## Documentacion

| Archivo | Que tiene |
|---|---|
| `docs/ARQUITECTURA.md` | Contratos entre modulos, schema de DB, flujos de datos |
| `docs/ADVERTENCIAS.md` | Problemas de arquitectura a resolver |
| `apps/*/TASK_*.md` | Tareas especificas de cada modulo |
| `PROGRESO.md` | Estado actual del desarrollo paso a paso |
| `PROMPTS_CODING.md` | Pasos de implementacion detallados |

**Lee ARQUITECTURA.md antes de tocar cualquier codigo.**

---

## Convenciones

- **Todo en ingles:** variables, funciones, clases, archivos, endpoints
- **Nombres explicitos:** `calculate_study_sequence` no `calc_seq`
- **SQLAlchemy 2.0:** `Mapped` + `mapped_column`, nunca `Column` legacy
- **Sin magic numbers:** toda constante tiene nombre en UPPER_SNAKE_CASE

### Commits

```
feat(api): add check-in endpoint with rules engine integration
fix(bot): handle duplicate webhook messages with Redis lock
docs(readme): update setup instructions
```

### Ramas

- `main` - siempre funciona, es lo que se presenta al jurado
- `feature/*` - tu trabajo
