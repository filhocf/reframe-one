"""Parse PDF cut suggestions and use LLM to define exact clip boundaries."""

import json
import re
import subprocess

from reframe_one.llm import LLMConfig, llm_chat

BOUNDARY_PROMPT = """\
You define exact start/end times for podcast video clips.

Given:
- A suggested start time and title for each clip
- The transcript text around that time (with timestamps)
- Target duration: 1-3 minutes per clip

Rules:
1. Start: find the beginning of the sentence closest to the suggested time
2. End: find a natural ending point (complete sentence, pause, topic change)
3. Duration must be 60-180 seconds
4. Never cut mid-sentence

Return JSON: {"clips": [{"start": 130.5, "end": 235.2, "title": "..."}]}"""


def parse_pdf(pdf_path: str) -> str:
    """Extract text from PDF using pdftotext."""
    result = subprocess.run(
        ["pdftotext", "-layout", pdf_path, "-"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"pdftotext failed: {result.stderr}")
    return result.stdout


def extract_episode_cuts(pdf_text: str, episode_name: str) -> list[dict]:
    """Extract cut timestamps and titles for a specific episode from PDF text.

    Returns list of {"time_s": float, "title": str}
    """
    # Find the section for this episode (case-insensitive partial match)
    # Skip table of contents — find the section that has actual cut lines after it
    lines = pdf_text.replace("\x0c", "\n").split("\n")
    cuts = []

    # Find all positions where episode name appears
    header_positions = [
        i for i, line in enumerate(lines) if episode_name.lower() in line.strip().lower()
    ]

    for header_idx in header_positions:
        # Check if lines after this header contain cut timestamps
        section_cuts = []
        for j in range(header_idx + 1, min(header_idx + 50, len(lines))):
            stripped = lines[j].strip()
            if not stripped:
                continue
            # Stop at next section
            if ("–" in stripped or " - " in stripped) and len(stripped) > 15:
                if not stripped[0].isdigit():
                    break
            # Try to parse as cut line
            match = re.match(
                r"(\d{1,2}):(\d{2}(?:\.\d+)?)\s*:?\s*(?:Corte\s*\d+\s*[—–-]\s*)?(.*)",
                stripped,
            )
            if match:
                minutes = int(match.group(1))
                seconds = float(match.group(2))
                title = match.group(3).strip().strip('"').strip("'")
                time_s = minutes * 60 + seconds
                if title:
                    section_cuts.append({"time_s": time_s, "title": title})

        # Use this section if it has cuts
        if section_cuts:
            cuts = section_cuts
            break

    return cuts


def define_boundaries_with_llm(
    cuts: list[dict],
    transcript_segments: list[dict],
    offset_s: float,
    config: LLMConfig | None = None,
) -> list[dict]:
    """Use LLM to find exact start/end for each cut.

    Args:
        cuts: list of {"time_s": float, "title": str} from PDF
        transcript_segments: Whisper segments with text + timestamps
        offset_s: source project in-point (added to PDF times)
        config: LLM config (None = use heuristic fallback)

    Returns: list of {"start": float, "end": float, "title": str}
    """
    if config is None:
        return _heuristic_boundaries(cuts, transcript_segments, offset_s)

    # Build context for LLM: transcript around each cut point
    context_parts = []
    for i, cut in enumerate(cuts):
        raw_time = cut["time_s"] + offset_s
        # Get transcript ±30s around the cut point
        nearby = [
            f"  [{s['start']:.1f}-{s['end']:.1f}] {s['text'].strip()}"
            for s in transcript_segments
            if abs(s["start"] - raw_time) < 30 or abs(s["end"] - raw_time) < 30
        ]
        context_parts.append(
            f'Cut {i + 1}: suggested_start={raw_time:.1f}s, title="{cut["title"]}"\n'
            + "\n".join(nearby[:10])
        )

    user_msg = "\n\n".join(context_parts)
    response = llm_chat(config, BOUNDARY_PROMPT, user_msg)

    if response:
        try:
            data = json.loads(response)
            return data.get("clips", [])
        except (json.JSONDecodeError, KeyError):
            pass

    # Fallback to heuristic
    return _heuristic_boundaries(cuts, transcript_segments, offset_s)


def _heuristic_boundaries(
    cuts: list[dict], transcript_segments: list[dict], offset_s: float
) -> list[dict]:
    """Heuristic: start at sentence boundary, end before next cut."""
    segs = transcript_segments
    if not segs:
        # No transcript: use raw times with fixed 90s duration
        return [
            {
                "start": round(c["time_s"] + offset_s, 2),
                "end": round(c["time_s"] + offset_s + 90, 2),
                "title": c["title"],
            }
            for c in cuts
        ]
    clips = []

    for i, cut in enumerate(cuts):
        raw_start = cut["time_s"] + offset_s

        # Find segment starting at or just before this time
        clip_start = segs[0]["start"]
        for s in segs:
            if s["start"] <= raw_start:
                clip_start = s["start"]

        # End: last complete segment before next cut
        if i + 1 < len(cuts):
            next_raw = cuts[i + 1]["time_s"] + offset_s
            clip_end = segs[0]["end"]
            for s in segs:
                if s["end"] <= next_raw:
                    clip_end = s["end"]
        else:
            # Last clip: ~2min
            target = clip_start + 120
            clip_end = clip_start + 120
            for s in segs:
                if s["end"] >= target:
                    clip_end = s["end"]
                    break

        # Cap 3min
        if clip_end - clip_start > 180:
            target = clip_start + 170
            for s in segs:
                if s["end"] >= target:
                    clip_end = s["end"]
                    break
                if s["end"] <= target:
                    clip_end = s["end"]

        clips.append(
            {
                "start": round(clip_start, 2),
                "end": round(clip_end, 2),
                "title": cut["title"],
            }
        )

    return clips
