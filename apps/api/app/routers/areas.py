import uuid
from datetime import datetime, timezone

import redis.asyncio as redis
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.models import ClinicalArea, WaitTimeEstimate
from app.schemas.schemas import OccupancyUpdateRequest, OccupancyResponse

router = APIRouter()

redis_client = redis.from_url(settings.redis_url)

OCCUPANCY_TTL_SECONDS = 30

BASE_WAIT_TIMES = {
    "laboratorio": 15,
    "ultrasonido": 20,
    "rayos_x": 12,
    "electrocardiograma": 8,
    "papanicolaou": 10,
    "densitometria": 15,
    "tomografia": 25,
}

WAIT_MINUTES_PER_PERSON = 3
WAIT_MINUTES_PER_QUEUED = 5
DEFAULT_BASE_WAIT_MINUTES = 15


@router.post("/{area_id}/occupancy", response_model=OccupancyResponse)
async def update_occupancy(
    area_id: uuid.UUID,
    request: OccupancyUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Receive people count from CV worker and update wait time estimate."""

    # 1. Find ClinicalArea
    result = await db.execute(
        select(ClinicalArea).where(ClinicalArea.id == area_id)
    )
    area = result.scalar_one_or_none()
    if area is None:
        return JSONResponse(
            status_code=404,
            content={"error": "Area not found", "code": "AREA_NOT_FOUND"},
        )

    # 2. Store occupancy in Redis with TTL
    await redis_client.set(
        f"occupancy:{area_id}", request.people_count, ex=OCCUPANCY_TTL_SECONDS
    )

    # 3. Get queue length from Redis
    queue_length = await redis_client.zcard(f"queue:{area_id}")

    # 4. Calculate estimated wait (placeholder until ML integration)
    base = BASE_WAIT_TIMES.get(area.study_type, DEFAULT_BASE_WAIT_MINUTES)
    estimated_minutes = (
        base
        + (request.people_count * WAIT_MINUTES_PER_PERSON)
        + (queue_length * WAIT_MINUTES_PER_QUEUED)
    )

    # 5. Upsert WaitTimeEstimate
    result = await db.execute(
        select(WaitTimeEstimate).where(
            WaitTimeEstimate.clinical_area_id == area_id
        )
    )
    wait_estimate = result.scalar_one_or_none()

    if wait_estimate is not None:
        wait_estimate.estimated_minutes = estimated_minutes
        wait_estimate.people_in_area = request.people_count
        wait_estimate.updated_at = datetime.now(timezone.utc)
    else:
        wait_estimate = WaitTimeEstimate(
            clinical_area_id=area_id,
            estimated_minutes=estimated_minutes,
            people_in_area=request.people_count,
        )
        db.add(wait_estimate)

    await db.commit()

    # 6. Return response
    return OccupancyResponse(wait_time_estimate_minutes=estimated_minutes)


@router.get("/")
async def list_areas(db: AsyncSession = Depends(get_db)):
    return {"status": "not implemented", "resource": "areas"}
