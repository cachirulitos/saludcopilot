import numpy as np


PERSON_CLASS_ID = 0


class PeopleDetector:
    """Detect and count people in video frames using a YOLO model."""

    def __init__(self, model_name: str, confidence_threshold: float) -> None:
        from ultralytics import YOLO

        self.model = YOLO(model_name)
        self.confidence_threshold = confidence_threshold

    def count_people_in_frame(self, frame: np.ndarray) -> int:
        """Return the number of people detected in a single frame."""
        results = self.model(frame, verbose=False)
        return self._count_from_results(results)

    def count_people_with_annotated_frame(
        self, frame: np.ndarray
    ) -> tuple[int, np.ndarray]:
        """Return (people_count, annotated_frame) for display purposes."""
        results = self.model(frame, verbose=False)
        people_count = self._count_from_results(results)
        annotated_frame = results[0].plot()
        return people_count, annotated_frame

    def _count_from_results(self, results) -> int:
        """Count detections matching person class above confidence threshold."""
        return sum(
            1
            for box in results[0].boxes
            if int(box.cls) == PERSON_CLASS_ID
            and float(box.conf) >= self.confidence_threshold
        )
