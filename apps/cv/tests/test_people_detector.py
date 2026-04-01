import sys
from unittest.mock import MagicMock

import numpy as np

CONFIDENCE_THRESHOLD = 0.4

# Mock ultralytics before importing PeopleDetector
_mock_yolo_class = MagicMock()
_mock_ultralytics = MagicMock()
_mock_ultralytics.YOLO = _mock_yolo_class
sys.modules["ultralytics"] = _mock_ultralytics

from models.people_detector import PeopleDetector


def _make_box(cls_id: int, confidence: float):
    """Create a mock detection box."""
    box = MagicMock()
    box.cls = cls_id
    box.conf = confidence
    return box


def _make_detector(boxes):
    """Create a PeopleDetector with a mocked YOLO model returning the given boxes."""
    mock_results_item = MagicMock()
    mock_results_item.boxes = boxes
    mock_results_item.plot.return_value = np.zeros((480, 640, 3), dtype=np.uint8)

    mock_model = MagicMock()
    mock_model.return_value = [mock_results_item]

    detector = PeopleDetector("yolov8n.pt", CONFIDENCE_THRESHOLD)
    detector.model = mock_model
    return detector


def test_count_returns_integer_for_black_frame():
    boxes = [_make_box(0, 0.8), _make_box(0, 0.6)]
    detector = _make_detector(boxes)
    black_frame = np.zeros((480, 640, 3), dtype=np.uint8)

    result = detector.count_people_in_frame(black_frame)

    assert isinstance(result, int)
    assert result == 2


def test_count_returns_zero_for_empty_frame():
    detector = _make_detector(boxes=[])
    empty_frame = np.zeros((480, 640, 3), dtype=np.uint8)

    result = detector.count_people_in_frame(empty_frame)

    assert result == 0
