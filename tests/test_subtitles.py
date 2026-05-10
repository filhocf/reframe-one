"""Tests for subtitles module."""

import tempfile

from reframe_one.subtitles import (
    SubtitleStyle,
    break_into_lines,
    clean_words_local,
    generate_ass,
    generate_karaoke_ass,
)

SAMPLE_SEGMENTS = [
    {
        "start": 1.0,
        "end": 4.0,
        "text": "Então a violência né contra a mulher",
        "words": [
            {"word": "Então", "start": 1.0, "end": 1.3},
            {"word": " a", "start": 1.35, "end": 1.45},
            {"word": " violência", "start": 1.5, "end": 2.1},
            {"word": " né", "start": 2.2, "end": 2.4},
            {"word": " contra", "start": 2.5, "end": 2.8},
            {"word": " a", "start": 2.85, "end": 2.95},
            {"word": " mulher", "start": 3.0, "end": 3.6},
        ],
    }
]


# --- Legacy compatibility ---


def test_generate_karaoke_ass_creates_file():
    segments = [
        {
            "start": 1.0,
            "end": 3.0,
            "text": "Olá pessoal",
            "words": [
                {"word": "Olá", "start": 1.0, "end": 1.5},
                {"word": " pessoal", "start": 1.6, "end": 2.8},
            ],
        }
    ]
    with tempfile.NamedTemporaryFile(suffix=".ass", delete=False) as f:
        generate_karaoke_ass(segments, f.name)
        with open(f.name) as out:
            content = out.read()

    assert "PlayResX: 1080" in content
    assert "PlayResY: 1920" in content
    assert "\\k" in content


def test_generate_karaoke_ass_word_timing():
    segments = [
        {
            "start": 0.0,
            "end": 2.0,
            "text": "Hello world",
            "words": [
                {"word": "Hello", "start": 0.0, "end": 0.5},
                {"word": " world", "start": 0.6, "end": 1.8},
            ],
        }
    ]
    with tempfile.NamedTemporaryFile(suffix=".ass", delete=False) as f:
        generate_karaoke_ass(segments, f.name)
        with open(f.name) as out:
            content = out.read()

    assert "\\k50" in content
    assert "\\k120" in content


def test_generate_karaoke_ass_fallback_no_words():
    segments = [{"start": 5.0, "end": 8.0, "text": "Sem words"}]
    with tempfile.NamedTemporaryFile(suffix=".ass", delete=False) as f:
        generate_karaoke_ass(segments, f.name)
        with open(f.name) as out:
            content = out.read()

    assert "Sem words" in content


# --- Local cleanup ---


def test_clean_words_local_removes_fillers():
    words = [
        {"word": "Então", "start": 1.0, "end": 1.3},
        {"word": " a", "start": 1.35, "end": 1.45},
        {"word": " violência", "start": 1.5, "end": 2.1},
        {"word": " né", "start": 2.2, "end": 2.4},
        {"word": " contra", "start": 2.5, "end": 2.8},
    ]
    cleaned = clean_words_local(words)
    texts = [w["word"].strip() for w in cleaned]
    assert "né" not in texts
    assert "violência" in texts
    assert "contra" in texts


def test_clean_words_local_keeps_meaningful():
    words = [
        {"word": "A", "start": 0.0, "end": 0.1},
        {"word": " saúde", "start": 0.2, "end": 0.6},
        {"word": " mental", "start": 0.7, "end": 1.1},
    ]
    cleaned = clean_words_local(words)
    assert len(cleaned) == 3


# --- Line breaking ---


def test_break_into_lines_respects_max_chars():
    words = [
        {"word": "A", "start": 0.0, "end": 0.1},
        {"word": " violência", "start": 0.2, "end": 0.6},
        {"word": " contra", "start": 0.7, "end": 1.0},
        {"word": " a", "start": 1.1, "end": 1.2},
        {"word": " mulher", "start": 1.3, "end": 1.7},
        {"word": " é", "start": 1.8, "end": 1.9},
        {"word": " um", "start": 2.0, "end": 2.1},
        {"word": " problema", "start": 2.2, "end": 2.8},
        {"word": " grave", "start": 2.9, "end": 3.3},
    ]
    lines = break_into_lines(words, max_chars=25)
    assert len(lines) >= 2
    for line in lines:
        text = "".join(w["word"] for w in line).strip()
        # Allow slight overflow (last word can push past limit)
        assert len(text) <= 35


def test_break_into_lines_single_short():
    words = [
        {"word": "Olá", "start": 0.0, "end": 0.3},
        {"word": " mundo", "start": 0.4, "end": 0.8},
    ]
    lines = break_into_lines(words, max_chars=50)
    assert len(lines) == 1


# --- Multiple styles ---


def test_generate_ass_karaoke_style():
    with tempfile.NamedTemporaryFile(suffix=".ass", delete=False) as f:
        generate_ass(SAMPLE_SEGMENTS, f.name, style="karaoke")
        with open(f.name) as out:
            content = out.read()

    assert "\\k" in content
    assert "PlayResX: 1080" in content


def test_generate_ass_hormozi_style():
    with tempfile.NamedTemporaryFile(suffix=".ass", delete=False) as f:
        generate_ass(SAMPLE_SEGMENTS, f.name, style="hormozi")
        with open(f.name) as out:
            content = out.read()

    assert "\\k" in content
    assert "Montserrat" in content


def test_generate_ass_word_pop_style():
    with tempfile.NamedTemporaryFile(suffix=".ass", delete=False) as f:
        generate_ass(SAMPLE_SEGMENTS, f.name, style="word-pop")
        with open(f.name) as out:
            content = out.read()

    assert "\\kf" in content  # word-pop uses \kf (fill)


def test_generate_ass_custom_style():
    custom = SubtitleStyle(font="Comic Sans MS", fontsize=60, active_color="&H000000FF")
    with tempfile.NamedTemporaryFile(suffix=".ass", delete=False) as f:
        generate_ass(SAMPLE_SEGMENTS, f.name, style=custom)
        with open(f.name) as out:
            content = out.read()

    assert "Comic Sans MS" in content


def test_generate_ass_with_local_cleanup():
    """Local cleanup removes fillers without LLM."""
    with tempfile.NamedTemporaryFile(suffix=".ass", delete=False) as f:
        generate_ass(SAMPLE_SEGMENTS, f.name, style="karaoke", llm_config=None)
        with open(f.name) as out:
            content = out.read()

    # "né" should be removed by local cleanup
    assert "né" not in content
    assert "violência" in content or "viol" in content


def test_generate_ass_line_breaking():
    """Lines should be broken at ~50 chars."""
    long_segment = {
        "start": 0.0,
        "end": 10.0,
        "text": "A violência contra a mulher é um problema grave que afeta toda a sociedade",
        "words": [
            {"word": "A", "start": 0.0, "end": 0.1},
            {"word": " violência", "start": 0.2, "end": 0.7},
            {"word": " contra", "start": 0.8, "end": 1.1},
            {"word": " a", "start": 1.2, "end": 1.3},
            {"word": " mulher", "start": 1.4, "end": 1.8},
            {"word": " é", "start": 1.9, "end": 2.0},
            {"word": " um", "start": 2.1, "end": 2.2},
            {"word": " problema", "start": 2.3, "end": 2.8},
            {"word": " grave", "start": 2.9, "end": 3.2},
            {"word": " que", "start": 3.3, "end": 3.5},
            {"word": " afeta", "start": 3.6, "end": 4.0},
            {"word": " toda", "start": 4.1, "end": 4.4},
            {"word": " a", "start": 4.5, "end": 4.6},
            {"word": " sociedade", "start": 4.7, "end": 5.3},
        ],
    }
    with tempfile.NamedTemporaryFile(suffix=".ass", delete=False) as f:
        generate_ass([long_segment], f.name, style="karaoke", max_chars=30)
        with open(f.name) as out:
            content = out.read()

    # Should have multiple Dialogue lines (broken into lines)
    dialogue_count = content.count("Dialogue:")
    assert dialogue_count >= 2
