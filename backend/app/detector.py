"""Motores de detección intercambiables (patrón adaptador del documento: DEMO -> REAL).

  yolo : YOLO (ultralytics). Reconoce 80 clases COCO; con un modelo propio reconoce cascos, chalecos, defectos...
  hog  : HOG de OpenCV. Detecta personas sin descargar ningún modelo (funciona sin internet).
  demo : no analiza video real; devuelve resultados de ejemplo.

Todas las detecciones salen normalizadas (0 a 1): {"c": clase, "p": confianza, "x","y","w","h"}.
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
        small = cv2.resize(frame, (int(w * scale), int(h * scale))) if scale != 1.0 else frame
        sh, sw = small.shape[:2]
        rects, weights = self.hog.detectMultiScale(small, winStride=(8, 8), padding=(8, 8), scale=1.05)
        if len(rects) == 0:
            return []
        boxes = [[int(x), int(y), int(rw), int(rh)] for (x, y, rw, rh) in rects]
        scores = [float(min(0.99, max(0.4, 0.4 + 0.2 * wt))) for wt in np.ravel(weights)]
        keep = np.array(cv2.dnn.NMSBoxes(boxes, scores, 0.3, 0.4)).flatten()
        out = []
        for i in keep:
            x, y, rw, rh = boxes[int(i)]
            out.append({"c": "person", "p": round(scores[int(i)], 3), "x": x / sw, "y": y / sh, "w": rw / sw, "h": rh / sh})
        return out


class YoloDetector(Detector):
    real = True

    def __init__(self, path: str, conf: float):
        from ultralytics import YOLO  # import perezoso: solo si se usa
        self.model = YOLO(path)
        self.conf = conf
        self.name = "YOLO (%s)" % Path(path).stem

    def detect(self, frame):
        r = self.model.predict(frame, conf=self.conf, verbose=False)[0]
        h, w = frame.shape[:2]
        out = []
        for b in r.boxes:
            x1, y1, x2, y2 = b.xyxy[0].tolist()
            out.append({"c": r.names[int(b.cls[0])], "p": round(float(b.conf[0]), 3),
                        "x": x1 / w, "y": y1 / h, "w": (x2 - x1) / w, "h": (y2 - y1) / h})
        return out


_DEMO = {
    "seg": [("person", .96, .12, .2, .2, .68), ("person", .94, .58, .24, .2, .64), ("no_vest", .88, .58, .38, .2, .25)],
    "alm": [("forklift", .90, .6, .38, .28, .42), ("person", .95, .2, .46, .12, .42)],
    "cal": [("producto", .97, .25, .18, .5, .62), ("defecto", .86, .53, .46, .14, .14)],
    "ret": [("person", .95, .1, .4, .1, .46), ("person", .92, .3, .44, .1, .42), ("person", .9, .55, .38, .1, .48)],
}


class DemoDetector(Detector):
    name = "DEMO (resultados simulados)"
    real = False

    def detect(self, frame):
        return []

    def detect_scenario(self, frame, scenario):
        return [{"c": c, "p": p, "x": x, "y": y, "w": w, "h": h} for (c, p, x, y, w, h) in _DEMO.get(scenario, _DEMO["seg"])]


def build_detector(kind: str = "auto", model_path: str = "yolov8n.pt", conf: float = 0.4) -> Detector:
    order = {"auto": ["yolo", "hog"], "yolo": ["yolo"], "hog": ["hog"], "demo": []}.get(kind, ["yolo", "hog"])
    for k in order:
        try:
            d = YoloDetector(model_path, conf) if k == "yolo" else HogDetector()
            log.info("Detector activo: %s", d.name)
            return d
        except Exception as e:  # noqa: BLE001
            log.warning("No se pudo iniciar '%s': %s", k, e)
    log.info("Detector activo: DEMO")
    return DemoDetector()
