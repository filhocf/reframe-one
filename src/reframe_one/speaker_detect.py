"""Speaker detection via lip movement analysis using MediaPipe FaceLandmarker."""

import os
import subprocess
import tempfile

import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import BaseOptions, vision

# Inner lip landmark indices in MediaPipe Face Mesh (478 landmarks)
INNER_LIP_INDICES = [
    78,
    95,
    88,
    178,
    87,
    14,
    317,
    402,
    318,
    324,
    308,
    415,
    310,
    311,
    312,
    13,
    82,
    81,
    80,
    191,
]

_MODEL_PATH = os.path.expanduser("~/.mediapipe/face_landmarker.task")


def _extract_frames(video_path: str, start: float, end: float, num_frames: int = 8) -> list[str]:
    """Extract evenly-spaced frames from a video segment."""
    duration = end - start
    interval = duration / (num_frames + 1)
    paths = []

    for i in range(1, num_frames + 1):
        ts = start + interval * i
        tmp = tempfile.mktemp(suffix=".jpg")
        subprocess.run(
            ["ffmpeg", "-ss", str(ts), "-i", video_path, "-frames:v", "1", "-q:v", "2", tmp, "-y"],
            capture_output=True,
        )
        if os.path.exists(tmp) and os.path.getsize(tmp) > 0:
            paths.append(tmp)

    return paths


def _get_landmarker():
    """Create FaceLandmarker instance."""
    options = vision.FaceLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=_MODEL_PATH),
        num_faces=4,
        min_face_detection_confidence=0.5,
        min_face_presence_confidence=0.5,
    )
    return vision.FaceLandmarker.create_from_options(options)


def detect_speaker_position(
    video_path: str,
    start: float,
    end: float,
    num_frames: int = 5,
) -> float | None:
    """Detect which face is speaking and return its X position (0.0-1.0).

    Returns normalized X position of the speaking face in the frame,
    or None if detection fails.
    """
    frame_paths = _extract_frames(video_path, start, end, num_frames)
    if len(frame_paths) < 3:
        _cleanup(frame_paths)
        return None

    try:
        landmarker = _get_landmarker()

        # Collect lip positions per frame
        all_frames_lips = []
        for fp in frame_paths:
            image = mp.Image.create_from_file(fp)
            result = landmarker.detect(image)

            if not result.face_landmarks:
                all_frames_lips.append([])
                continue

            frame_lips = []
            for face in result.face_landmarks:
                lips = np.array([[face[i].x, face[i].y] for i in INNER_LIP_INDICES])
                frame_lips.append(lips)
            all_frames_lips.append(frame_lips)

        landmarker.close()

        # Filter frames with faces detected
        valid_frames = [fl for fl in all_frames_lips if fl]
        if len(valid_frames) < 3:
            return None

        # Determine consistent face count
        face_counts = [len(fl) for fl in valid_frames]
        expected_faces = max(set(face_counts), key=face_counts.count)
        valid_frames = [fl for fl in valid_frames if len(fl) == expected_faces]

        if len(valid_frames) < 3 or expected_faces == 0:
            return None

        # Sort faces by X position for consistent ordering across frames
        sorted_frames = []
        for frame_lips in valid_frames:
            sorted_by_x = sorted(frame_lips, key=lambda lips: lips[:, 0].mean())
            sorted_frames.append(sorted_by_x)

        # Calculate lip movement variance for each face
        face_variances = []
        face_x_positions = []

        for face_idx in range(expected_faces):
            openness_values = []
            x_positions = []

            for frame in sorted_frames:
                lips = frame[face_idx]
                # Lip openness = Y distance between upper and lower inner lip
                top_lip_y = lips[:10, 1].mean()
                bottom_lip_y = lips[10:, 1].mean()
                openness = abs(bottom_lip_y - top_lip_y)
                openness_values.append(openness)
                x_positions.append(lips[:, 0].mean())

            variance = np.var(openness_values) if openness_values else 0.0
            face_variances.append(variance)
            face_x_positions.append(np.mean(x_positions))

        # Speaker = face with highest lip variance
        speaker_idx = int(np.argmax(face_variances))
        return face_x_positions[speaker_idx]

    finally:
        _cleanup(frame_paths)


def _cleanup(paths: list[str]):
    for fp in paths:
        if os.path.exists(fp):
            os.unlink(fp)


def x_position_to_pan(face_x: float, frame_width: int = 1920) -> int:
    """Convert normalized face X position to Kdenlive pan X value.

    face_x: 0.0 (left edge) to 1.0 (right edge) in original frame
    Returns: X value for qtblend rect (negative, in 3456x6144 space)
    """
    # Scaled video width = 3456, canvas width = 1080
    # Scale factor = 3456 / 1920 = 1.8
    # Visible portion of original = 1080 / 1.8 = 600px
    scale = 3456 / frame_width  # 1.8
    visible_orig = 1080 / scale  # 600px of original visible

    # Face position in original pixels
    face_pixel = face_x * frame_width

    # Center face in visible window
    pan_orig = face_pixel - visible_orig / 2

    # Clamp: can't pan beyond edges of original frame
    pan_orig = max(0, min(pan_orig, frame_width - visible_orig))

    # Convert to rect X: offset in scaled space, negative
    rect_x = -int(pan_orig * scale)

    return rect_x
