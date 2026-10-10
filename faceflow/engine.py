"""Local-only face detection/recognition and photographic diagnostics.

Pre-trained model accuracy varies with pose, lighting and demographics. None of the
appearance outputs represents gender identity, attractiveness, or a verified age.
"""
from __future__ import annotations

import math
import threading
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
MODELS = ROOT / "models"
AGE_BUCKETS = ["0–2", "4–6", "8–12", "15–20", "25–32", "38–43", "48–53", "60+"]
MEAN = (78.4263377603, 87.7689143744, 114.895847746)


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(x)))


def photo_metrics(face: np.ndarray, frame_w: int, frame_h: int, rect: tuple[int, int, int, int]):
    """Rate photo capture quality, NOT the person's beauty or worth."""
    x, y, w, h = rect
    gray = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY)
    luminance = float(gray.mean())
    contrast = float(gray.std())
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    brightness_score = clamp(100 - abs(luminance - 130) * 0.8, 0, 100)
    contrast_score = clamp(contrast / 55 * 100, 0, 100)
    sharpness_score = clamp((math.log1p(sharpness) - math.log1p(12)) / (math.log1p(300) - math.log1p(12)) * 100, 0, 100)
    cx, cy = x + w / 2, y + h / 2
    offset = math.hypot((cx / frame_w - 0.5), (cy / frame_h - 0.5))
    position_score = clamp(100 - offset * 105, 0, 100)
    size_score = clamp(min(w / frame_w, h / frame_h) * 450, 0, 100)
    total = (0.27 * brightness_score + 0.25 * sharpness_score + 0.22 * contrast_score
             + 0.16 * position_score + 0.10 * size_score)
    tips = []
    if luminance < 85: tips.append("Try brighter, even front lighting.")
    if luminance > 205: tips.append("Reduce strong light or exposure.")
    if sharpness < 55: tips.append("Hold the camera steady and focus on the face.")
    if contrast < 28: tips.append("Use more even lighting with a clearer background.")
    if offset > 0.24: tips.append("Move the face closer to the center.")
    if min(w, h) < 95: tips.append("Move closer for a larger, clearer face.")
    if not tips: tips = ["Good framing. This is a technical photo score, not a beauty judgment."]
    return {
        "photo_aesthetics_score": int(round(total)),
        "brightness": round(luminance, 1),
        "contrast": round(contrast, 1),
        "sharpness": round(sharpness, 1),
        "framing_score": int(round(position_score)),
        "capture_tips": tips[:3],
    }


class FaceEngine:
    def __init__(self, model_dir: Path = MODELS):
        self.model_dir = Path(model_dir)
        self.lock = threading.RLock()
        self.detector = None
        self.recognizer = None
        self.age_net = None
        self.presentation_net = None
        haar = Path(cv2.data.haarcascades)
        self.haar = cv2.CascadeClassifier(str(haar / "haarcascade_frontalface_default.xml"))
        self.eyes = cv2.CascadeClassifier(str(haar / "haarcascade_eye.xml"))
        self.smile = cv2.CascadeClassifier(str(haar / "haarcascade_smile.xml"))
        self.load_models()

    def load_models(self):
        with self.lock:
            self.detector = None
            self.recognizer = None
            self.age_net = None
            self.presentation_net = None
            yunet = self.model_dir / "face_detection_yunet_2023mar.onnx"
            sface = self.model_dir / "face_recognition_sface_2021dec.onnx"
            age_model = self.model_dir / "age_net.caffemodel"
            age_proto = self.model_dir / "age_deploy.prototxt"
            pres_model = self.model_dir / "gender_net.caffemodel"
            pres_proto = self.model_dir / "gender_deploy.prototxt"
            if yunet.is_file() and yunet.stat().st_size > 100_000:
                try:
                    self.detector = cv2.FaceDetectorYN.create(str(yunet), "", (320, 320), 0.68, 0.3, 5000)
                except cv2.error:
                    self.detector = None
            if self.detector is not None and sface.is_file() and sface.stat().st_size > 1_000_000:
                try:
                    self.recognizer = cv2.FaceRecognizerSF.create(str(sface), "")
                except cv2.error:
                    self.recognizer = None
            if age_model.is_file() and age_proto.is_file() and age_model.stat().st_size > 1_000_000:
                try:
                    self.age_net = cv2.dnn.readNet(str(age_model), str(age_proto))
                except cv2.error:
                    self.age_net = None
            if pres_model.is_file() and pres_proto.is_file() and pres_model.stat().st_size > 1_000_000:
                try:
                    self.presentation_net = cv2.dnn.readNet(str(pres_model), str(pres_proto))
                except cv2.error:
                    self.presentation_net = None

    def status(self):
        return {
            "face_detection": "YuNet AI" if self.detector is not None else "OpenCV basic fallback",
            "face_recognition": self.recognizer is not None,
            "age_estimation": self.age_net is not None,
            "appearance_estimation": self.presentation_net is not None,
            "local_only": True,
        }

    def _detect(self, img: np.ndarray):
        h, w = img.shape[:2]
        if self.detector is not None:
            try:
                self.detector.setInputSize((w, h))
                _ok, faces = self.detector.detect(img)
                if faces is None:
                    return []
                return [np.asarray(row, dtype=np.float32) for row in faces]
            except cv2.error:
                # A corrupt/incompatible model should not break basic photo analysis.
                pass
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        boxes = self.haar.detectMultiScale(gray, scaleFactor=1.12, minNeighbors=5, minSize=(48, 48))
        return [np.array([float(x), float(y), float(bw), float(bh), 0.6], dtype=np.float32)
                for x, y, bw, bh in boxes]

    def _feature(self, img: np.ndarray, raw_face: np.ndarray):
        if self.recognizer is None or len(raw_face) < 15:
            return None
        try:
            aligned = self.recognizer.alignCrop(img, raw_face)
            feat = self.recognizer.feature(aligned).reshape(-1).astype(np.float32)
            length = float(np.linalg.norm(feat))
            if length < 1e-8 or not np.all(np.isfinite(feat)):
                return None
            return (feat / length).tolist()
        except cv2.error:
            return None

    def analyze(self, img: np.ndarray, *, want_age: bool = True, want_appearance: bool = False,
                fast: bool = False, want_features: bool = True):
        with self.lock:
            height, width = img.shape[:2]
            raw = self._detect(img)
            raw = sorted(raw, key=lambda f: float(f[2] * f[3]), reverse=True)[:(8 if fast else 20)]
            items = []
            for idx, obj in enumerate(raw):
                x0, y0, bw, bh = (int(round(v)) for v in obj[:4])
                x, y = max(0, x0), max(0, y0)
                right, bottom = min(width, x0 + bw), min(height, y0 + bh)
                if right - x < 24 or bottom - y < 24:
                    continue
                crop = img[y:bottom, x:right]
                mx = photo_metrics(crop, width, height, (x, y, right-x, bottom-y))
                # Skip slower Haar eye/smile heuristics during live streaming.
                # These unreliable diagnostics are not needed to draw live boxes.
                eyes_seen = smile_seen = None
                if not fast:
                    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
                    eyeregion = gray[:max(1, len(gray)//2), :]
                    eye_boxes = self.eyes.detectMultiScale(eyeregion, 1.1, 6, minSize=(12,12))
                    smile_boxes = self.smile.detectMultiScale(gray, 1.7, 30, minSize=(20, 12))
                    eyes_seen = min(2, len(eye_boxes))
                    smile_seen = bool(len(smile_boxes))
                age = None
                appearance = None
                if (want_age and self.age_net is not None) or (want_appearance and self.presentation_net is not None):
                    pad = int(0.13 * max(bw, bh))
                    focus = img[max(0,y-pad):min(height,bottom+pad), max(0,x-pad):min(width,right+pad)]
                    blob = cv2.dnn.blobFromImage(focus, 1.0, (227,227), MEAN, swapRB=False)
                    if want_age and self.age_net is not None:
                        self.age_net.setInput(blob)
                        pred = self.age_net.forward().reshape(-1)
                        age = {"range": AGE_BUCKETS[int(np.argmax(pred))], "confidence": round(float(np.max(pred)), 3)}
                    if want_appearance and self.presentation_net is not None:
                        self.presentation_net.setInput(blob)
                        pred = self.presentation_net.forward().reshape(-1)
                        appearance = {"label": ["Male-appearing", "Female-appearing"][int(np.argmax(pred))],
                                      "confidence": round(float(np.max(pred)), 3)}
                tilt = None
                landmarks = []
                if len(obj) >= 15:
                    for a in range(4,14,2):
                        landmarks.append([round(float(obj[a]), 1), round(float(obj[a+1]), 1)])
                    eye_a, eye_b = landmarks[0], landmarks[1]
                    tilt = round(math.degrees(math.atan2(eye_b[1]-eye_a[1], eye_b[0]-eye_a[0])), 1)
                items.append({
                    "index": idx + 1,
                    "bbox": [x, y, right-x, bottom-y],
                    "detector_score": round(float(obj[-1]), 3) if len(obj) >= 15 else None,
                    "landmarks": landmarks,
                    "head_tilt_degrees": tilt,
                    "eyes_visible_estimate": eyes_seen,
                    "smile_pattern_detected": smile_seen,
                    "age_estimate": age,
                    "appearance_estimate": appearance,
                    "feature": self._feature(img, obj) if want_features else None,
                    **mx,
                })
            return {"width": width, "height": height, "face_count": len(items), "faces": items}
