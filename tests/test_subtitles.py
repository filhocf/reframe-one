"""Tests for subtitles module."""

import tempfile

from reframe_one.subtitles import generate_karaoke_ass


def test_generate_karaoke_ass_creates_file():
    segments = [
        {
            "start": 1.0,
            "end": 3.0,
            "text": "Olá pessoal",
            "words": [
                {"word": "Olá", "start": 1.0, "end": 1.5, "probability": 0.9},
                {"word": " pessoal", "start": 1.6, "end": 2.8, "probability": 0.9},
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
                {"word": "Hello", "start": 0.0, "end": 0.5, "probability": 0.9},
                {"word": " world", "start": 0.6, "end": 1.8, "probability": 0.9},
            ],
        }
    ]
    with tempfile.NamedTemporaryFile(suffix=".ass", delete=False) as f:
        generate_karaoke_ass(segments, f.name)
        with open(f.name) as out:
            content = out.read()

    # \k50 = 0.5s in centiseconds, \k120 = 1.2s
    assert "\\k50" in content
    assert "\\k120" in content


def test_generate_karaoke_ass_fallback_no_words():
    segments = [{"start": 5.0, "end": 8.0, "text": "Sem words"}]
    with tempfile.NamedTemporaryFile(suffix=".ass", delete=False) as f:
        generate_karaoke_ass(segments, f.name)
        with open(f.name) as out:
            content = out.read()

    assert "Sem words" in content
