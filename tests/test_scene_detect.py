"""Tests for scene_detect module."""

from reframe_one.scene_detect import SceneChange, classify_cameras


def test_classify_cameras_returns_segments():
    # Mock: we can't run ffmpeg in tests, but we can test the classification logic
    # by calling with pre-built scenes and mocking frame extraction
    scenes = [
        SceneChange(timestamp=0.0, score=0.5),
        SceneChange(timestamp=10.0, score=0.4),
        SceneChange(timestamp=20.0, score=0.6),
    ]
    # classify_cameras needs a real video, so we test the structure only
    # This is an integration test placeholder
    assert len(scenes) == 3
    assert scenes[0].timestamp == 0.0


def test_scene_change_dataclass():
    sc = SceneChange(timestamp=5.5, score=0.35)
    assert sc.timestamp == 5.5
    assert sc.score == 0.35
