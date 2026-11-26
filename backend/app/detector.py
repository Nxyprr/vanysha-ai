
"""Motores de detección intercambiables para Vanysha AI.

  yolo : detector especializado en cascos, chalecos y personas.
  hog  : detector OpenCV para personas.
  demo : resultados simulados, no analiza video real.

Todas las detecciones usan coordenadas normalizadas (0 a 1).
"""

import logging
from pathlib import Path
from typing import List

import cv2
import numpy as np

log = logging.getLogger("vanysha.detector")


class Detector:
    name = "base"
    real = False

    def detect(self, frame: np.ndarray) -> List[dict]:
        raise NotImplementedError

    def detect_scenario(self, frame: np.ndarray, scenario: str) -> List[dict]:
        return self.detect(frame)


class HogDetector(Detector):
    name = "OpenCV HOG (personas)"
    real = True

    def __init__(self):
        self.hog = cv2.HOGDescriptor()
        self.hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

    def detect(self, frame):
        h, w = frame.shape[:2]
        scale = 480.0 / w if w > 480 else 1.0
        small = cv2.resize(
            frame, (int(w * scale), int(h * scale))
        ) if scale != 1.0 else frame

        sh, sw = small.shape[:2]
        rects, weights = self.hog.detectMultiScale(
            small,
            winStride=(8, 8),
            padding=(8, 8),
            scale=1.05,
        )

        if len(rects) == 0:
            return []

        boxes = [
            [int(x), int(y), int(rw), int(rh)]
            for (x, y, rw, rh) in rects
        ]
        scores = [
            float(min(0.99, max(0.4, 0.4 + 0.2 * wt)))
            for wt in np.ravel(weights)
        ]

        keep = np.array(
            cv2.dnn.NMSBoxes(boxes, scores, 0.3, 0.4)
        ).flatten()

        out = []
        for i in keep:
            x, y, rw, rh = boxes[int(i)]
            out.append({
                "c": "person",
                "p": round(scores[int(i)], 3),
                "x": x / sw,
                "y": y / sh,
                "w": rw / sw,
                "h": rh / sh,
            })

        return out


class YoloDetector(Detector):
    real = True

    def __init__(self, path: str, conf: float):
        from ultralytics import YOLO

        model_path = Path(path)
        if not model_path.is_absolute():
            model_path = Path(__file__).resolve().parents[1] / model_path

        if not model_path.is_file():
            raise FileNotFoundError(
                f"No se encontró el modelo YOLO: {model_path}"
            )

        self.model = YOLO(str(model_path))
        self.conf = conf
        self.name = f"YOLO EPP ({model_path.stem})"

        log.info("Modelo YOLO cargado. Clases: %s", self.model.names)

    def detect(self, frame):
        results = self.model.predict(
            source=frame,
            conf=self.conf,
            verbose=False,
            device="cpu",
            imgsz=416,
            max_det=50,
        )

        result = results[0]
        h, w = frame.shape[:2]
        out = []

        # Normaliza los nombres del modelo de EPP para que las reglas
        # y la interfaz reciban siempre las mismas clases.
        class_map = {
            "person": "person",
            "persona": "person",
            "hat": "helmet",
            "hardhat": "helmet",
            "helmet": "helmet",
            "safety_helmet": "helmet",
            "nohat": "no_helmet",
            "no_hat": "no_helmet",
            "nohelmet": "no_helmet",
            "no_helmet": "no_helmet",
            "no_hardhat": "no_helmet",
            "novest": "no_vest",
            "no_vest": "no_vest",
            "no_safety_vest": "no_vest",
            "vest": "vest",
            "safety_vest": "vest",
        }

        for box in result.boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            class_id = int(box.cls[0])
            class_name = str(result.names[class_id]).strip().lower()
            class_name = class_name.replace("-", "_").replace(" ", "_")
            class_name = class_map.get(class_name, class_name)

            out.append({
                "c": class_name,
                "p": round(float(box.conf[0]), 3),
                "x": max(0.0, x1 / w),
                "y": max(0.0, y1 / h),
                "w": min(1.0, (x2 - x1) / w),
                "h": min(1.0, (y2 - y1) / h),
            })

        return out


_DEMO = {
    "seg": [
        ("person", .96, .12, .2, .2, .68),
        ("person", .94, .58, .24, .2, .64),
        ("no_vest", .88, .58, .38, .2, .25),
    ],
    "alm": [
        ("forklift", .90, .6, .38, .28, .42),
        ("person", .95, .2, .46, .12, .42),
    ],
    "cal": [
        ("producto", .97, .25, .18, .5, .62),
        ("defecto", .86, .53, .46, .14, .14),
    ],
    "ret": [
        ("person", .95, .1, .4, .1, .46),
        ("person", .92, .3, .44, .1, .42),
        ("person", .9, .55, .38, .1, .48),
    ],
}


class DemoDetector(Detector):
    name = "DEMO (resultados simulados)"
    real = False

    def detect(self, frame):
        return []

    def detect_scenario(self, frame, scenario):
        return [
            {
                "c": c,
                "p": p,
                "x": x,
                "y": y,
                "w": w,
                "h": h,
            }
            for c, p, x, y, w, h
            in _DEMO.get(scenario, _DEMO["seg"])
        ]


def build_detector(
    kind: str = "auto",
    model_path: str = "models/yolo11n_safety.pt",
    conf: float = 0.4,
) -> Detector:

    order = {
        "auto": ["yolo", "hog"],
        "yolo": ["yolo"],
        "hog": ["hog"],
        "demo": [],
    }.get(kind, ["yolo", "hog"])

    for detector_type in order:
        try:
            detector = (
                YoloDetector(model_path, conf)
                if detector_type == "yolo"
                else HogDetector()
            )

            log.info("Detector activo: %s", detector.name)
            return detector

        except Exception as error:
            log.warning(
                "No se pudo iniciar '%s': %s",
                detector_type,
                error,
            )

    log.info("Detector activo: DEMO")
    return DemoDetector()
