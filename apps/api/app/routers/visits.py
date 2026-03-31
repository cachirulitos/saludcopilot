import uuid
from datetime import datetime, timezone

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
from rules_engine.engine import Study, calculate_sequence

router = APIRouter()

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
)
async def check_in(request: CheckInRequest, db: AsyncSession = Depends(get_db)):
    """Registers a patient visit and calculates the optimal study sequence."""

    # 1. Find or create patient
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
        await db.flush()

    # 2. Create visit
    visit = Visit(
        patient_id=patient.id,
        clinic_id=request.clinic_id,
        status=VisitStatus.PENDING,
        has_appointment=request.has_appointment,
        is_urgent=request.is_urgent,
    )
    db.add(visit)
    await db.flush()

    # 3. Look up clinical areas for each study_id
    areas = []
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

    # 4. Build Study objects for rules engine
    studies = [
        Study(
            id=str(area.id),
            study_type=area.study_type,
            requires_fasting=(area.study_type == "laboratorio"),
            is_urgent=request.is_urgent,
            has_appointment=request.has_appointment,
        )
        for area in areas
    ]

    # 5. Calculate optimal sequence
    sequence_result = calculate_sequence(studies)

    # 6. Create VisitStep for each step in the sequence
    area_by_id = {str(area.id): area for area in areas}
    sequence_response = []

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

    # 7. Create arrival event
    arrival_event = PatientEvent(
        visit_id=visit.id,
        event_type="arrival",
        event_metadata={},
    )
    db.add(arrival_event)

    # 8. Push to Redis queue for first area
    if sequence_result.steps:
        first_area_id = sequence_result.steps[0].study.id
        timestamp_score = datetime.now(timezone.utc).timestamp()
        await redis_client.zadd(
            f"queue:{first_area_id}",
            {str(visit.id): timestamp_score},
        )

    # 9. Flush all to DB
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
)
async def get_visit_context(
    visit_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Returns the current context of a visit for the bot or dashboard."""

    # 1. Find visit by id
    result = await db.execute(select(Visit).where(Visit.id == visit_id))
    visit = result.scalar_one_or_none()

    if visit is None:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": "Visit not found", "code": "VISIT_NOT_FOUND"},
        )

    # 2. Load related patient
    result = await db.execute(select(Patient).where(Patient.id == visit.patient_id))
    patient = result.scalar_one()

    # 3. Load all visit steps ordered by step_order
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

    # 4. Identify current_step: first step where status != completed
    current_step = None
    for step in steps:
        if step.status != VisitStepStatus.COMPLETED:
            current_step = step
            break

    # If all steps are completed, current_step is the last one
    if current_step is None:
        current_step = steps[-1]

    # 5. For current_step: look up WaitTimeEstimate by clinical_area_id
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

    # Load area name for current step
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

    # 6. remaining_steps: all pending steps excluding current
    remaining_steps_response = []
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

    # 7. total_estimated_minutes = current + remaining
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
