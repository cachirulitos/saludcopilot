# TASK.md — apps/cv

> Read CLAUDE.md and ARQUITECTURA.md before starting.
> The CV worker depends on the API occupancy endpoint.
> Confirm Task 5 in apps/api/TASK.md is complete before implementing Task 3 here.

---

## Current status

- [x] Project scaffold created
- [x] requirements.txt
- [ ] Configuration and area mapping
- [ ] YOLOv8 people detector
- [ ] API count publisher
- [ ] Main capture loop
- [ ] Demo mode (no camera required)

---

## What this module does — read this first

The CV worker is a standalone Python process — not a web server.
It runs a continuous loop:
1. Capture frame from camera
2. Detect and count people with YOLOv8
3. POST count to API every N seconds
4. Repeat

It has no database. It has no Redis. It has no UI.
Its only output is HTTP POST requests to the API occupancy endpoint.

For the hackathon demo, it runs on a laptop with a webcam
pointed at a space where team members simulate patients.
The loop closes: camera → YOLOv8 → API → ML model → WhatsApp update → dashboard.

---

## Task 1 — Configuration

Create `apps/cv/config.py`.

```python
from pydantic_settings import BaseSettings

class CVSettings(BaseSettings):
    # API connection
    api_base_url: str = "http://localhost:8000"
    internal_cv_token: str = ""

    # Camera
    camera_index: int = 0
    capture_interval_seconds: int = 5

    # Detection
    yolo_model_name: str = "yolov8n.pt"    # nano — fastest, sufficient for demo
    confidence_threshold: float = 0.4
    target_class_id: int = 0               # YOLO class 0 = person

    # Maps camera index to clinical_area UUID in the database
    # Set via env var as JSON string: '{"0": "uuid-of-area"}'
    camera_to_area_mapping: str = "{}"

    class Config:
        env_file = ".env"
        case_sensitive = False

settings = CVSettings()
```

**Acceptance criteria:**
- Settings load from `.env` without error
- `camera_to_area_mapping` is valid JSON parseable to a dict

---

## Task 2 — YOLOv8 people detector

Create `apps/cv/models/people_detector.py`.

```python
import numpy as np

class PeopleDetector:
    """
    Wraps YOLOv8 for people counting in video frames.
    Model loads once at initialization — never on each frame.
    """

    def __init__(self, model_name: str, confidence_threshold: float) -> None:
        """
        Load YOLOv8 model from ultralytics.
        yolov8n.pt downloads automatically on first run (~6MB).
        """

    def count_people_in_frame(self, frame: np.ndarray) -> int:
        """
        Run inference on a single BGR frame (OpenCV format).
        Returns count of detections where class=0 (person)
        and confidence >= threshold.
        Does not modify the frame.
        """

    def count_people_with_annotated_frame(
        self, frame: np.ndarray
    ) -> tuple[int, np.ndarray]:
        """
        Run inference and return (count, annotated_frame).
        annotated_frame has bounding boxes drawn — for demo display only.
        """
```

**Implementation sketch:**
```python
from ultralytics import YOLO

results = self.model(frame, verbose=False)
count = sum(
    1 for box in results[0].boxes
    if int(box.cls) == 0 and float(box.conf) >= self.confidence_threshold
)
```

**Acceptance criteria:**
- Model loads once in `__init__`, confirmed by single download on first run
- `count_people_in_frame` always returns int >= 0, never raises
- Works with BGR numpy arrays from OpenCV
- Test in `tests/test_people_detector.py` passes a synthetic black frame
  and verifies return type is int (count on black frame = 0)

---

## Task 3 — API count publisher

Create `apps/cv/services/count_publisher.py`.

```python
from datetime import datetime, timezone

async def publish_people_count(area_id: str, people_count: int) -> int | None:
    """
    POST people count to API occupancy endpoint.

    Endpoint: POST {api_base_url}/api/v1/areas/{area_id}/occupancy
    Auth: Bearer {internal_cv_token}
    Body: {"people_count": int, "timestamp": "ISO8601"}

    Returns wait_time_estimate_minutes from API response on success.
    Returns None on any failure — logs error, never raises.
    """
```

**Acceptance criteria:**
- Uses `httpx.AsyncClient` (async, not requests)
- Timestamp in ISO8601 format with timezone: `datetime.now(timezone.utc).isoformat()`
- Returns None on connection error, timeout, or non-2xx response
- Logs both successes and failures with count, area_id, and result
- Test mocks HTTP and verifies exact request body structure

---

## Task 4 — Main capture loop

Create `apps/cv/main.py`.

**Entry point. `python main.py` starts the worker.**

**Logic:**
```
1. Parse args (--demo flag for Task 5)
2. Load config, parse camera_to_area_mapping as dict
3. Initialize PeopleDetector
4. Open camera: cv2.VideoCapture(camera_index)
5. If camera fails to open: print clear error message, sys.exit(1)
6. Start async loop:
   a. Read frame: ret, frame = cap.read()
   b. If ret is False: log warning, continue (transient frame drop)
   c. count, annotated = detector.count_people_with_annotated_frame(frame)
   d. For each area_id in mapping:
      estimate = await publish_people_count(area_id, count)
      log: f"Area {area_id}: {count} people | Est. wait: {estimate} min"
   e. Display annotated frame in OpenCV window (demo visibility)
   f. await asyncio.sleep(capture_interval_seconds)
7. On KeyboardInterrupt: cap.release(), cv2.destroyAllWindows(), exit cleanly
```

**Demo window — important for jury impression:**
```python
cv2.imshow("SaludCopilot — Sala de espera", annotated_frame)
cv2.waitKey(1)  # non-blocking, keeps window responsive
```

The jury must be able to see bounding boxes appear around people in real time.
This makes the system tangible — not just a number in a log.

**Acceptance criteria:**
- `python main.py` starts loop without error when camera is available
- Camera failure exits with: "Error: no se pudo abrir la cámara (índice {N}). Verifica que esté conectada."
- Ctrl+C exits cleanly — no traceback, camera released, window closed
- Count logged every interval
- Annotated frame visible in OpenCV window

---

## Task 5 — Demo mode (no camera required)

Add `--demo` flag support to `main.py`.

**Why this exists:**
If the webcam fails during the presentation, the team can switch to demo mode
instantly. The loop still posts real counts to the API — only the frame source changes.

**Demo mode behavior:**
- No camera opened
- Simulated count pattern: starts at 3, +1 every 3 intervals, resets to 2 at 8
  Pattern: 3, 3, 3, 4, 4, 4, 5, 5, 5, 6, 6, 6, 7, 7, 7, 8, 8, 8, 2, 3, 3, 3...
- Display a black frame with white text overlay: "DEMO MODE — N personas detectadas"
- All other behavior identical: posts to API, logs, OpenCV window

**Usage:**
```bash
python main.py --demo
```

**Acceptance criteria:**
- Runs without camera on any machine
- Count follows exact simulated pattern
- API still receives real POST requests with simulated count
- Window shows "DEMO MODE" + current count clearly
- Seamless switch: same log format as real mode

---

## Area mapping — how to configure

```bash
# In .env (single camera for demo)
CAMERA_TO_AREA_MAPPING='{"0": "paste-area-uuid-from-db-here"}'
```

The UUID comes from the `clinical_areas` table after running seed data.
Ask Dev 1 (API) for the UUID of the waiting room area once the DB is seeded.

---

## Do not implement yet

- Multiple simultaneous cameras beyond index mapping
- Zone-based counting within frame regions
- Camera health monitoring or auto-reconnect
- Video file as input source
