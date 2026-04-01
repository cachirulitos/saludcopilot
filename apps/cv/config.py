import json
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ROOT_ENV = str(Path(__file__).parent.parent.parent / ".env")


class CVSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ROOT_ENV,
        case_sensitive=False,
        extra="ignore",
    )

    api_base_url: str = "http://localhost:8000"
    internal_cv_token: str = "saludcopilot-internal-token-change-in-prod"
    camera_index: int = 0
    capture_interval_seconds: int = 5
    yolo_model_name: str = "yolov8n.pt"
    confidence_threshold: float = 0.4
    target_class_id: int = 0
    camera_to_area_mapping: str = "{}"

    @property
    def area_mapping(self) -> dict:
        """Parse the JSON camera-to-area mapping from the env string."""
        return json.loads(self.camera_to_area_mapping)


settings = CVSettings()
