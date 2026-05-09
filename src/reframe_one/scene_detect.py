"""Scene detection: identify camera switches in podcast video."""

import json
import os
import subprocess
import tempfile
from dataclasses import dataclass

import cv2
import numpy as np

_PROTOTXT = "/home/claudio/git/podcli/backend/models/deploy.prototxt"
_CAFFEMODEL = "/home/claudio/git/podcli/backend/models/res10_300x300_ssd_iter_140000.caffemodel"
_FACE_NET = None


def _get_face_net():
    global _FACE_NET
    if _FACE_NET is None:
        _FACE_NET = cv2.dnn.readNetFromCaffe(_PROTOTXT, _CAFFEMODEL)
    return _FACE_NET


@dataclass
class SceneChange:
    timestamp: float
    score: float


def detect_scenes(video_path: str, threshold: float = 0.3) -> list[SceneChange]:
    """Detect scene changes using ffmpeg."""
    cmd = [
        "ffmpeg", "-i", video_path,
        "-filter:v", f"select='gt(scene,{threshold})',showinfo",
        "-f", "null", "-"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)

    scenes = []
    for line in result.stderr.split("\n"):
        if "pts_time:" in line:
            parts = line.split("pts_time:")
            if len(parts) > 1:
                ts = float(parts[1].split()[0])
                # Extract scene score
                score_parts = line.split("scene_score=")
                score = float(score_parts[1].split()[0]) if len(score_parts) > 1 else threshold
                scenes.append(SceneChange(timestamp=ts, score=score))

    return scenes


def classify_cameras(video_path: str, scenes: list[SceneChange]) -> list[dict]:
    """Classify each segment between scene changes by camera type.

    Uses face count heuristic:
    - 3+ faces → central (all participants)
    - 2 faces → entrevistadores (interviewers)
    - 1 face → entrevistada (guest)
    - 0 faces → central (fallback)
    """
    net = _get_face_net()
    segments = []

    for i, scene in enumerate(scenes):
        start = scene.timestamp
        end = scenes[i + 1].timestamp if i + 1 < len(scenes) else None
        mid = start + ((end - start) / 2) if end else start + 1.0

        # Extract frame with ffmpeg
        tmp_path = f"/tmp/_reframe_frame_{os.getpid()}_{i}.jpg"
        subprocess.run(
            ["ffmpeg", "-y", "-ss", str(mid), "-i", video_path,
             "-frames:v", "1", "-q:v", "2", tmp_path],
            capture_output=True,
        )

        face_count = 0
        if os.path.exists(tmp_path):
            img = cv2.imread(tmp_path)
            os.remove(tmp_path)
            if img is not None:
                h, w = img.shape[:2]
                blob = cv2.dnn.blobFromImage(img, 1.0, (300, 300), (104.0, 177.0, 123.0))
                net.setInput(blob)
                detections = net.forward()
                for j in range(detections.shape[2]):
                    if detections[0, 0, j, 2] > 0.5:
                        face_count += 1

        if face_count >= 3:
            camera = "central"
        elif face_count == 2:
            camera = "entrevistadores"
        elif face_count == 1:
            camera = "entrevistada"
        else:
            camera = "central"

        segments.append({"start": start, "end": end, "camera": camera, "face_count": face_count})

    return segments


def save_scenes(scenes: list[SceneChange], output_path: str):
    """Save scene changes to JSON."""
    data = [{"timestamp": s.timestamp, "score": s.score} for s in scenes]
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)
