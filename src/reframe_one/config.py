"""Per-episode configuration for reframe-one."""

import json
import os
from dataclasses import dataclass, field

# Default camera positions (Papo Saúde studio)
DEFAULT_CAMERAS = {
    "central": (-1200, -2112, 3456, 6144),
    "entrevistadores": (-1400, -2112, 3456, 6144),
    "entrevistada": (-1900, -2112, 3456, 6144),
    "unknown": (-1400, -2112, 3456, 6144),
}

DEFAULT_CLOSING = "/home/claudio/Insync/ssd/papo-saude/00 Comum/fechamento papo podcast Insta.mp4"


@dataclass
class EpisodeConfig:
    """Configuration for a single episode."""

    cameras: dict[str, tuple[int, int, int, int]] = field(
        default_factory=lambda: dict(DEFAULT_CAMERAS)
    )
    closing: str = DEFAULT_CLOSING
    subtitle_style: str = "karaoke"
    scene_threshold: float = 0.3
    max_chars: int = 50


def load_config(path: str | None) -> EpisodeConfig:
    """Load episode config from JSON or YAML file. Returns defaults if path is None."""
    if not path:
        return EpisodeConfig()

    if not os.path.exists(path):
        return EpisodeConfig()

    with open(path, encoding="utf-8") as f:
        if path.endswith((".yaml", ".yml")):
            try:
                import yaml

                data = yaml.safe_load(f)
            except ImportError:
                # YAML not installed, try as JSON
                data = json.load(f)
        else:
            data = json.load(f)

    return _parse_config(data)


def _parse_config(data: dict) -> EpisodeConfig:
    """Parse config dict into EpisodeConfig."""
    if not data:
        return EpisodeConfig()

    config = EpisodeConfig()

    if "cameras" in data:
        for name, pos in data["cameras"].items():
            config.cameras[name] = tuple(pos)

    if "closing" in data:
        config.closing = data["closing"]

    if "subtitle_style" in data:
        config.subtitle_style = data["subtitle_style"]

    if "scene_threshold" in data:
        config.scene_threshold = float(data["scene_threshold"])

    if "max_chars" in data:
        config.max_chars = int(data["max_chars"])

    return config
