"""
Tests del Motor de Reglas Clínicas
====================================

LECCIÓN DE ARQUITECTURA: Estos tests son la prueba de que el diseño es correcto.

Observa que no hay:
- import de FastAPI
- import de SQLAlchemy
- mocks de base de datos
- servidores levantados

Solo Python puro llamando funciones puras.
Eso es lo que significa "testeable por diseño".

Corre con: pytest tests/test_rules_engine.py -v
"""

import pytest
from app.services.rules_engine import (
    Study, PatientPriority,
    calculate_sequence,
    get_preparation_instructions,
    requires_medical_order,
    compare_priority,
)


# ── Tests de calculate_sequence ───────────────────────────────────────────────

class TestCalculateSequence:

    def test_single_study_returns_same(self):
        """Un solo estudio no tiene nada que ordenar."""
        result = calculate_sequence([Study.ELECTROCARDIOGRAMA])
        assert result == [Study.ELECTROCARDIOGRAMA]

    def test_empty_returns_empty(self):
        result = calculate_sequence([])
        assert result == []

    def test_pap_before_transvaginal_ultrasound(self):
        """Regla explícita: PAP siempre antes que ultrasonido transvaginal."""
        # Input en orden incorrecto
        result = calculate_sequence([Study.ULTRASONIDO_TRANSVAG, Study.PAPANICOLAOU])
        assert result.index(Study.PAPANICOLAOU) < result.index(Study.ULTRASONIDO_TRANSVAG)

    def test_pap_before_transvaginal_already_correct(self):
        """Si ya está en el orden correcto, debe mantenerse."""
        result = calculate_sequence([Study.PAPANICOLAOU, Study.ULTRASONIDO_TRANSVAG])
        assert result.index(Study.PAPANICOLAOU) < result.index(Study.ULTRASONIDO_TRANSVAG)

    def test_lab_before_ultrasound(self):
        """Laboratorio con ayuno va antes que ultrasonido."""
        result = calculate_sequence([Study.ULTRASONIDO, Study.LABORATORIO])
        assert result.index(Study.LABORATORIO) < result.index(Study.ULTRASONIDO)

    def test_densitometria_before_tomografia(self):
        """Densitometría antes que tomografía con contraste."""
        result = calculate_sequence([Study.TOMOGRAFIA, Study.DENSITOMETRIA])
        assert result.index(Study.DENSITOMETRIA) < result.index(Study.TOMOGRAFIA)

    def test_no_prep_studies_go_first(self):
        """Estudios sin preparación siempre van primero."""
        result = calculate_sequence([Study.LABORATORIO, Study.ELECTROCARDIOGRAMA])
        assert result.index(Study.ELECTROCARDIOGRAMA) < result.index(Study.LABORATORIO)

    def test_complex_combination_pap_vph_cultivo(self):
        """
        Caso real: Cultivo vaginal + Papanicolaou + VPH
        Regla: PAP primero.
        """
        result = calculate_sequence([Study.VPH, Study.CULTIVO_VAGINAL, Study.PAPANICOLAOU])
        assert result.index(Study.PAPANICOLAOU) < result.index(Study.VPH)
        assert result.index(Study.PAPANICOLAOU) < result.index(Study.CULTIVO_VAGINAL)

    def test_full_visit_complex(self):
        """
        Visita compleja: ECG + Laboratorio + Ultrasonido transvaginal + PAP
        Orden esperado:
        1. ECG (sin preparación → va primero)
        2. PAP (antes que US transvaginal, regla obligatoria)
        3. Laboratorio (con preparación, pero antes que US por regla)
        4. Ultrasonido transvaginal (último por todas las reglas)
        """
        studies = [
            Study.ULTRASONIDO_TRANSVAG,
            Study.LABORATORIO,
            Study.PAPANICOLAOU,
            Study.ELECTROCARDIOGRAMA,
        ]
        result = calculate_sequence(studies)

        # ECG va antes que todo lo que tiene preparación
        assert result.index(Study.ELECTROCARDIOGRAMA) < result.index(Study.LABORATORIO)
        # PAP antes que US transvaginal (regla obligatoria)
        assert result.index(Study.PAPANICOLAOU) < result.index(Study.ULTRASONIDO_TRANSVAG)
        # Lab antes que US (regla obligatoria)
        assert result.index(Study.LABORATORIO) < result.index(Study.ULTRASONIDO_TRANSVAG)

    def test_all_studies_present_in_result(self):
        """El resultado siempre debe tener todos los estudios del input."""
        studies = [Study.LABORATORIO, Study.PAPANICOLAOU, Study.ELECTROCARDIOGRAMA]
        result = calculate_sequence(studies)
        assert set(result) == set(studies)
        assert len(result) == len(studies)


# ── Tests de get_preparation_instructions ────────────────────────────────────

class TestPreparationInstructions:

    def test_electrocardiograma_no_instructions(self):
        """ECG no tiene preparación."""
        assert get_preparation_instructions(Study.ELECTROCARDIOGRAMA) is None

    def test_laboratorio_has_instructions(self):
        result = get_preparation_instructions(Study.LABORATORIO)
        assert result is not None
        assert len(result) > 0

    def test_papanicolaou_has_instructions(self):
        result = get_preparation_instructions(Study.PAPANICOLAOU)
        assert result is not None
        assert "48 horas" in result


# ── Tests de requires_medical_order ──────────────────────────────────────────

class TestMedicalOrderRequirement:

    def test_mastografia_under_35_requires_order(self):
        requires, reason = requires_medical_order(Study.MASTOGRAFIA, patient_age=30)
        assert requires is True
        assert reason is not None

    def test_mastografia_over_35_no_order(self):
        requires, reason = requires_medical_order(Study.MASTOGRAFIA, patient_age=40)
        assert requires is False

    def test_mastografia_recent_less_than_6_months(self):
        requires, reason = requires_medical_order(Study.MASTOGRAFIA, months_since_last=4)
        assert requires is True

    def test_mastografia_more_than_6_months_no_order(self):
        requires, reason = requires_medical_order(Study.MASTOGRAFIA, months_since_last=8)
        assert requires is False

    def test_other_studies_never_require_order(self):
        requires, _ = requires_medical_order(Study.LABORATORIO)
        assert requires is False


# ── Tests de compare_priority ─────────────────────────────────────────────────

class TestPriorityComparison:

    def test_urgent_beats_appointment(self):
        assert compare_priority(PatientPriority.URGENT, PatientPriority.APPOINTMENT) == -1

    def test_urgent_beats_walkin(self):
        assert compare_priority(PatientPriority.URGENT, PatientPriority.WALKIN) == -1

    def test_appointment_beats_walkin(self):
        assert compare_priority(PatientPriority.APPOINTMENT, PatientPriority.WALKIN) == -1

    def test_equal_priority(self):
        assert compare_priority(PatientPriority.WALKIN, PatientPriority.WALKIN) == 0
