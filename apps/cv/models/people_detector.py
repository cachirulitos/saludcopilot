from dataclasses import dataclass, field
import numpy as np
import cv2

PERSON_CLASS_ID = 0
THRESHOLD_WARNING = 4
THRESHOLD_SATURATED = 8

# BGR colors
COLOR_NORMAL = (80, 200, 80)
COLOR_WARNING = (0, 165, 255)
COLOR_SATURATED = (0, 0, 220)
COLOR_OUTSIDE_ROI = (100, 100, 100)

# ── Parámetros de detección recomendados para cámaras de seguridad ──────────
DEFAULT_CONF      = 0.25   # ↓ Más bajo para no perder personas lejanas/pequeñas
DEFAULT_IOU       = 0.45   # Controla fusión de cajas solapadas (personas juntas)
DEFAULT_IMGSZ     = 1280   # ↑ Mayor resolución → detecta personas pequeñas
DEFAULT_AUGMENT   = True   # Test-time augmentation: mejora detección a costa de fps
# ────────────────────────────────────────────────────────────────────────────


def classify_status(count: int) -> str:
    if count >= THRESHOLD_SATURATED:
        return "saturated"
    if count >= THRESHOLD_WARNING:
        return "warning"
    return "normal"


def status_color(status: str) -> tuple[int, int, int]:
    return {"normal": COLOR_NORMAL, "warning": COLOR_WARNING,
            "saturated": COLOR_SATURATED}.get(status, COLOR_NORMAL)


def point_in_roi(cx: float, cy: float, roi: tuple[int, int, int, int]) -> bool:
    x1, y1, x2, y2 = roi
    return x1 <= cx <= x2 and y1 <= cy <= y2


def enhance_frame(frame: np.ndarray) -> np.ndarray:
    """
    Mejora de contraste con CLAHE en canal L (LAB).
    Ayuda mucho en cámaras oscuras o con IR.
    """
    lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l = clahe.apply(l)
    enhanced = cv2.merge((l, a, b))
    return cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)


@dataclass
class DetectionFrame:
    count: int
    status: str
    color: tuple[int, int, int]
    tracks_in_roi: list = field(default_factory=list)
    tracks_outside_roi: list = field(default_factory=list)


class PeopleDetector:
    """
    Detecta y rastrea personas con YOLOv8 + ByteTrack,
    optimizado para grabaciones de cámaras de seguridad.

    Mejoras respecto a la versión original:
    - Preprocesado CLAHE para mejorar contraste en escenas oscuras
    - imgsz=1280 para detectar personas pequeñas/lejanas
    - conf=0.25 para no perder detecciones en cámaras cenitales
    - iou=0.45 para separar personas que se solapan
    - augment=True para test-time augmentation
    - Soporte de modelos alternativos recomendados para vigilancia
    """

    # Modelos recomendados en orden de precisión vs velocidad:
    # - "yolov8x.pt"          → máxima precisión, más lento
    # - "yolov8l.pt"          → buen balance (recomendado para producción)
    # - "yolov8m.pt"          → balance intermedio
    # - "yolov8s.pt"          → rápido, menor precisión
    # - "yolov8n.pt"          → muy rápido, precisión limitada en cámaras lejanas
    # Para ángulos cenitales considera modelos especializados:
    # - "yolov8x-worldv2.pt"  → mejor generalización
    # - Modelos fine-tuned en datasets de vigilancia (VisDrone, CCTV, etc.)

    def __init__(
        self,
        model_name: str = "yolov8l.pt",
        confidence_threshold: float = DEFAULT_CONF,
        iou_threshold: float = DEFAULT_IOU,
        imgsz: int = DEFAULT_IMGSZ,
        augment: bool = DEFAULT_AUGMENT,
        enhance: bool = True,
    ) -> None:
        from ultralytics import YOLO
        import torch

        original_load = torch.load

        def custom_load(*args, **kwargs):
            kwargs["weights_only"] = False
            return original_load(*args, **kwargs)

        torch.load = custom_load
        try:
            self.model = YOLO(model_name)
        finally:
            torch.load = original_load

        self.confidence_threshold = confidence_threshold
        self.iou_threshold = iou_threshold
        self.imgsz = imgsz
        self.augment = augment
        self.enhance = enhance

    def detect(
        self,
        frame: np.ndarray,
        roi: tuple[int, int, int, int] | None = None,
    ) -> DetectionFrame:
        # 1. Preprocesado: mejora contraste para cámaras oscuras/IR
        processed = enhance_frame(frame) if self.enhance else frame

        # 2. Inferencia con parámetros optimizados para vigilancia
        results = self.model.track(
            processed,
            persist=True,
            classes=[PERSON_CLASS_ID],
            tracker="bytetrack.yaml",
            conf=self.confidence_threshold,   # ← antes no se pasaba explícitamente
            iou=self.iou_threshold,           # ← nuevo: controla NMS
            imgsz=self.imgsz,                 # ← nuevo: mayor resolución de inferencia
            augment=self.augment,             # ← nuevo: test-time augmentation
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