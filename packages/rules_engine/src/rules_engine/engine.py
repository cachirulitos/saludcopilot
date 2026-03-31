"""
Clinical Rules Engine — SaludCopilot
=====================================
Independent module. Does not import anything from apps/api.
Input: list of requested studies
Output: ordered list with optimal sequence and the reason behind each decision

Rules coded directly from Salud Digna's operational documentation.
Each rule has a traceable code (R-01, R-02...) for auditing.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Study:
    id: str
    study_type: str       # "laboratorio", "ultrasonido", "papanicolaou", etc.
    requires_fasting: bool = False
    is_urgent: bool = False
    has_appointment: bool = False


@dataclass
class SequenceStep:
    order: int
    study: Study
    rule_applied: Optional[str]   # code of the rule that determined this order
    reason: str                   # human-readable description for the patient


@dataclass
class SequenceResult:
    steps: list[SequenceStep]
    estimated_time_minutes: int


MINUTES_PER_STUDY = 15
MINUTES_TRANSFER_BETWEEN_AREAS = 5

# ── Coded rules ─────────────────────────────────────────────────────────
# Each rule evaluates whether it applies and returns the relative order

RULES = [
    {
        "code": "R-01",
        "description": "Papanicolaou antes que Ultrasonido transvaginal",
        "affected_types": {"papanicolaou", "ultrasonido_transvaginal"},
        "first": "papanicolaou",
    },
    {
        "code": "R-02",
        "description": "En combinación VPH + Papanicolaou + Cultivo vaginal, Papanicolaou es primero",
        "affected_types": {"papanicolaou", "vph", "cultivo_vaginal"},
        "first": "papanicolaou",
    },
    {
        "code": "R-03",
        "description": "Densitometría antes que Tomografía o Resonancia con contraste",
        "affected_types": {"densitometria", "tomografia", "resonancia"},
        "first": "densitometria",
    },
    {
        "code": "R-04",
        "description": "Laboratorio con ayuno antes que Ultrasonido si este puede verse afectado",
        "affected_types": {"laboratorio", "ultrasonido"},
        "first": "laboratorio",
        "condition": "requires_fasting",
    },
    {
        "code": "R-05",
        "description": "Estudios sin preparación antes que estudios con preparación",
        "affected_types": None,   # applies to all
        "first": "sin_preparacion",
    },
]

CARE_PRIORITY = {
    "urgent": 0,
    "with_appointment": 1,
    "walk_in": 2,
}


def calculate_sequence(studies: list[Study]) -> SequenceResult:
    """
    Single entry point for the rules engine.
    Receives a patient's studies and returns the optimal sequence.
    """
    if not studies:
        return SequenceResult(steps=[], estimated_time_minutes=0)

    ordered = _apply_rules(studies)
    steps = [
        SequenceStep(
            order=i + 1,
            study=study,
            rule_applied=rule,
            reason=reason,
        )
        for i, (study, rule, reason) in enumerate(ordered)
    ]

    time = len(steps) * MINUTES_PER_STUDY + (len(steps) - 1) * MINUTES_TRANSFER_BETWEEN_AREAS

    return SequenceResult(steps=steps, estimated_time_minutes=time)


def _apply_rules(studies: list[Study]) -> list[tuple[Study, str, str]]:
    """
    Applies rules in priority order and returns
    list of (study, rule_code, human_readable_reason).
    """
    types = {study.study_type for study in studies}

    # Care priority first (R-00: urgent > with appointment > walk-in)
    studies = sorted(studies, key=lambda study: (
        0 if study.is_urgent else (1 if study.has_appointment else 2)
    ))

    result = []
    remaining = list(studies)

    # R-01: Papanicolaou before transvaginal ultrasound
    if {"papanicolaou", "ultrasonido_transvaginal"}.issubset(types):
        remaining = _move_first(remaining, "papanicolaou", result, "R-01",
                                "Papanicolaou debe realizarse antes del ultrasonido transvaginal.")

    # R-02: In VPH + Papanicolaou + Cultivo vaginal combination, Papanicolaou goes first
    if "papanicolaou" in types and types & {"vph", "cultivo_vaginal"}:
        remaining = _move_first(remaining, "papanicolaou", result, "R-02",
                                "En combinación con VPH o cultivo vaginal, Papanicolaou debe realizarse primero.")

    # R-03: Densitometry before CT/MRI
    if "densitometria" in types and types & {"tomografia", "resonancia"}:
        remaining = _move_first(remaining, "densitometria", result, "R-03",
                                "Densitometría debe realizarse antes de la tomografía o resonancia con contraste.")

    # R-04: Fasting lab before ultrasound
    if "laboratorio" in types and "ultrasonido" in types:
        fasting_lab_study = next((study for study in remaining if study.study_type == "laboratorio" and study.requires_fasting), None)
        if fasting_lab_study:
            remaining = _move_first(remaining, "laboratorio", result, "R-04",
                                    "El laboratorio con ayuno debe realizarse antes del ultrasonido.")

    # R-05: No-prep studies before prep-required studies
    without_preparation = [study for study in remaining if not study.requires_fasting]
    with_preparation = [study for study in remaining if study.requires_fasting]
    remaining = without_preparation + with_preparation

    # Add remaining studies without a specific rule
    for study in remaining:
        result.append((study, None, "Orden estándar de atención."))

    return result


def _move_first(
    remaining: list[Study],
    study_type: str,
    result: list,
    rule_code: str,
    reason: str,
) -> list[Study]:
    """Moves the first study of the given type to result and removes it from remaining."""
    target = next((study for study in remaining if study.study_type == study_type), None)
    if target and target not in [result_entry[0] for result_entry in result]:
        result.append((target, rule_code, reason))
        return [study for study in remaining if study is not target]
    return remaining
