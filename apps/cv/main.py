import argparse
import asyncio
import sys
import threading
import time

import cv2
import numpy as np

from config import settings
from models.people_detector import PeopleDetector
from services.count_publisher import publish_people_count

DEMO_PEOPLE_PATTERN = [3, 3, 3, 4, 4, 4, 5, 5, 5, 6, 6, 6, 7, 7, 7, 8, 8, 8, 2, 2, 2]
DEMO_FRAME_HEIGHT = 480
DEMO_FRAME_WIDTH = 640
DEMO_TEXT_POSITION = (50, 240)
DEMO_FONT_SCALE = 0.8
DEMO_FONT_COLOR = (255, 255, 255)
DEMO_FONT_THICKNESS = 2
WINDOW_TITLE = "SaludCopilot - Sala de espera"
WINDOW_REFRESH_MS = 33  # ~30 fps for responsive UI


def _build_demo_frame(people_count: int) -> np.ndarray:
    """Create a black frame with the simulated people count overlaid."""
    frame = np.zeros((DEMO_FRAME_HEIGHT, DEMO_FRAME_WIDTH, 3), dtype=np.uint8)
    cv2.putText(
        frame,
        f"DEMO MODE - {people_count} personas detectadas",
        DEMO_TEXT_POSITION,
        cv2.FONT_HERSHEY_SIMPLEX,
        DEMO_FONT_SCALE,
        DEMO_FONT_COLOR,
        DEMO_FONT_THICKNESS,
    )
    return frame


def _open_camera() -> cv2.VideoCapture:
    """Open the configured camera or exit with an error message."""
    capture = cv2.VideoCapture(settings.camera_index)
    if not capture.isOpened():
        print(
            f"Error: no se pudo abrir la camara (indice {settings.camera_index}). "
            f"Verifica que este conectada."
        )
        sys.exit(1)
    return capture


def _open_video(video_path: str) -> cv2.VideoCapture:
    """Open a video file as the frame source, or exit with an error message."""
    capture = cv2.VideoCapture(video_path)
    if not capture.isOpened():
        print(f"Error: no se pudo abrir el video '{video_path}'.")
        sys.exit(1)
    return capture


def _publish_in_background(area_id: str, people_count: int) -> None:
    """Run the async publish call in a separate event loop on a background thread."""
    try:
        asyncio.run(publish_people_count(area_id, people_count))
    except Exception as exc:
        print(f"Error publicando conteo: {exc}")


def run_loop(
    demo_mode: bool = False,
    show_window: bool = True,
    video_path: str = "",
) -> None:
    """Main capture loop: read frames, count people, publish to API.

    Runs synchronously so OpenCV window events are processed correctly.
    HTTP publishing runs in background threads to avoid blocking the UI.

    Args:
        demo_mode: Use simulated people counts instead of a real video source.
        show_window: Display a preview window with annotated detections.
        video_path: Path to a video file to use as frame source. When empty,
            the configured camera index is used. Ignored in demo_mode.
    """
    area_mapping = settings.area_mapping
    if not area_mapping:
        print(
            "ERROR: CAMERA_TO_AREA_MAPPING esta vacio. "
            "Configura el .env con los UUIDs de las areas."
        )
        sys.exit(1)

    detector = PeopleDetector(settings.yolo_model_name, settings.confidence_threshold)
    capture = None
    demo_index = 0

    if not demo_mode:
        if video_path:
            capture = _open_video(video_path)
            mode_label = f"VIDEO: {video_path}"
        else:
            capture = _open_camera()
            mode_label = "CAMARA REAL"
    else:
        mode_label = "DEMO"

    print(f"SaludCopilot CV Worker iniciado. Modo: {mode_label}")
    if show_window:
        print("Presiona 'q' en la ventana para salir.")

    last_publish_time = 0.0
    publish_interval = settings.capture_interval_seconds

    try:
        while True:
            # --- Capture / detect ---
            if demo_mode:
                people_count = DEMO_PEOPLE_PATTERN[demo_index % len(DEMO_PEOPLE_PATTERN)]
                demo_index += 1
                frame = _build_demo_frame(people_count)
            else:
                frame_captured, raw_frame = capture.read()
                if not frame_captured:
                    if video_path:
                        # Loop video back to the beginning
                        capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        continue
                    print("Advertencia: frame no capturado, reintentando...")
                    time.sleep(0.1)
                    continue
                people_count, frame = detector.count_people_with_annotated_frame(raw_frame)

            # --- Publish at configured interval ---
            now = time.monotonic()
            if now - last_publish_time >= publish_interval:
                last_publish_time = now
                for _camera_index, area_id in area_mapping.items():
                    thread = threading.Thread(
                        target=_publish_in_background,
                        args=(area_id, people_count),
                        daemon=True,
                    )
                    thread.start()

            # --- Display ---
            if show_window:
                cv2.namedWindow(WINDOW_TITLE, cv2.WINDOW_NORMAL)
                cv2.imshow(WINDOW_TITLE, frame)
                key = cv2.waitKey(WINDOW_REFRESH_MS) & 0xFF
                if key == ord("q"):
                    break
            else:
                time.sleep(publish_interval)

    except KeyboardInterrupt:
        print("\nCV Worker detenido.")
    finally:
        if capture:
            capture.release()
        if show_window:
            cv2.destroyAllWindows()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SaludCopilot CV Worker")
    parser.add_argument(
        "--demo", action="store_true",
        help="Usar datos simulados en lugar de camara",
    )
    parser.add_argument(
        "--no-window", action="store_true",
        help="No mostrar ventana de preview (util en Wayland/headless)",
    )
    parser.add_argument(
        "--video", metavar="PATH", default="",
        help="Ruta a un archivo de video (mp4, avi, etc.) como fuente de frames. "
             "Si no se indica, usa la camara configurada en CAMERA_INDEX.",
    )
    args = parser.parse_args()
    run_loop(demo_mode=args.demo, show_window=not args.no_window, video_path=args.video)
