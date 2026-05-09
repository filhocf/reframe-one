"""Scene detection: identify camera switches in podcast video."""

import json
import subprocess
from dataclasses import dataclass


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
    """
    # TODO: implement face counting per segment
    # For now, return segments with timestamps only
    segments = []
    for i, scene in enumerate(scenes):
        end = scenes[i + 1].timestamp if i + 1 < len(scenes) else None
        segments.append({
            "start": scene.timestamp,
            "end": end,
            "camera": "unknown",
        })
    return segments


def save_scenes(scenes: list[SceneChange], output_path: str):
    """Save scene changes to JSON."""
    data = [{"timestamp": s.timestamp, "score": s.score} for s in scenes]
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)
