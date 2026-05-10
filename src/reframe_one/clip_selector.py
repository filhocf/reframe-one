"""Clip selection — choose which segments become shorts."""

import json
import re

from reframe_one.llm import LLMConfig, llm_chat

SCORING_PROMPT = """\
You score podcast segments for short-form video potential (TikTok/Instagram Reels).

Score each segment 1-10 based on:
- Emotional impact (stories, revelations, strong opinions)
- Standalone clarity (makes sense without context)
- Hook potential (grabs attention in first 3 seconds)
- Shareability (people would share this clip)

Return ONLY a JSON object: {"scores": [{"index": 0, "score": 7, "reason": "..."}, ...]}
Only include segments scoring >= 6."""


def select_by_time_ranges(
    segments: list[dict], time_ranges: list[tuple[float, float]]
) -> list[dict]:
    """Filter segments that overlap with given time ranges.

    Args:
        segments: list of {start: float, end: float, ...}
        time_ranges: list of (start_seconds, end_seconds)
    """
    selected = []
    for seg in segments:
        for t_start, t_end in time_ranges:
            if seg["start"] < t_end and seg["end"] > t_start:
                selected.append(seg)
                break
    return selected


def parse_time_ranges(spec: str) -> list[tuple[float, float]]:
    """Parse time range spec like '0:30-1:45,3:00-4:20' or '1:02:30-1:05:00'."""
    ranges = []
    for part in spec.split(","):
        part = part.strip()
        # Match H:MM:SS, M:SS, or just seconds
        times = part.split("-")
        if len(times) == 2:
            start = _parse_time_value(times[0].strip())
            end = _parse_time_value(times[1].strip())
            if start is not None and end is not None:
                ranges.append((start, end))
    return ranges


def select_by_llm(
    segments: list[dict],
    transcript_segments: list[dict],
    config: LLMConfig,
    threshold: int = 6,
) -> list[dict]:
    """Use LLM to score segments and return those above threshold.

    Args:
        segments: list of {start, end} (timeline segments)
        transcript_segments: Whisper segments with text
        config: LLM configuration
        threshold: minimum score to include (1-10)
    """
    # Build text summary per segment
    seg_texts = []
    for i, seg in enumerate(segments):
        # Find transcript text overlapping this segment
        text = _get_text_for_range(transcript_segments, seg["start"], seg["end"])
        seg_texts.append(f"[{i}] ({seg['start']:.1f}s-{seg['end']:.1f}s): {text[:500]}")

    user_msg = "\n".join(seg_texts)
    response = llm_chat(config, SCORING_PROMPT, user_msg)

    if not response:
        return segments  # fallback: keep all

    try:
        data = json.loads(response)
        scored = {s["index"]: s["score"] for s in data.get("scores", [])}
        return [seg for i, seg in enumerate(segments) if scored.get(i, 0) >= threshold]
    except (json.JSONDecodeError, KeyError, TypeError):
        return segments  # fallback: keep all


def load_clips_file(path: str) -> list[tuple[float, float]]:
    """Load clip selections from JSON file.

    Expected format: [{"start": 30.0, "end": 105.0}, ...]
    or: [{"start": "0:30", "end": "1:45"}, ...]
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    ranges = []
    for item in data:
        start = _parse_time_value(item["start"])
        end = _parse_time_value(item["end"])
        ranges.append((start, end))
    return ranges


def _parse_time_value(val) -> float | None:
    """Parse time value — float seconds, 'M:SS', or 'H:MM:SS' string."""
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    # H:MM:SS or HH:MM:SS
    match = re.match(r"(\d+):(\d+):(\d+(?:\.\d+)?)", s)
    if match:
        return int(match.group(1)) * 3600 + int(match.group(2)) * 60 + float(match.group(3))
    # M:SS
    match = re.match(r"(\d+):(\d+(?:\.\d+)?)", s)
    if match:
        return int(match.group(1)) * 60 + float(match.group(2))
    # Plain seconds
    try:
        return float(s)
    except ValueError:
        return None


def _get_text_for_range(transcript_segments: list[dict], start: float, end: float) -> str:
    """Get transcript text overlapping a time range."""
    texts = []
    for seg in transcript_segments:
        if seg["start"] < end and seg["end"] > start:
            texts.append(seg.get("text", "").strip())
    return " ".join(texts)
