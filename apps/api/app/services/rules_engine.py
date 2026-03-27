"""
Motor de Reglas Clínicas — SaludCopilot
========================================

Este es el archivo más importante del sistema.
Contiene el conocimiento exclusivo de Salud Digna:
el orden correcto entre estudios y las prioridades de atención.

PRINCIPIO DE DISEÑO: Funciones puras.
Una función pura:
- Dado el mismo input, siempre devuelve el mismo output.
- No tiene efectos secundarios (no escribe en DB, no llama APIs).
- Es 100% testeable sin mocks ni infraestructura.

Si alguna vez sientes la necesidad de hacer una de estas funciones
async o de que lea de la base de datos, algo está mal en el diseño.
Las reglas son conocimiento, no datos en tiempo real.
"""

from enum import Enum
from dataclasses import dataclass


# ── Tipos de Estudio ──────────────────────────────────────────────────────────

class Study(str, Enum):
    """
    Catálogo de estudios disponibles en Salud Digna.
    Usar enums en lugar de strings libres previene errores de tipeo
    que son imposibles de detectar en tiempo de ejecución.
    """
    LABORATORIO          = "laboratorio"
    ULTRASONIDO          = "ultrasonido"
    ULTRASONIDO_TRANSVAG = "ultrasonido_transvaginal"
    PAPANICOLAOU         = "papanicolaou"
    VPH                  = "vph"
    CULTIVO_VAGINAL      = "cultivo_vaginal"
    MASTOGRAFIA          = "mastografia"
    TOMOGRAFIA           = "tomografia"
    RESONANCIA           = "resonancia"
    DENSITOMETRIA        = "densitometria"
    ELECTROCARDIOGRAMA   = "electrocardiograma"
    NUTRICION            = "nutricion"
    OPTICA               = "optica"


class PatientPriority(str, Enum):
    """
    Prioridades de atención definidas por Salud Digna.
    El orden importa: URGENT > APPOINTMENT > WALKIN
    """
    URGENT      = "urgent"       # Sangrado, necesidad inmediata
    APPOINTMENT = "appointment"  # Paciente con cita previa
    WALKIN      = "walkin"       # Paciente sin cita


# ── Reglas de Preparación ─────────────────────────────────────────────────────

# Estudios que requieren preparación (ayuno, etc.)
# Fuente: Reglas de negocio Salud Digna — documento oficial del hackathon
STUDIES_REQUIRING_PREPARATION: set[Study] = {
    Study.LABORATORIO,          # algunos análisis requieren ayuno
    Study.ULTRASONIDO,          # puede requerir vejiga llena o ayuno
    Study.ULTRASONIDO_TRANSVAG, # requiere vejiga llena, puede interactuar con ayuno
    Study.TOMOGRAFIA,           # contraste puede requerir ayuno
    Study.RESONANCIA,           # contraste puede requerir ayuno
}

# Estudios sin ninguna restricción de preparación
STUDIES_NO_PREPARATION: set[Study] = {
    Study.ELECTROCARDIOGRAMA,
    Study.NUTRICION,
    Study.OPTICA,
    Study.MASTOGRAFIA,
}


# ── Reglas de Orden Obligatorio ───────────────────────────────────────────────

# Formato: (estudio_que_va_primero, estudio_que_va_despues)
# Si ambos estudios están presentes, el primero SIEMPRE precede al segundo.
#
# Fuente: Reglas de negocio Salud Digna — documento oficial del hackathon
MANDATORY_ORDER_RULES: list[tuple[Study, Study]] = [
    # PAP siempre antes que ultrasonido transvaginal
    (Study.PAPANICOLAOU, Study.ULTRASONIDO_TRANSVAG),
    # En combinación Cultivo + PAP + VPH: PAP primero
    (Study.PAPANICOLAOU, Study.VPH),
    (Study.PAPANICOLAOU, Study.CULTIVO_VAGINAL),
    # Densitometría antes que Tomografía/Resonancia con contraste
    (Study.DENSITOMETRIA, Study.TOMOGRAFIA),
    (Study.DENSITOMETRIA, Study.RESONANCIA),
    # Laboratorio con ayuno antes que cualquier tipo de ultrasonido
    (Study.LABORATORIO, Study.ULTRASONIDO),
    (Study.LABORATORIO, Study.ULTRASONIDO_TRANSVAG),
]


# ── Función Principal ─────────────────────────────────────────────────────────

def calculate_sequence(studies: list[Study]) -> list[Study]:
    """
    Calcula la secuencia óptima de estudios para un paciente.

    El algoritmo aplica tres capas de lógica en orden:
    1. Estudios sin preparación van primero (regla general).
    2. Reglas de orden obligatorio entre estudios específicos.
    3. Estabilidad: los estudios sin restricción mantienen su orden original.

    Args:
        studies: Lista de estudios que el paciente tiene agendados.
                 El orden de entrada no importa — este es el punto.

    Returns:
        Lista ordenada según las reglas clínicas de Salud Digna.

    Examples:
        >>> calculate_sequence([Study.ULTRASONIDO, Study.LABORATORIO])
        [Study.LABORATORIO, Study.ULTRASONIDO]

        >>> calculate_sequence([Study.ULTRASONIDO_TRANSVAG, Study.PAPANICOLAOU])
        [Study.PAPANICOLAOU, Study.ULTRASONIDO_TRANSVAG]

        >>> calculate_sequence([Study.ELECTROCARDIOGRAMA])
        [Study.ELECTROCARDIOGRAMA]
    """
    if not studies:
        return []

    if len(studies) == 1:
        return list(studies)

    # Paso 1: Separar estudios sin preparación (van primero siempre)
    no_prep = [s for s in studies if s in STUDIES_NO_PREPARATION]
    with_prep = [s for s in studies if s not in STUDIES_NO_PREPARATION]
    other = [s for s in studies if s not in STUDIES_NO_PREPARATION and s not in STUDIES_REQUIRING_PREPARATION]

    # Combinar: sin preparación → con preparación → el resto
    working_order = no_prep + other + with_prep

    # Eliminar duplicados manteniendo el orden (por si acaso)
    seen = set()
    working_order_dedup = []
    for s in working_order:
        if s not in seen:
            seen.add(s)
            working_order_dedup.append(s)

    # Paso 2: Aplicar reglas de orden obligatorio
    # Usamos bubble sort conceptual: si (A, B) es regla y B está antes que A, los intercambiamos
    study_set = set(studies)
    result = working_order_dedup.copy()

    # Iteramos hasta que no haya más intercambios necesarios (máximo n² pasadas)
    changed = True
    while changed:
        changed = False
        for (first, second) in MANDATORY_ORDER_RULES:
            if first not in study_set or second not in study_set:
                continue  # La regla no aplica si alguno de los estudios no está presente
            if first in result and second in result:
                idx_first = result.index(first)
                idx_second = result.index(second)
                if idx_first > idx_second:
                    # Violación de la regla: intercambiar
                    result[idx_first], result[idx_second] = result[idx_second], result[idx_first]
                    changed = True

    return result


def get_preparation_instructions(study: Study) -> str | None:
    """
    Devuelve las instrucciones de preparación para un estudio, si las hay.
    Retorna None si el estudio no requiere preparación.

    Estas instrucciones se envían al paciente vía WhatsApp ANTES de su visita.
    """
    instructions = {
        Study.LABORATORIO: (
            "Para su estudio de laboratorio: si incluye glucosa, colesterol u otros "
            "análisis metabólicos, requiere ayuno de 8-12 horas. Solo puede tomar agua."
        ),
        Study.ULTRASONIDO: (
            "Para su ultrasonido abdominal: requiere ayuno de 4 horas previas. "
            "Para ultrasonido pélvico: beba 1 litro de agua 1 hora antes y NO orine."
        ),
        Study.PAPANICOLAOU: (
            "Para su Papanicolaou: evite relaciones sexuales 48 horas antes, "
            "no use medicamentos vaginales ni duchas vaginales 48 horas previas. "
            "No realice el estudio durante su período menstrual."
        ),
        Study.MASTOGRAFIA: (
            "Para su mastografía: use ropa en dos piezas. No use desodorante, "
            "talco ni cremas en la zona axilar o del pecho el día del estudio."
        ),
        Study.TOMOGRAFIA: (
            "Para su tomografía: si es con contraste, requiere ayuno de 4 horas. "
            "Informe si tiene alergia al yodo o a medios de contraste."
        ),
        Study.RESONANCIA: (
            "Para su resonancia magnética: retire cualquier objeto metálico "
            "(aretes, piercing, cinturón). Informe si tiene implantes metálicos o marcapasos."
        ),
    }
    return instructions.get(study)


def requires_medical_order(study: Study, patient_age: int | None = None,
                            months_since_last: int | None = None) -> tuple[bool, str | None]:
    """
    Determina si un estudio requiere orden médica previa.

    Returns:
        (requires_order, reason): tupla de (booleano, mensaje explicativo si aplica)
    """
    if study == Study.MASTOGRAFIA:
        if patient_age is not None and patient_age < 35:
            return True, "Pacientes menores de 35 años requieren orden médica de especialista para mastografía."
        if months_since_last is not None and months_since_last < 6:
            return True, "Se requiere orden médica si la última mastografía fue hace menos de 6 meses."

    return False, None


# ── Función de Prioridad en Cola ──────────────────────────────────────────────

def compare_priority(p1: PatientPriority, p2: PatientPriority) -> int:
    """
    Compara dos prioridades de paciente.
    Returns: -1 si p1 > p2 (p1 va primero), 0 si igual, 1 si p1 < p2.
    """
    order = {
        PatientPriority.URGENT: 0,
        PatientPriority.APPOINTMENT: 1,
        PatientPriority.WALKIN: 2,
    }
    if order[p1] < order[p2]:
        return -1
    if order[p1] > order[p2]:
        return 1
    return 0
