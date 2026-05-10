"""Generate ASS subtitles with multiple styles and optional LLM text cleanup."""

import json
from dataclasses import dataclass

import pysubs2

from reframe_one.llm import LLMConfig, llm_chat

# --- Styles -----------------------------------------------------------


@dataclass
class SubtitleStyle:
    """Visual style for subtitles."""

    name: str = "karaoke"
    font: str = "Arial"
    fontsize: int = 80
    active_color: str = "&H0000FFFF"  # Yellow
    inactive_color: str = "&H00FFFFFF"  # White
    outline_color: str = "&H00000000"  # Black
    back_color: str = "&H00000000"  # Transparent
    outline: float = 5.0
    margin_v: int = 300
    alignment: int = 2  # bottom center
    bold: bool = False


STYLE_PRESETS: dict[str, SubtitleStyle] = {
    "karaoke": SubtitleStyle(
        name="karaoke",
        active_color="&H0000FFFF",  # Yellow active
        inactive_color="&H00FFFFFF",  # White inactive
    ),
    "hormozi": SubtitleStyle(
        name="hormozi",
        font="Montserrat",
        fontsize=90,
        active_color="&H00FFFFFF",  # White active
        inactive_color="&H00BBBBBB",  # Gray inactive
        back_color="&H00800080",  # Purple background on active
        outline=8.0,
        bold=True,
        margin_v=400,
    ),
    "word-pop": SubtitleStyle(
        name="word-pop",
        font="Arial",
        fontsize=100,
        active_color="&H00FFFFFF",  # White
        inactive_color="&H00000000",  # Hidden (transparent)
        outline_color="&H00000000",
        outline=6.0,
        margin_v=500,
        alignment=5,  # center screen
        bold=True,
    ),
}


# --- LLM Text Cleanup ------------------------------------------------

CLEANUP_SYSTEM_PROMPT = """You clean podcast transcription text for subtitles.

Rules:
1. Remove filler words: "né", "tipo", "assim", "então" (when used as filler), "ah", "eh", "hm", "uh"
2. Remove stutters: repeated syllables like "vi-vi-violência" → keep only the final complete word
3. Keep the meaning intact — never change the speaker's message
4. Return ONLY a JSON with a "remove_indices" array of 0-based indices of words to remove

Example input: ["Então", " a", " vi-", " vi-", " violência", " né", " contra", " a", " mulher"]
Example output: {"remove_indices": [0, 2, 3, 5]}"""


def clean_words_with_llm(
    words: list[dict], config: LLMConfig | None = None
) -> list[dict]:
    """Remove fillers and stutters using LLM. Returns filtered word list."""
    if config is None:
        return words

    word_texts = [w["word"] for w in words]
    user_msg = json.dumps(word_texts, ensure_ascii=False)

    response = llm_chat(config, CLEANUP_SYSTEM_PROMPT, user_msg)
    if not response:
        return words  # fallback: keep all

    try:
        data = json.loads(response)
        remove_indices = set(data.get("remove_indices", []))
        return [w for i, w in enumerate(words) if i not in remove_indices]
    except (json.JSONDecodeError, KeyError):
        return words  # fallback: keep all


def clean_words_local(words: list[dict]) -> list[dict]:
    """Remove obvious fillers without LLM (fast local fallback)."""
    fillers = {"né", "neh", "tipo", "ah", "eh", "hm", "uh", "uhm", "ahn"}
    result = []
    for w in words:
        text = w["word"].strip().lower().rstrip(",.")
        if text in fillers:
            continue
        result.append(w)
    return result


# --- Line Breaking ----------------------------------------------------


def break_into_lines(words: list[dict], max_chars: int = 50) -> list[list[dict]]:
    """Break words into lines of approximately max_chars."""
    lines: list[list[dict]] = []
    current_line: list[dict] = []
    current_len = 0

    for word in words:
        word_len = len(word["word"].strip())
        if current_len + word_len > max_chars and current_line:
            lines.append(current_line)
            current_line = [word]
            current_len = word_len
        else:
            current_line.append(word)
            current_len += word_len + 1  # +1 for space

    if current_line:
        lines.append(current_line)
    return lines


# --- ASS Generation ---------------------------------------------------


def load_whisper_json(path: str) -> list[dict]:
    """Load Whisper transcription JSON (segments with words)."""
    with open(path) as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    return data.get("segments", [])


def generate_ass(
    segments: list[dict],
    output_path: str,
    style: SubtitleStyle | str = "karaoke",
    max_chars: int = 50,
    llm_config: LLMConfig | None = None,
):
    """Generate ASS file with configurable style and optional LLM cleanup.

    Args:
        segments: Whisper segments with word-level timestamps.
        output_path: Path to write .ass file.
        style: Style preset name or SubtitleStyle instance.
        max_chars: Max characters per subtitle line.
        llm_config: LLM config for text cleanup (None = local-only cleanup).
    """
    if isinstance(style, str):
        style = STYLE_PRESETS.get(style, STYLE_PRESETS["karaoke"])

    subs = pysubs2.SSAFile()
    subs.info["PlayResX"] = "1080"
    subs.info["PlayResY"] = "1920"

    ass_style = pysubs2.SSAStyle(
        fontname=style.font,
        fontsize=style.fontsize,
        primarycolor=pysubs2.Color(*_parse_ass_color(style.active_color)),
        secondarycolor=pysubs2.Color(*_parse_ass_color(style.inactive_color)),
        outlinecolor=pysubs2.Color(*_parse_ass_color(style.outline_color)),
        backcolor=pysubs2.Color(*_parse_ass_color(style.back_color)),
        outline=style.outline,
        marginv=style.margin_v,
        alignment=style.alignment,
        bold=style.bold,
    )
    subs.styles["Default"] = ass_style

    for seg in segments:
        words = seg.get("words", [])
        if not words:
            start_ms = int(seg["start"] * 1000)
            end_ms = int(seg["end"] * 1000)
            event = pysubs2.SSAEvent(start=start_ms, end=end_ms, text=seg["text"].strip())
            subs.events.append(event)
            continue

        # Clean text
        if llm_config:
            cleaned = clean_words_with_llm(words, llm_config)
        else:
            cleaned = clean_words_local(words)

        if not cleaned:
            continue

        # Break into lines
        lines = break_into_lines(cleaned, max_chars)

        # Generate events per line
        for line_words in lines:
            start_ms = int(line_words[0]["start"] * 1000)
            end_ms = int(line_words[-1]["end"] * 1000)

            if style.name == "word-pop":
                text = _build_word_pop(line_words)
            else:
                text = _build_karaoke(line_words, style)

            subs.events.append(pysubs2.SSAEvent(start=start_ms, end=end_ms, text=text))

    subs.save(output_path)


def _build_karaoke(words: list[dict], style: SubtitleStyle) -> str:
    """Build karaoke text with \\k tags for word-by-word highlight."""
    parts = []
    for word in words:
        duration_cs = max(1, int((word["end"] - word["start"]) * 100))
        parts.append(f"{{\\k{duration_cs}}}{word['word']}")
    return "".join(parts).strip()


def _build_word_pop(words: list[dict]) -> str:
    """Build word-pop: only active word visible, others hidden via \\alpha."""
    # For word-pop, we show all words but use \kf (fill) for smooth highlight
    parts = []
    for word in words:
        duration_cs = max(1, int((word["end"] - word["start"]) * 100))
        parts.append(f"{{\\kf{duration_cs}}}{word['word']}")
    return "".join(parts).strip()


def _parse_ass_color(color_str: str) -> tuple[int, int, int, int]:
    """Parse ASS color string like &H0000FFFF to (r, g, b, a)."""
    hex_str = color_str.replace("&H", "").replace("&h", "")
    a = int(hex_str[0:2], 16)
    b = int(hex_str[2:4], 16)
    g = int(hex_str[4:6], 16)
    r = int(hex_str[6:8], 16)
    return (r, g, b, a)


# --- Legacy compatibility ---


def generate_karaoke_ass(
    segments: list[dict],
    output_path: str,
    style_name: str = "Default",
    font: str = "Arial",
    fontsize: int = 80,
    primary_color: str = "&H0000FFFF",
    secondary_color: str = "&H00FFFFFF",
    outline_color: str = "&H00000000",
    margin_v: int = 300,
):
    """Legacy function — wraps generate_ass with karaoke style."""
    style = SubtitleStyle(
        font=font,
        fontsize=fontsize,
        active_color=primary_color,
        inactive_color=secondary_color,
        outline_color=outline_color,
        margin_v=margin_v,
    )
    generate_ass(segments, output_path, style=style, max_chars=999)
