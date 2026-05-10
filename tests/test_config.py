"""Tests for config module."""

import json
import tempfile

from reframe_one.config import DEFAULT_CAMERAS, load_config


def test_default_config():
    config = load_config(None)
    assert config.cameras == DEFAULT_CAMERAS
    assert config.subtitle_style == "karaoke"
    assert config.max_chars == 50


def test_load_config_nonexistent_file():
    config = load_config("/nonexistent/path.json")
    assert config.cameras == DEFAULT_CAMERAS


def test_load_config_json():
    data = {
        "cameras": {"central": [-1000, -2000, 3000, 5000]},
        "subtitle_style": "hormozi",
        "max_chars": 40,
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        f.flush()
        config = load_config(f.name)

    assert config.cameras["central"] == (-1000, -2000, 3000, 5000)
    # Other cameras keep defaults
    assert config.cameras["entrevistadores"] == DEFAULT_CAMERAS["entrevistadores"]
    assert config.subtitle_style == "hormozi"
    assert config.max_chars == 40


def test_load_config_partial():
    """Config with only some fields uses defaults for the rest."""
    data = {"closing": "/custom/closing.mp4"}
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        f.flush()
        config = load_config(f.name)

    assert config.closing == "/custom/closing.mp4"
    assert config.cameras == DEFAULT_CAMERAS
    assert config.subtitle_style == "karaoke"
