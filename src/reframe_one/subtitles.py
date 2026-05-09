"""Generate karaoke-style ASS subtitles with word highlighting."""

import json

import pysubs2


def load_whisper_json(path: str) -> list[dict]:
    """Load Whisper transcription JSON (segments with words)."""
    with open(path) as f:
        data = json.load(f)
    # Handle both formats: list of segments or {segments: [...]}
    if isinstance(data, list):
        return data
    return data.get("segments", [])


def generate_karaoke_ass(
    segments: list[dict],
    output_path: str,
    style_name: str = "Default",
    font: str = "Arial",
    fontsize: int = 80,
    primary_color: str = "&H0000FFFF",  # Yellow (active word)
    secondary_color: str = "&H00FFFFFF",  # White (inactive)
    outline_color: str = "&H00000000",  # Black outline
    margin_v: int = 300,
):
    """Generate ASS file with karaoke word-by-word highlighting.

    Each word gets a \\k tag with duration in centiseconds.
    """
    subs = pysubs2.SSAFile()
    subs.info["PlayResX"] = "1080"
    subs.info["PlayResY"] = "1920"

    style = pysubs2.SSAStyle(
        fontname=font,
        fontsize=fontsize,
        primarycolor=pysubs2.Color(*_parse_ass_color(primary_color)),
        secondarycolor=pysubs2.Color(*_parse_ass_color(secondary_color)),
        outlinecolor=pysubs2.Color(*_parse_ass_color(outline_color)),
        backcolor=pysubs2.Color(0, 0, 0, 0),
        outline=5.0,
        marginv=margin_v,
        alignment=2,  # bottom center
    )
    subs.styles[style_name] = style

    for seg in segments:
        words = seg.get("words", [])
        if not words:
            # Fallback: single line without karaoke
            start_ms = int(seg["start"] * 1000)
            end_ms = int(seg["end"] * 1000)
            event = pysubs2.SSAEvent(start=start_ms, end=end_ms, text=seg["text"].strip())
            subs.events.append(event)
            continue

        # Build karaoke line
        start_ms = int(words[0]["start"] * 1000)
        end_ms = int(words[-1]["end"] * 1000)

        karaoke_text = ""
        for word in words:
            duration_cs = int((word["end"] - word["start"]) * 100)
            duration_cs = max(1, duration_cs)  # minimum 1 centisecond
            karaoke_text += f"{{\\k{duration_cs}}}{word['word']}"

        event = pysubs2.SSAEvent(start=start_ms, end=end_ms, text=karaoke_text.strip())
        subs.events.append(event)

    subs.save(output_path)


def _parse_ass_color(color_str: str) -> tuple[int, int, int, int]:
    """Parse ASS color string like &H0000FFFF to (r, g, b, a)."""
    # ASS format: &HAABBGGRR
    hex_str = color_str.replace("&H", "").replace("&h", "")
    a = int(hex_str[0:2], 16)
    b = int(hex_str[2:4], 16)
    g = int(hex_str[4:6], 16)
    r = int(hex_str[6:8], 16)
    return (r, g, b, a)
