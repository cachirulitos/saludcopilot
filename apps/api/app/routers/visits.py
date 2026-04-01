"""
POST /api/v1/visits/check-in
GET  /api/v1/visits/{visit_id}/context
POST /api/v1/visits/{visit_id}/advance-step
"""

import uuid
import sys
from datetime import datetime, timezone
from pathlib import Path

import redis.asyncio as redis
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.models import (
    ClinicalArea,
    Patient,
    PatientEvent,
    Visit,
    VisitStatus,
    VisitStep,
    VisitStepStatus,
    WaitTimeEstimate,
)
from app.schemas.schemas import (
    CheckInRequest,
    CheckInResponse,
    SequenceStepResponse,
    VisitContextResponse,
    VisitContextStepResponse,
)

engine_routes = Path("/packages")
sys.path.append(str(engine_routes))

from rules_engine.src.rules_engine.engine import Study, calculate_sequence

router = APIRouter()

# Placeholder until the ML model is integrated (Task 7 of api TASK.md)
PLACEHOLDER_WAIT_MINUTES = 15

redis_client = redis.from_url(settings.redis_url)


@router.get("/")
async def list_visits(db: AsyncSession = Depends(get_db)):
    """Lists visits. Not implemented yet."""
    return {"status": "not implemented", "resource": "visits"}


@router.post(
    "/check-in",
    response_model=CheckInResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a patient visit and calculate the study sequence",
)
async def check_in(request: CheckInRequest, db: AsyncSession = Depends(get_db)):
    """
    Registers a patient visit (walk-in or appointment) and returns the
    optimal study sequence calculated by the clinical rules engine.

    Steps:
    1. Find or create Patient by phone_number.
    2. Create Visit.
    3. Validate all study_ids map to existing ClinicalArea rows.
    4. Build Study objects for the rules engine.
    5. Run calculate_sequence().
    6. Persist VisitStep rows for each sequence step.
    7. Record arrival PatientEvent.
    8. Push visit_id to Redis queue for the first area.
    9. Return 201 with CheckInResponse.
    """

    # ── Step 1: find or create patient ───────────────────────────────────
    result = await db.execute(
        select(Patient).where(Patient.phone_number == request.phone_number)
    )
    patient = result.scalar_one_or_none()

    if patient is None:
        patient = Patient(
            phone_number=request.phone_number,
            full_name="Paciente " + request.phone_number[-4:],
        )
        db.add(patient)
        await db.flush()  # assigns patient.id before FK use

    # ── Step 2: create visit ──────────────────────────────────────────────
    visit = Visit(
        patient_id=patient.id,
        clinic_id=request.clinic_id,
        status=VisitStatus.PENDING,
        has_appointment=request.has_appointment,
        is_urgent=request.is_urgent,
    )
    db.add(visit)
    await db.flush()  # assigns visit.id before FK use

    # ── Step 3: resolve study_ids → ClinicalArea rows ────────────────────
    areas: list[ClinicalArea] = []
    for study_id in request.study_ids:
        result = await db.execute(
            select(ClinicalArea).where(ClinicalArea.id == study_id)
        )
        area = result.scalar_one_or_none()
        if area is None:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"error": "Area not found", "code": "AREA_NOT_FOUND"},
            )
        areas.append(area)

    # ── Step 4: build Study objects for the rules engine ─────────────────
    # `type` matches Study.type (renamed from study_type in engine.py)
    studies = [
        Study(
            id=str(area.id),
            type=area.study_type,
            requires_fasting=(area.study_type == "laboratorio"),
            is_urgent=request.is_urgent,
            has_appointment=request.has_appointment,
        )
        for area in areas
    ]

    # ── Step 5: calculate optimal sequence ───────────────────────────────
    sequence_result = calculate_sequence(studies)

    # ── Steps 6: persist VisitStep rows ──────────────────────────────────
    area_by_id: dict[str, ClinicalArea] = {str(area.id): area for area in areas}
    sequence_response: list[SequenceStepResponse] = []

    for step in sequence_result.steps:
        area = area_by_id[step.study.id]
        visit_step = VisitStep(
            visit_id=visit.id,
            clinical_area_id=area.id,
            step_order=step.order,
            status=VisitStepStatus.PENDING,
            rule_applied=step.rule_applied,
            estimated_wait_minutes=PLACEHOLDER_WAIT_MINUTES,
        )
        db.add(visit_step)

        sequence_response.append(
            SequenceStepResponse(
                order=step.order,
                area_name=area.name,
                estimated_wait_minutes=PLACEHOLDER_WAIT_MINUTES,
                rule_applied=step.rule_applied,
            )
        )

    # ── Step 7: record arrival event ──────────────────────────────────────
    db.add(
        PatientEvent(
            visit_id=visit.id,
            event_type="arrival",
            event_metadata={},
        )
    )

    # ── Step 8: push to Redis queue for first area ────────────────────────
    if sequence_result.steps:
        first_area_id = sequence_result.steps[0].study.id
        timestamp_score = datetime.now(timezone.utc).timestamp()
        await redis_client.zadd(
            f"queue:{first_area_id}",
            {str(visit.id): timestamp_score},
        )

    # ── Step 9: flush remaining inserts and return ────────────────────────
    await db.flush()

    return CheckInResponse(
        visit_id=visit.id,
        patient_id=patient.id,
        sequence=sequence_response,
        total_estimated_minutes=sequence_result.estimated_time_minutes,
    )


@router.get(
    "/{visit_id}/context",
    response_model=VisitContextResponse,
    summary="Get current visit context for bot or dashboard",
)
async def get_visit_context(
    visit_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Returns the current state of a visit.
    Used by the bot to build WhatsApp messages and by the dashboard.
    """

    # 1. Find visit
    result = await db.execute(select(Visit).where(Visit.id == visit_id))
    visit = result.scalar_one_or_none()

    if visit is None:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": "Visit not found", "code": "VISIT_NOT_FOUND"},
        )

    # 2. Load patient
    result = await db.execute(select(Patient).where(Patient.id == visit.patient_id))
    patient = result.scalar_one()

    # 3. Load all steps ordered
    result = await db.execute(
        select(VisitStep)
        .where(VisitStep.visit_id == visit_id)
        .order_by(VisitStep.step_order)
    )
    steps = list(result.scalars().all())

    if not steps:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": "Visit has no steps", "code": "NO_STEPS_FOUND"},
        )

    # 4. Current step = first non-completed; fallback to last
    current_step = next(
        (s for s in steps if s.status != VisitStepStatus.COMPLETED),
        steps[-1],
    )

    # 5. Live wait time from WaitTimeEstimate if available
    result = await db.execute(
        select(WaitTimeEstimate).where(
            WaitTimeEstimate.clinical_area_id == current_step.clinical_area_id
        )
    )
    wait_estimate = result.scalar_one_or_none()
    current_wait_minutes = (
        wait_estimate.estimated_minutes
        if wait_estimate is not None
        else current_step.estimated_wait_minutes
    )

    # 6. Area name for current step
    result = await db.execute(
        select(ClinicalArea).where(ClinicalArea.id == current_step.clinical_area_id)
    )
    current_area = result.scalar_one()

    current_step_response = VisitContextStepResponse(
        order=current_step.step_order,
        area_name=current_area.name,
        status=current_step.status.value,
        estimated_wait_minutes=current_wait_minutes,
        rule_applied=current_step.rule_applied,
    )

    # 7. Remaining steps (pending, excluding current)
    remaining_steps_response: list[VisitContextStepResponse] = []
    for step in steps:
        if step.status == VisitStepStatus.PENDING and step.id != current_step.id:
            result = await db.execute(
                select(ClinicalArea).where(ClinicalArea.id == step.clinical_area_id)
            )
            area = result.scalar_one()
            remaining_steps_response.append(
                VisitContextStepResponse(
                    order=step.step_order,
                    area_name=area.name,
                    status=step.status.value,
                    estimated_wait_minutes=step.estimated_wait_minutes,
                    rule_applied=step.rule_applied,
                )
            )

    total_estimated_minutes = current_wait_minutes + sum(
        s.estimated_wait_minutes for s in remaining_steps_response
    )

    return VisitContextResponse(
        visit_id=visit.id,
        patient_name=patient.full_name,
        current_step=current_step_response,
        remaining_steps=remaining_steps_response,
        total_estimated_minutes=total_estimated_minutes,
    )
