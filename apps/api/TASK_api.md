# TASK.md — apps/api

> Read CLAUDE.md and ARQUITECTURA.md before starting.
> Complete tasks in order. Do not start the next task until the current one
> passes its acceptance criteria.

---

## Current status

- [x] Project scaffold created
- [x] FastAPI entry point (`app/main.py`)
- [x] Database connection (`app/core/database.py`)
- [x] Config with pydantic-settings (`app/core/config.py`)
- [x] Skeleton routers (return 501)
- [ ] SQLAlchemy models
- [ ] Alembic initial migration
- [ ] Check-in endpoint
- [ ] Visit context endpoint
- [ ] Advance step endpoint
- [ ] Occupancy endpoint
- [ ] Wait time estimate endpoint
- [ ] WebSocket for dashboard
- [ ] Rules engine integration
- [ ] Internal bot notification trigger

---

## Task 1 — SQLAlchemy models

Create `apps/api/app/models/models.py` with all models.
Schema source of truth: ARQUITECTURA.md → Database schema section.

**Models to implement:**
`Patient`, `Clinic`, `ClinicalArea`, `Visit`, `VisitStep`,
`Notification`, `ClinicalRule`, `WaitTimeEstimate`, `PatientEvent`

**Requirements:**

- All models inherit from `Base` (from `app/core/database.py`)
- Use SQLAlchemy 2.0 style: `Mapped` and `mapped_column` — not legacy `Column`
- All primary keys are UUID with `default=uuid.uuid4`
- All timestamps are `TIMESTAMPTZ` (timezone-aware)
- `PatientEvent` has NO `updated_at` — it is append-only by design
- All ENUMs are Python `enum.Enum` subclasses defined before the models that use them
- Every model has `__repr__` showing `id` and one human-readable field
- All FK columns have their corresponding `relationship()` on both sides

**Acceptance criteria:**

```bash
python -c "from app.models.models import Patient, Visit, VisitStep, ClinicalArea; print('OK')"
# Must print OK with zero import errors
```

---

## Task 2 — Alembic initial migration

Run after Task 1 is verified:

```bash
cd apps/api
alembic revision --autogenerate -m "initial_schema"
alembic upgrade head
```

**Acceptance criteria:**

- `alembic upgrade head` exits 0
- All 9 tables exist in PostgreSQL
- `alembic downgrade -1` exits 0 and removes all tables cleanly

---

## Task 3 — Check-in endpoint (critical path — bot depends on this)

Implement `POST /api/v1/visits/check-in` in `app/routers/visits.py`.

**Contract:** ARQUITECTURA.md → "Bot → API (check-in)"

**Step-by-step logic:**

1. Look up `Patient` by `phone_number`. Create if not found.
2. Create `Visit` with `status=pending`.
3. Resolve `study_ids` to `ClinicalArea` records. Return 404 if any not found.
4. Build `Study` objects and call `rules_engine.calculate_sequence(studies)`.
5. Create `VisitStep` records from the sequence. Store `rule_applied` from engine output.
6. Create `PatientEvent` with `event_type="arrival"`.
7. Push `visit_id` to Redis sorted set: `queue:{first_area_id}` with score = `time.time()`.
8. Return 201 with full sequence and `total_estimated_minutes`.

**Rules engine import:**

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../../packages"))
from rules_engine.src.engine import calculate_sequence, Study
```

**Study fields the engine expects:**

- `id: str`
- `type: str` — must match `clinical_areas.study_type`
- `requires_fasting: bool`
- `is_urgent: bool`
- `has_appointment: bool`

**Acceptance criteria:**

- Returns 201 with correct sequence for valid payload
- Creates new patient if phone number is new
- Reuses existing patient if phone number already exists
- `VisitStep.step_order` matches rules engine output
- Redis queue contains the `visit_id`
- Returns 422 for missing required fields
- Returns 404 if any `study_id` is not found in `clinical_areas`

---

## Task 4 — Visit context endpoint (critical path — bot depends on this)

Implement `GET /api/v1/visits/{visit_id}/context` in `app/routers/visits.py`.

**Contract:** ARQUITECTURA.md → "Bot → API (visit context)"

**Logic:**

1. Fetch `Visit` + all `VisitStep` records + `Patient` from DB.
2. Current step = first step where `status != completed`.
3. Fetch `WaitTimeEstimate` for current step's `clinical_area_id`.
4. Build and return response.

**Acceptance criteria:**

- Returns 200 with correct structure for existing visit
- Returns 404 with `{"error": "Visit not found", "code": "VISIT_NOT_FOUND"}` for unknown id
- `estimated_wait_minutes` comes from `WaitTimeEstimate` table, not hardcoded

---

## Task 5 — Occupancy endpoint (critical path — CV worker depends on this)

Implement `POST /api/v1/areas/{area_id}/occupancy` in `app/routers/areas.py`.

**Contract:** ARQUITECTURA.md → "CV Worker → API (occupancy)"

**Logic:**

1. Validate area exists. Return 404 if not.
2. Store in Redis: `occupancy:{area_id}` = `people_count`, TTL 30 seconds.
3. Calculate updated wait time estimate using placeholder formula:
   `estimated_minutes = base_minutes_for_study_type + (people_count * 5)`
   (Real ML model replaces this in Task 8)
4. Upsert `WaitTimeEstimate` in PostgreSQL.
5. Return `{"wait_time_estimate_minutes": int}`.

**Acceptance criteria:**

- Returns 200 with estimate
- Redis key `occupancy:{area_id}` is set with 30s TTL
- `WaitTimeEstimate` row is created or updated in PostgreSQL
- Returns 404 for unknown `area_id`

---

## Task 6 — Advance step endpoint

Implement `POST /api/v1/visits/{visit_id}/advance-step` in `app/routers/visits.py`.

**Logic:**

1. Find the current step: first step with `status=in_progress`,
   or first step with `status=pending` if none are in progress.
2. Mark it `completed`. Set `completed_at=now()`. Calculate `actual_wait_minutes`.
3. Find next `pending` step.
4. If next step exists: mark it `in_progress`, set `started_at=now()`.
5. Remove `visit_id` from Redis queue of completed area.
6. Add `visit_id` to Redis queue of next area.
7. Create `PatientEvent` with `event_type="step_completed"`.
8. If no next step: set `Visit.status=completed`, set `completed_at=now()`,
   create `PatientEvent` with `event_type="visit_completed"`.
9. Call internal bot notification (implement as a simple `httpx.post` to bot service).

**Acceptance criteria:**

- Step statuses transition correctly in DB
- Redis queues updated: removed from old area, added to new area
- `PatientEvent` created for each transition
- Visit marked completed when last step is done
- Returns 404 for unknown visit

---

## Task 7 — Wait time estimate endpoint

Implement `GET /api/v1/areas/{area_id}/wait-time-estimate` in `app/routers/areas.py`.

**Logic:**

1. Validate area exists.
2. Get current `WaitTimeEstimate` from PostgreSQL.
3. Get current queue length from Redis: `ZCARD queue:{area_id}`.
4. Return estimate with queue context.

**Response:**

```json
{
  "area_id": "uuid",
  "estimated_wait_minutes": int,
  "current_queue_length": int,
  "people_in_area": int,
  "updated_at": "ISO8601"
}
```

**Acceptance criteria:**

- Returns current estimate from DB
- `current_queue_length` comes from Redis, not DB
- Returns 404 for unknown area

---

## Do not implement yet

- JWT authentication (use hardcoded `INTERNAL_API_TOKEN` from settings)
- WebSocket (implement after critical path endpoints are working)
- Post-visit recommendations
- Results delivery endpoint
- ML model integration (placeholder formula is sufficient for now)
