# SaludCopilot

Motor de orquestación clínica para Salud Digna.  
Genius Arena Hackathon 2026 · Equipo Cachirulitos

---

## Estructura del monorepo

```
saludcopilot/
├── apps/
│   ├── api/          → Backend FastAPI (Dev 1)
│   ├── bot/          → Chatbot WhatsApp + Claude API (Dev 2)
│   ├── dashboard/    → Panel gerencial Next.js (Dev 5)
│   └── cv/           → Visión computacional YOLOv8 (Dev 4)
├── packages/
│   └── rules_engine/ → Motor de reglas clínicas (Dev 1, módulo independiente)
├── ml/               → Modelo predictivo Random Forest (Dev 3)
├── scripts/          → Utilidades de desarrollo
└── docker-compose.yml
```

## Setup en 4 pasos

**1. Requisitos**
- Docker Desktop
- Python 3.12+
- Node.js 20+
- pnpm 8+

**2. Variables de entorno**
```bash
cp .env.example .env
# Edita .env con tus credenciales
```

**3. Levantar servicios base**
```bash
docker compose up
```

**4. Verificar**
- API: http://localhost:8000/health
- Dashboard: http://localhost:3000
- Docs API: http://localhost:8000/docs

## Convenciones de Git

```
feat(bot): implementar modo proactivo con cita
fix(api): corregir orden de regla R-03
docs(readme): agregar instrucciones de setup
```

**Ramas:**
- `main` → siempre funciona, es lo que se presenta al jurado
- `develop` → integración
- `feat/nombre` → tu trabajo

**nunca pushear directo a `main`.**
