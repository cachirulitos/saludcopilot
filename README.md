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
│   ├── api/          -> Backend FastAPI (Dev 1) - TODA la logica de negocio y DB
│   ├── bot/          -> Chatbot WhatsApp + Claude API (Dev 2)
│   ├── dashboard/    -> Panel operativo Next.js (Dev 5)
│   └── cv/           -> Vision computacional YOLOv8 (Dev 4)
├── packages/
│   └── rules_engine/ -> Motor de reglas clinicas (modulo aislado, sin deps externas)
├── ml/               -> Modelo predictivo de tiempos de espera (Dev 3)
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
- PostgreSQL 15 (local o via Docker)

### 1. Clonar y configurar variables de entorno

```bash
git clone <url-del-repo>
cd saludcopilot
cp .env.example .env
# Edita .env con tus credenciales
```

### 2. Base de datos

**Opcion A - PostgreSQL local:**
```bash
# Crear usuario y DB (una sola vez)
sudo -u postgres psql -c "CREATE USER saludcopilot WITH PASSWORD 'saludcopilot_dev';"
sudo -u postgres psql -c "CREATE DATABASE saludcopilot_dev OWNER saludcopilot;"

# Si te da error de autenticacion Ident, edita pg_hba.conf:
# Cambia "ident" por "md5" en las lineas de host
# Luego: sudo systemctl restart postgresql
```

**Opcion B - PostgreSQL via Docker:**
```bash
docker compose up -d postgres
```

### 3. Aplicar migraciones

```bash
cd apps/api
pip install -r requirements.txt
python -m alembic upgrade head
```

Esto crea las 9 tablas: `patients`, `clinics`, `clinical_areas`, `visits`,
`visit_steps`, `notifications`, `clinical_rules`, `wait_time_estimates`, `patient_events`.

### 4. Instalar el motor de reglas

```bash
pip install -e packages/rules_engine
```

Esto permite hacer `from rules_engine.engine import calculate_sequence` desde la API
sin hacks de `sys.path`.

### 5. Levantar servicios

```bash
# Todo junto (PostgreSQL + Redis + API)
docker compose up

# O solo la API local (si ya tienes PostgreSQL y Redis corriendo)
cd apps/api
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 6. Verificar que funciona

- API health: http://localhost:8000/health
- API docs (Swagger): http://localhost:8000/docs
- Dashboard: http://localhost:3000

---

## Endpoints de la API (prefijos actuales)

| Prefijo | Modulo | Estado |
|---|---|---|
| `/api/v1/patients` | Pacientes | Stub |
| `/api/v1/visits` | Visitas | Stub |
| `/api/v1/areas` | Areas clinicas | Stub |
| `/api/v1/visit-steps` | Pasos de visita | Stub |
| `/api/v1/notifications` | Notificaciones | Stub |
| `/health` | Health check | Funcional |

Los endpoints estan en stub (devuelven `"not implemented"`). Se implementan
segun cada TASK_*.md en su modulo correspondiente.

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

**Correr tests:**
```bash
pytest packages/rules_engine/tests/ -v
# 14 tests, todos pasan
```

---

## Documentacion importante

| Archivo | Que tiene |
|---|---|
| `docs/ARQUITECTURA.md` | Contratos entre modulos, schema de DB, flujos de datos |
| `docs/ADVERTENCIAS.md` | Problemas de arquitectura a resolver ANTES de programar |
| `apps/*/TASK_*.md` | Tareas especificas de cada modulo |

**Lee ARQUITECTURA.md antes de tocar cualquier codigo.** Ahi estan los contratos
de API entre modulos. Si cambias un contrato, afectas a otro dev.

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
- `feat/nombre` - tu trabajo

---

## Variables de entorno

Todas documentadas en `.env.example`. Las criticas:

| Variable | Para que |
|---|---|
| `DATABASE_URL` | Conexion a PostgreSQL (asyncpg) |
| `REDIS_URL` | Conexion a Redis |
| `SECRET_KEY` | JWT y seguridad |
| `WHATSAPP_TOKEN` | Token de WhatsApp Cloud API |
| `ANTHROPIC_API_KEY` | API key de Claude |
