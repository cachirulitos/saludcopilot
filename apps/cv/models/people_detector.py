import statistics
from collections import deque

import numpy as np


PERSON_CLASS_ID = 0


class PeopleDetector:
    """Detect and count people in video frames using a YOLO model.

    Raw per-frame counts are smoothed with a rolling median over a configurable
    window so that momentary detection failures (occlusion, motion blur) do not
    cause the published count — and therefore the ML wait-time estimate — to
    spike up or down.
    """

    def __init__(
        self,
        model_name: str,
        confidence_threshold: float,
        smoothing_window: int = 15,
    ) -> None:
        from ultralytics import YOLO

        self.model = YOLO(model_name)
        self.confidence_threshold = confidence_threshold
        self._window: deque[int] = deque(maxlen=smoothing_window)

    def count_people_in_frame(self, frame: np.ndarray) -> int:
        """Return the smoothed number of people detected in a single frame."""
        results = self.model(frame, verbose=False, classes=[PERSON_CLASS_ID])
        return self._smooth(self._count_from_results(results))

    def count_people_with_annotated_frame(
        self, frame: np.ndarray
    ) -> tuple[int, np.ndarray]:
        """Return (smoothed_count, annotated_frame) for display purposes.

        Only person detections are run and drawn — non-human objects are ignored
        at inference time by passing classes=[PERSON_CLASS_ID] to the model.
        """
        results = self.model(frame, verbose=False, classes=[PERSON_CLASS_ID])
        smoothed_count = self._smooth(self._count_from_results(results))
        annotated_frame = results[0].plot()
        return smoothed_count, annotated_frame

    def _smooth(self, raw_count: int) -> int:
        """Append raw_count to the window and return the rolling median."""
        self._window.append(raw_count)
        return round(statistics.median(self._window))

    def _count_from_results(self, results) -> int:
        """Count person detections above the confidence threshold."""
        return sum(
            1
            for box in results[0].boxes
            if int(box.cls) == PERSON_CLASS_ID
            and float(box.conf) >= self.confidence_threshold
        )
