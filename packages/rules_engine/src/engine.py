"""
Motor de Reglas Clínicas — SaludCopilot
========================================
Módulo independiente. No importa nada de apps/api.
Entrada: lista de estudios solicitados
Salida: lista ordenada con el orden óptimo y la razón de cada decisión

Reglas codificadas directamente de la documentación operativa de Salud Digna.
Cada regla tiene un código trazable (R-01, R-02...) para auditoría.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Estudio:
    id: str
    tipo: str          # "laboratorio", "ultrasonido", "papanicolaou", etc.
    requiere_ayuno: bool = False
    es_urgente: bool = False
    tiene_cita: bool = False


@dataclass
class PasoSecuencia:
    orden: int
    estudio: Estudio
    regla_aplicada: Optional[str]   # código de la regla que determinó este orden
    razon: str                      # descripción legible para el paciente


@dataclass
class ResultadoSecuencia:
    pasos: list[PasoSecuencia]
    tiempo_estimado_minutos: int


# ── Reglas codificadas ────────────────────────────────────────────────────
# Cada regla es una función que evalúa si aplica y devuelve el orden relativo

REGLAS = [
    {
        "codigo": "R-01",
        "descripcion": "Papanicolaou antes que Ultrasonido transvaginal",
        "tipos_afectados": {"papanicolaou", "ultrasonido_transvaginal"},
        "primero": "papanicolaou",
    },
    {
        "codigo": "R-02",
        "descripcion": "En combinación VPH + Papanicolaou + Cultivo vaginal, Papanicolaou es primero",
        "tipos_afectados": {"papanicolaou", "vph", "cultivo_vaginal"},
        "primero": "papanicolaou",
    },
    {
        "codigo": "R-03",
        "descripcion": "Densitometría antes que Tomografía o Resonancia con contraste",
        "tipos_afectados": {"densitometria", "tomografia", "resonancia"},
        "primero": "densitometria",
    },
    {
        "codigo": "R-04",
        "descripcion": "Laboratorio con ayuno antes que Ultrasonido si este puede verse afectado",
        "tipos_afectados": {"laboratorio", "ultrasonido"},
        "primero": "laboratorio",
        "condicion": "requiere_ayuno",
    },
    {
        "codigo": "R-05",
        "descripcion": "Estudios sin preparación antes que estudios con preparación",
        "tipos_afectados": None,   # aplica a todos
        "primero": "sin_preparacion",
    },
]

PRIORIDAD_ATENCION = {
    "urgente": 0,
    "con_cita": 1,
    "sin_cita": 2,
}


def calcular_secuencia(estudios: list[Estudio]) -> ResultadoSecuencia:
    """
    Punto de entrada único del motor de reglas.
    Recibe los estudios de un paciente y devuelve la secuencia óptima.
    """
    if not estudios:
        return ResultadoSecuencia(pasos=[], tiempo_estimado_minutos=0)

    ordenados = _aplicar_reglas(estudios)
    pasos = [
        PasoSecuencia(
            orden=i + 1,
            estudio=estudio,
            regla_aplicada=regla,
            razon=razon,
        )
        for i, (estudio, regla, razon) in enumerate(ordenados)
    ]

    # Tiempo estimado simplificado: 15 min por estudio + 5 min de traslado entre áreas
    tiempo = len(pasos) * 15 + (len(pasos) - 1) * 5

    return ResultadoSecuencia(pasos=pasos, tiempo_estimado_minutos=tiempo)


def _aplicar_reglas(estudios: list[Estudio]) -> list[tuple[Estudio, str, str]]:
    """
    Aplica las reglas en orden de prioridad y devuelve
    lista de (estudio, codigo_regla, razon_legible).
    """
    tipos = {e.tipo for e in estudios}

    # Prioridad de atención primero (R-00: urgentes > con cita > sin cita)
    estudios = sorted(estudios, key=lambda e: (
        0 if e.es_urgente else (1 if e.tiene_cita else 2)
    ))

    resultado = []
    restantes = list(estudios)

    # R-01: Papanicolaou antes que Ultrasonido transvaginal
    if {"papanicolaou", "ultrasonido_transvaginal"}.issubset(tipos):
        restantes = _mover_primero(restantes, "papanicolaou", resultado, "R-01",
                                   "Papanicolaou debe realizarse antes del ultrasonido transvaginal.")

    # R-03: Densitometría antes que Tomografía/Resonancia
    if "densitometria" in tipos and tipos & {"tomografia", "resonancia"}:
        restantes = _mover_primero(restantes, "densitometria", resultado, "R-03",
                                   "Densitometría debe realizarse antes de la tomografía o resonancia con contraste.")

    # R-04: Laboratorio con ayuno antes que Ultrasonido
    if "laboratorio" in tipos and "ultrasonido" in tipos:
        lab = next((e for e in restantes if e.tipo == "laboratorio" and e.requiere_ayuno), None)
        if lab:
            restantes = _mover_primero(restantes, "laboratorio", resultado, "R-04",
                                       "El laboratorio con ayuno debe realizarse antes del ultrasonido.")

    # R-05: Sin preparación antes que con preparación
    sin_prep = [e for e in restantes if not e.requiere_ayuno]
    con_prep = [e for e in restantes if e.requiere_ayuno]
    restantes = sin_prep + con_prep

    # Agregar los restantes sin regla específica
    for estudio in restantes:
        resultado.append((estudio, None, "Orden estándar de atención."))

    return resultado


def _mover_primero(
    restantes: list[Estudio],
    tipo: str,
    resultado: list,
    codigo_regla: str,
    razon: str,
) -> list[Estudio]:
    """Mueve el primer estudio del tipo dado al resultado y lo quita de restantes."""
    objetivo = next((e for e in restantes if e.tipo == tipo), None)
    if objetivo and objetivo not in [r[0] for r in resultado]:
        resultado.append((objetivo, codigo_regla, razon))
        return [e for e in restantes if e is not objetivo]
    return restantes
