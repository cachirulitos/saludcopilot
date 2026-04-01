import uuid
from datetime import datetime, timezone

import redis.asyncio as redis
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.routers.dashboard import broadcast_to_clinic
from app.services.notification_service import trigger_bot_notification
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
    AdvanceStepResponse,
    AdvanceStepStepResponse,
    CheckInRequest,
    CheckInResponse,
    SequenceStepResponse,
    VisitContextResponse,
    VisitContextStepResponse,
)
from rules_engine.engine import Study, calculate_sequence

router = APIRouter()

PLACEHOLDER_WAIT_MINUTES = 15
FASTING_STUDY_TYPE = "laboratorio"
DEFAULT_PATIENT_NAME_PREFIX = "Paciente "

redis_client = redis.from_url(settings.redis_url)


# ── Helpers ─────────────────────────────────────────────────────────────────


async def _find_or_create_patient(
    phone_number: str, db: AsyncSession
) -> Patient:
    """Look up a patient by phone, creating a stub record if not found."""
    result = await db.execute(
        select(Patient).where(Patient.phone_number == phone_number)
    )
    patient = result.scalar_one_or_none()
    if patient is None:
        patient = Patient(
            phone_number=phone_number,
            full_name=DEFAULT_PATIENT_NAME_PREFIX + phone_number[-4:],
        )
        db.add(patient)
        await db.flush()
    return patient


async def _resolve_clinical_areas(
    study_ids: list[uuid.UUID], db: AsyncSession
) -> list[ClinicalArea] | JSONResponse:
    """Fetch ClinicalArea for each study_id. Returns JSONResponse on 404."""
    areas = []
    for study_id in study_ids:
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
    return areas


def _build_studies(
    areas: list[ClinicalArea], is_urgent: bool, has_appointment: bool
) -> list[Study]:
    """Convert ClinicalArea rows into rules-engine Study objects."""
    return [
        Study(
            id=str(area.id),
            study_type=area.study_type,
            requires_fasting=(area.study_type == FASTING_STUDY_TYPE),
            is_urgent=is_urgent,
            has_appointment=has_appointment,
        )
        for area in areas
    ]


async def _enqueue_first_area(visit_id: uuid.UUID, first_area_id: str) -> None:
    """Push the visit into the Redis queue for its first clinical area."""
    timestamp_score = datetime.now(timezone.utc).timestamp()
    await redis_client.zadd(
        f"queue:{first_area_id}",
        {str(visit_id): timestamp_score},
    )


async def _load_area_by_id(
    area_id: uuid.UUID, db: AsyncSession
) -> ClinicalArea:
    """Fetch a single ClinicalArea by primary key."""
    result = await db.execute(
        select(ClinicalArea).where(ClinicalArea.id == area_id)
    )
    return result.scalar_one()


async def _find_visit_step_by_status(
    visit_id: uuid.UUID, step_status: VisitStepStatus, db: AsyncSession
) -> VisitStep | None:
    """Return the first VisitStep matching the given status, ordered by step_order."""
    result = await db.execute(
        select(VisitStep)
        .where(VisitStep.visit_id == visit_id, VisitStep.status == step_status)
        .order_by(VisitStep.step_order)
    )
    return result.scalar_one_or_none()


async def _complete_current_step(current_step: VisitStep) -> int:
    """Mark a step as completed and return actual_wait_minutes."""
    now = datetime.now(timezone.utc)
    current_step.status = VisitStepStatus.COMPLETED
    current_step.completed_at = now
    actual_wait_minutes = 0
    if current_step.started_at is not None:
        delta = now - current_step.started_at
        actual_wait_minutes = int(delta.total_seconds() / 60)
    current_step.actual_wait_minutes = actual_wait_minutes
    return actual_wait_minutes


async def _start_next_step(
    next_step: VisitStep, current_area_id: uuid.UUID, visit_id: uuid.UUID
) -> None:
    """Mark next step as in_progress and move the visit between Redis queues."""
    now = datetime.now(timezone.utc)
    next_step.status = VisitStepStatus.IN_PROGRESS
    next_step.started_at = now
    await redis_client.zrem(f"queue:{current_area_id}", str(visit_id))
    await redis_client.zadd(
        f"queue:{next_step.clinical_area_id}",
        {str(visit_id): now.timestamp()},
    )


async def _finish_visit(
    visit: Visit, current_area_id: uuid.UUID, db: AsyncSession
) -> None:
    """Mark the visit as completed and clean up the Redis queue."""
    now = datetime.now(timezone.utc)
    visit.status = VisitStatus.COMPLETED
    visit.completed_at = now
    visit_completed_event = PatientEvent(
        visit_id=visit.id,
        event_type="visit_completed",
        event_metadata={},
    )
    db.add(visit_completed_event)
    await redis_client.zrem(f"queue:{current_area_id}", str(visit.id))


# ── Endpoints ───────────────────────────────────────────────────────────────


@router.get("/")
async def list_visits(db: AsyncSession = Depends(get_db)):
    """List visits. Not implemented yet."""
    return {"status": "not implemented", "resource": "visits"}


@router.post(
    "/check-in",
    response_model=CheckInResponse,
    status_code=status.HTTP_201_CREATED,
)
async def check_in(request: CheckInRequest, db: AsyncSession = Depends(get_db)):
    """Register a patient visit and calculate the optimal study sequence."""
    patient = await _find_or_create_patient(request.phone_number, db)

    visit = Visit(
        patient_id=patient.id,
        clinic_id=request.clinic_id,
        status=VisitStatus.PENDING,
        has_appointment=request.has_appointment,
        is_urgent=request.is_urgent,
    )
    db.add(visit)
    await db.flush()

    areas = await _resolve_clinical_areas(request.study_ids, db)
    if isinstance(areas, JSONResponse):
        return areas

    studies = _build_studies(areas, request.is_urgent, request.has_appointment)
    sequence_result = calculate_sequence(studies)

    area_by_id = {str(area.id): area for area in areas}
    sequence_response = []
    for step in sequence_result.steps:
        area = area_by_id[step.study.id]
        db.add(VisitStep(
            visit_id=visit.id,
            clinical_area_id=area.id,
            step_order=step.order,
            status=VisitStepStatus.PENDING,
            rule_applied=step.rule_applied,
            estimated_wait_minutes=PLACEHOLDER_WAIT_MINUTES,
        ))
        sequence_response.append(SequenceStepResponse(
            order=step.order,
            area_name=area.name,
            estimated_wait_minutes=PLACEHOLDER_WAIT_MINUTES,
            rule_applied=step.rule_applied,
        ))

    db.add(PatientEvent(visit_id=visit.id, event_type="arrival", event_metadata={}))

    if sequence_result.steps:
        await _enqueue_first_area(visit.id, sequence_result.steps[0].study.id)

    await db.flush()

    response = CheckInResponse(
        visit_id=visit.id,
        patient_id=patient.id,
        sequence=sequence_response,
        total_estimated_minutes=sequence_result.estimated_time_minutes,
    )
    await trigger_bot_notification(
        visit_id=str(visit.id),
        notification_type="welcome",
        payload=response.model_dump(mode="json"),
    )
    return response


@router.get("/{visit_id}/context", response_model=VisitContextResponse)
async def get_visit_context(
    visit_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Return the current context of a visit for the bot or dashboard."""
    result = await db.execute(select(Visit).where(Visit.id == visit_id))
    visit = result.scalar_one_or_none()
    if visit is None:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": "Visit not found", "code": "VISIT_NOT_FOUND"},
        )

    result = await db.execute(select(Patient).where(Patient.id == visit.patient_id))
    patient = result.scalar_one()

    result = await db.execute(
        select(VisitStep)
        .where(VisitStep.visit_id == visit_id)
        .order_by(VisitStep.step_order)
    )
    visit_steps = list(result.scalars().all())
    if not visit_steps:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": "Visit has no steps", "code": "NO_STEPS_FOUND"},
        )

    current_step = next(
        (s for s in visit_steps if s.status != VisitStepStatus.COMPLETED),
        visit_steps[-1],
    )

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

    current_area = await _load_area_by_id(current_step.clinical_area_id, db)
    current_step_response = VisitContextStepResponse(
        order=current_step.step_order,
        area_name=current_area.name,
        status=current_step.status.value,
        estimated_wait_minutes=current_wait_minutes,
        rule_applied=current_step.rule_applied,
    )

    remaining_steps_response = []
    for step in visit_steps:
        if step.status == VisitStepStatus.PENDING and step.id != current_step.id:
            area = await _load_area_by_id(step.clinical_area_id, db)
            remaining_steps_response.append(VisitContextStepResponse(
                order=step.step_order,
                area_name=area.name,
                status=step.status.value,
                estimated_wait_minutes=step.estimated_wait_minutes,
                rule_applied=step.rule_applied,
            ))

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


@router.post("/{visit_id}/advance-step", response_model=AdvanceStepResponse)
async def advance_step(
    visit_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Advance the current visit step to completed and start the next one."""
    result = await db.execute(select(Visit).where(Visit.id == visit_id))
    visit = result.scalar_one_or_none()
    if visit is None:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": "Visit not found", "code": "VISIT_NOT_FOUND"},
        )

    current_step = await _find_visit_step_by_status(visit_id, VisitStepStatus.IN_PROGRESS, db)
    if current_step is None:
        current_step = await _find_visit_step_by_status(visit_id, VisitStepStatus.PENDING, db)
    if current_step is None:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "No steps to advance", "code": "NO_STEPS"},
        )

    actual_wait_minutes = await _complete_current_step(current_step)
    current_area = await _load_area_by_id(current_step.clinical_area_id, db)

    db.add(PatientEvent(
        visit_id=visit.id,
        event_type="step_completed",
        event_metadata={"area": current_area.name, "actual_wait": actual_wait_minutes},
    ))

    next_step = await _find_visit_step_by_status(visit_id, VisitStepStatus.PENDING, db)
    completed_step_response = AdvanceStepStepResponse(
        order=current_step.step_order,
        area_name=current_area.name,
        status="completed",
        actual_wait_minutes=actual_wait_minutes,
    )
    next_step_response = None

    if next_step is not None:
        await _start_next_step(next_step, current_step.clinical_area_id, visit.id)
        next_area = await _load_area_by_id(next_step.clinical_area_id, db)
        next_step_response = AdvanceStepStepResponse(
            order=next_step.step_order,
            area_name=next_area.name,
            status="in_progress",
        )
        position = await redis_client.zrank(
            f"queue:{next_step.clinical_area_id}", str(visit.id)
        )
        await trigger_bot_notification(
            visit_id=str(visit.id),
            notification_type="turn_ready",
            payload={
                "area_name": next_area.name,
                "estimated_wait_minutes": next_step.estimated_wait_minutes or PLACEHOLDER_WAIT_MINUTES,
                "position_in_queue": position if position is not None else 0,
            },
        )
    else:
        await _finish_visit(visit, current_step.clinical_area_id, db)

    await db.flush()

    broadcast_area_name = next_step_response.area_name if next_step_response else current_area.name
    await broadcast_to_clinic(
        str(visit.clinic_id),
        {
            "event": "visit_updated",
            "data": {"status": visit.status.value, "current_area": broadcast_area_name},
        },
    )

    return AdvanceStepResponse(
        visit_id=visit.id,
        visit_status=visit.status.value,
        completed_step=completed_step_response,
        next_step=next_step_response,
    )
