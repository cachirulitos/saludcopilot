import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

_ML_SRC = str(Path(__file__).parent.parent.parent.parent.parent / "ml" / "src")
sys.path.insert(0, _ML_SRC)

_predictor = None


def get_predictor():
    """Return the singleton WaitTimePredictor, loading artifacts on first call."""
    global _predictor
    if _predictor is None:
        try:
            from predictor import WaitTimePredictor  # noqa: PLC0415

            _predictor = WaitTimePredictor()
            logger.info("ML predictor loaded successfully")
        except Exception as exc:
            logger.error("Failed to load ML predictor: %s — falling back to placeholder", exc)
            _predictor = None
    return _predictor
