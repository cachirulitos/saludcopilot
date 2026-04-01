"""
SaludCopilot API — Pydantic v2 schemas
=======================================
Request/response contracts as defined in ARQUITECTURA.md.
"""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── Request schemas ──────────────────────────────────────────────────────────


class CheckInRequest(BaseModel):
    phone_number: str = Field(..., pattern=r"^\+[1-9]\d{1,14}$", description="E.164 format")
    clinic_id: uuid.UUID
    study_ids: list[uuid.UUID]
    has_appointment: bool
    is_urgent: bool


class OccupancyUpdateRequest(BaseModel):
    people_count: int = Field(..., ge=0)
    timestamp: datetime


class AdvanceStepRequest(BaseModel):
    pass


# ── Response schemas ─────────────────────────────────────────────────────────


class SequenceStepResponse(BaseModel):
    order: int
    area_name: str
    estimated_wait_minutes: int
    rule_applied: Optional[str] = None


class CheckInResponse(BaseModel):
    visit_id: uuid.UUID
    patient_id: uuid.UUID
    sequence: list[SequenceStepResponse]
    total_estimated_minutes: int


class VisitContextStepResponse(BaseModel):
    """Step detail for visit context — includes status per ARQUITECTURA.md contract."""
    order: int
    area_name: str
    status: str
    estimated_wait_minutes: int
    rule_applied: Optional[str] = None


class VisitContextResponse(BaseModel):
    visit_id: uuid.UUID
    patient_name: str
    current_step: VisitContextStepResponse
    remaining_steps: list[VisitContextStepResponse]
    total_estimated_minutes: int


class OccupancyResponse(BaseModel):
    wait_time_estimate_minutes: int


class AdvanceStepStepResponse(BaseModel):
    order: int
    area_name: str
    status: str
    actual_wait_minutes: Optional[int] = None


class AdvanceStepResponse(BaseModel):
    visit_id: uuid.UUID
    visit_status: str
    completed_step: AdvanceStepStepResponse
    next_step: Optional[AdvanceStepStepResponse] = None


class WaitTimeEstimateResponse(BaseModel):
    area_id: uuid.UUID
    estimated_wait_minutes: int
    current_queue_length: int
    people_in_area: int
    updated_at: datetime


class ErrorResponse(BaseModel):
    error: str
    code: str
