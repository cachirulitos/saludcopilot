"""
SaludCopilot API — Punto de entrada principal
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import init_db
from app.routers import pacientes, visitas, areas, turnos, notificaciones


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="SaludCopilot API",
    description="Motor de orquestación clínica para Salud Digna",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if True else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(pacientes.router,     prefix="/api/v1/pacientes",     tags=["Pacientes"])
app.include_router(visitas.router,       prefix="/api/v1/visitas",       tags=["Visitas"])
app.include_router(areas.router,         prefix="/api/v1/areas",         tags=["Áreas"])
app.include_router(turnos.router,        prefix="/api/v1/turnos",        tags=["Turnos"])
app.include_router(notificaciones.router,prefix="/api/v1/notificaciones",tags=["Notificaciones"])


@app.get("/health", tags=["Sistema"])
async def health():
    return {"status": "ok", "version": "0.1.0"}
