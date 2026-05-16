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
        inactive_color="&HFF000000",  # Transparent (FF alpha)
        outline_color="&H00000000",
        outline=6.0,
        margin_v=500,
        alignment=5,  # center screen
        bold=True,
    ),
    "papo-saude": SubtitleStyle(
        name="papo-saude",
        font="Arial",
        fontsize=80,
        active_color="&H005FA985",  # Green #85a95f (primary = after highlight)
        inactive_color="&H00BBBBBB",  # Gray (secondary = before highlight)
        outline_color="&H00000000",  # Black outline
        back_color="&H00000000",
        outline=4.0,
        margin_v=300,
        alignment=2,
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


def clean_words_with_llm(words: list[dict], config: LLMConfig | None = None) -> list[dict]:
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


# --- Timeline Remapping -----------------------------------------------


def _remap_segments_to_timeline(
    whisper_segments: list[dict],
    clips: list[dict],
    closing_duration: float,
    gap_duration: float,
    sync_offset_ms: int = 0,
) -> list[dict]:
    """Remap Whisper segments to timeline positions accounting for closings/gaps.

    Each clip occupies a position in the timeline:
      clip1 | closing | gap | clip2 | closing | gap | clip3 | closing

    Whisper timestamps are relative to the source video. We need to:
    1. Filter segments that fall within each clip's source time range
    2. Remap their timestamps to the corresponding timeline position
    """
    sync_offset_s = sync_offset_ms / 1000.0
    remapped = []
    timeline_pos = 0.0

    for clip_idx, clip in enumerate(clips):
        clip_start = clip["start"]
        clip_end = clip["end"]
        clip_duration = clip_end - clip_start

        # Find Whisper segments that overlap with this clip
        for seg in whisper_segments:
            seg_start = seg.get("start", 0)
            seg_end = seg.get("end", 0)

            # Skip segments outside this clip
            if seg_end <= clip_start or seg_start >= clip_end:
                continue

            # Clamp to clip boundaries
            clamped_start = max(seg_start, clip_start)
            clamped_end = min(seg_end, clip_end)

            # Calculate position in timeline
            # offset within clip + timeline position of clip start
            new_start = (clamped_start - clip_start) + timeline_pos - sync_offset_s
            new_end = (clamped_end - clip_start) + timeline_pos - sync_offset_s

            # Remap words too
            new_words = []
            for w in seg.get("words", []):
                w_start = w.get("start", 0)
                w_end = w.get("end", 0)
                if w_end <= clip_start or w_start >= clip_end:
                    continue
                new_words.append(
                    {
                        **w,
                        "start": (max(w_start, clip_start) - clip_start)
                        + timeline_pos
                        - sync_offset_s,
                        "end": (min(w_end, clip_end) - clip_start) + timeline_pos - sync_offset_s,
                    }
                )

            if new_words or not seg.get("words"):
                remapped.append(
                    {
                        **seg,
                        "start": new_start,
                        "end": new_end,
                        "words": new_words,
                    }
                )

        # Advance timeline position past this clip + closing + gap
        timeline_pos += clip_duration + closing_duration
        if clip_idx < len(clips) - 1:
            timeline_pos += gap_duration

    return remapped


# --- ASS Generation ---------------------------------------------------


def load_whisper_json(path: str) -> list[dict]:
    """Load Whisper transcription JSON (segments with words)."""
    with open(path) as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    return data.get("segments", [])


def _batch_clean_segments(segments: list[dict], llm_config: LLMConfig | None) -> list[list[dict]]:
    """Clean all segments in a single LLM call (or local fallback)."""
    results = []
    if not llm_config:
        for seg in segments:
            words = seg.get("words", [])
            results.append(clean_words_local(words) if words else [])
        return results

    # Batch: send all segments' words in one LLM call
    all_words = [seg.get("words", []) for seg in segments]
    non_empty = [(i, words) for i, words in enumerate(all_words) if words]

    if not non_empty:
        return [[] for _ in segments]

    # Build batch request: list of word lists
    batch_texts = [
        json.dumps([w["word"] for w in words], ensure_ascii=False) for _, words in non_empty
    ]
    batch_msg = "Process each line separately:\n" + "\n".join(
        f"[{i}] {t}" for i, t in enumerate(batch_texts)
    )

    batch_prompt = CLEANUP_SYSTEM_PROMPT.replace(
        "Return ONLY a JSON",
        'Return ONLY a JSON with "results" array, one entry per input line.'
        ' Each entry has "remove_indices"',
    )

    response = llm_chat(llm_config, batch_prompt, batch_msg)

    # Parse batch response
    batch_results: dict = {}
    if response:
        try:
            data = json.loads(response)
            for idx, entry in enumerate(data.get("results", [])):
                batch_results[idx] = set(entry.get("remove_indices", []))
        except (json.JSONDecodeError, KeyError, TypeError):
            pass  # fallback to local

    # Build final results
    results = [[] for _ in segments]
    for batch_idx, (seg_idx, words) in enumerate(non_empty):
        if batch_idx in batch_results:
            remove = batch_results[batch_idx]
            results[seg_idx] = [w for i, w in enumerate(words) if i not in remove]
        else:
            # LLM failed for this segment, use local fallback
            results[seg_idx] = clean_words_local(words)

    return results


def generate_ass(
    segments: list[dict],
    output_path: str,
    style: SubtitleStyle | str = "karaoke",
    max_chars: int = 50,
    llm_config: LLMConfig | None = None,
    offset_s: float = 0.0,
    sync_offset_ms: int = 0,
    clips: list[dict] | None = None,
    closing_duration: float = 3.8,
    gap_duration: float = 5.0,
):
    """Generate ASS file with configurable style and optional LLM cleanup.

    Args:
        segments: Whisper segments with word-level timestamps.
        output_path: Path to write .ass file.
        style: Style preset name or SubtitleStyle instance.
        max_chars: Max characters per subtitle line.
        llm_config: LLM config for text cleanup (None = local-only cleanup).
        offset_s: Subtract this from all timestamps (align to timeline start).
        sync_offset_ms: Fine-tune sync in milliseconds (negative = show earlier).
        clips: List of {start, end} dicts defining clip boundaries in source video.
            When provided, timestamps are remapped to timeline positions accounting
            for closings and gaps between clips.
        closing_duration: Duration of closing between clips (seconds).
        gap_duration: Duration of blank gap between clips (seconds).
    """
    # When clips are provided, remap segments to timeline positions
    if clips:
        segments = _remap_segments_to_timeline(
            segments, clips, closing_duration, gap_duration, sync_offset_ms
        )
        # offset_s and sync_offset_ms already applied in remap
        total_offset_s = 0.0
    else:
        # Legacy single-clip mode
        total_offset_s = offset_s - (sync_offset_ms / 1000.0)
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

    # Batch LLM cleanup: process all segments at once to minimize API calls
    cleaned_segments = _batch_clean_segments(segments, llm_config)

    for seg, cleaned_words in zip(segments, cleaned_segments):
        words = seg.get("words", [])
        if not words:
            start_ms = int((seg["start"] - total_offset_s) * 1000)
            end_ms = int((seg["end"] - total_offset_s) * 1000)
            event = pysubs2.SSAEvent(start=start_ms, end=end_ms, text=seg["text"].strip())
            subs.events.append(event)
            continue

        if not cleaned_words:
            continue

        # Break into lines
        lines = break_into_lines(cleaned_words, max_chars)

        # Generate events per line
        for line_words in lines:
            if False and style.name == "papo-saude":  # disabled: too heavy for full episodes
                # Per-word highlight only for short clips (avoids 4000+ events)
                events = _build_highlight_events(line_words, style, total_offset_s)
                subs.events.extend(events)
            else:
                start_ms = int((line_words[0]["start"] - total_offset_s) * 1000)
                end_ms = int((line_words[-1]["end"] - total_offset_s) * 1000)

                if style.name == "word-pop":
                    text = _build_word_pop(line_words)
                else:
                    text = _build_karaoke(line_words, style)

                subs.events.append(pysubs2.SSAEvent(start=start_ms, end=end_ms, text=text))

    subs.save(output_path)


def _build_karaoke(words: list[dict], style: SubtitleStyle) -> str:
    """Build karaoke text with \\k or \\kf tags for word-by-word highlight."""
    tag = "kf" if style.name in ("papo-saude", "word-pop") else "k"
    parts = []
    for word in words:
        duration_cs = max(1, int((word["end"] - word["start"]) * 100))
        parts.append(f"{{\\{tag}{duration_cs}}}{word['word']}")
    return "".join(parts).strip()


def _build_highlight_events(words: list[dict], style: SubtitleStyle, offset_s: float) -> list:
    """Build per-word highlight: gray→white transition + active word with background.

    Each word-moment = one event showing the full line (no gaps = no flicker).
    Words before active = white (already spoken).
    Active word = white + colored background box.
    Words after active = gray (not yet spoken).
    """
    import pysubs2

    events = []
    for i, word in enumerate(words):
        # Event spans from this word's start to next word's start (seamless)
        evt_start = int((word["start"] - offset_s) * 1000)
        if i + 1 < len(words):
            evt_end = int((words[i + 1]["start"] - offset_s) * 1000)
        else:
            evt_end = int((word["end"] - offset_s) * 1000)

        if evt_end <= evt_start:
            evt_end = evt_start + 33

        # Build full line with positional coloring
        parts = []
        for j, w in enumerate(words):
            if j < i:
                # Already spoken: white, no box
                parts.append(f"{{\\1c&H00FFFFFF&\\3c&H00000000&\\bord0}}{w['word']}")
            elif j == i:
                # Active: white + green background box
                parts.append(f"{{\\1c&H00FFFFFF&\\3c{style.outline_color}\\bord8}}{w['word']}")
            else:
                # Not yet spoken: gray, no box
                parts.append(f"{{\\1c{style.inactive_color}\\3c&H00000000&\\bord0}}{w['word']}")

        text = "".join(parts).strip()
        events.append(pysubs2.SSAEvent(start=evt_start, end=evt_end, text=text))

    return events


def _build_word_pop(words: list[dict]) -> str:
    """Build word-pop: only active word visible, others hidden via \\alpha."""
    # For word-pop, we show all words but use \kf (fill) for smooth highlight
    parts = []
    for word in words:
        duration_cs = max(1, int((word["end"] - word["start"]) * 100))
        parts.append(f"{{\\kf{duration_cs}}}{word['word']}")
    return "".join(parts).strip()


def _parse_ass_color(color_str: str) -> tuple[int, int, int, int]:
    """Parse ASS color string like &H0000FFFF to (r, g, b, a).

    ASS format: &HAABBGGRR where AA=alpha (00=opaque, FF=transparent).
    """
    hex_str = color_str.replace("&H", "").replace("&h", "").ljust(8, "0")
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
