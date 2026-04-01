from dataclasses import dataclass, field

import numpy as np

PERSON_CLASS_ID = 0

THRESHOLD_WARNING = 4
THRESHOLD_SATURATED = 7

# BGR colors
COLOR_NORMAL = (80, 200, 80)
COLOR_WARNING = (0, 165, 255)
COLOR_SATURATED = (0, 0, 220)
COLOR_OUTSIDE_ROI = (100, 100, 100)


def classify_status(count: int) -> str:
    """Return 'normal', 'warning', or 'saturated' based on people count."""
    if count >= THRESHOLD_SATURATED:
        return "saturated"
    if count >= THRESHOLD_WARNING:
        return "warning"
    return "normal"


def status_color(status: str) -> tuple[int, int, int]:
    """Return BGR color for a given status string."""
    return {"normal": COLOR_NORMAL, "warning": COLOR_WARNING, "saturated": COLOR_SATURATED}.get(
        status, COLOR_NORMAL
    )


def point_in_roi(cx: float, cy: float, roi: tuple[int, int, int, int]) -> bool:
    """Return True if (cx, cy) falls inside the ROI rectangle."""
    x1, y1, x2, y2 = roi
    return x1 <= cx <= x2 and y1 <= cy <= y2


@dataclass
class DetectionFrame:
    """Result of one detection pass."""

    count: int
    status: str
    color: tuple[int, int, int]
    tracks_in_roi: list = field(default_factory=list)   # [(x1,y1,x2,y2,track_id), ...]
    tracks_outside_roi: list = field(default_factory=list)


class PeopleDetector:
    """Detect and track people in video frames using YOLOv8 + ByteTrack.

    ByteTrack assigns persistent IDs to each person across frames, giving a
    stable per-area count without needing temporal smoothing. People whose
    bounding-box center falls outside the configured ROI are excluded from the
    count but still drawn (dimmed) so operators can see the full frame.
    """

    def __init__(self, model_name: str, confidence_threshold: float) -> None:
        from ultralytics import YOLO

        self.model = YOLO(model_name)
        self.confidence_threshold = confidence_threshold

    def detect(
        self,
        frame: np.ndarray,
        roi: tuple[int, int, int, int] | None = None,
    ) -> DetectionFrame:
        """Run ByteTrack on frame and return a DetectionFrame.

        Args:
            frame: BGR image as numpy array.
            roi: Optional (x1, y1, x2, y2) rectangle. When provided, only
                people whose center falls inside are counted. Outside people
                are still tracked but excluded from the count.
        """
        results = self.model.track(
            frame,
            persist=True,
            classes=[PERSON_CLASS_ID],
            tracker="bytetrack.yaml",
            verbose=False,
        )

        in_roi: list = []
        outside_roi: list = []

        boxes = results[0].boxes
        if boxes is not None and len(boxes) > 0:
            for box in boxes:
                if float(box.conf) < self.confidence_threshold:
                    continue

                x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())
                cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
                track_id = int(box.id[0]) if box.id is not None else -1
                entry = (x1, y1, x2, y2, track_id)

                if roi is None or point_in_roi(cx, cy, roi):
                    in_roi.append(entry)
                else:
                    outside_roi.append(entry)

        count = len(in_roi)
        s = classify_status(count)
        return DetectionFrame(
            count=count,
            status=s,
            color=status_color(s),
            tracks_in_roi=in_roi,
            tracks_outside_roi=outside_roi,
        )
