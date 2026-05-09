# reframe-one

Automated vertical reframing for podcast videos. Takes a horizontal Kdenlive project (1920×1080) and generates a vertical project (1080×1920) with zoom + pan tracking who's speaking.

## What it does

```bash
reframe-one generate episode.kdenlive --transcript episode-transcricao.json
```

**Input:** `episode.kdenlive` (edited horizontal episode)
**Output:** `episode-cortes.kdenlive` + `episode-cortes.ass` (vertical, ready to render)

## How it works

1. Parses the source .kdenlive project (extracts video path, segments)
2. Detects scene changes in the raw video (ffmpeg)
3. Classifies each scene by camera angle (face count via OpenCV)
4. Generates pan keyframes (zoom 320% + X position based on camera)
5. Generates karaoke subtitles (word-by-word highlight from Whisper JSON)
6. Outputs a complete .kdenlive project (vertical 1080×1920)

## Requirements

- Python 3.13+
- FFmpeg
- OpenCV face detection model (`res10_300x300_ssd_iter_140000.caffemodel`)

## Install

```bash
git clone https://github.com/filhocf/reframe-one.git
cd reframe-one
uv venv && uv pip install -e .
```

## Usage

```bash
# Generate vertical project from horizontal episode
PYTHONPATH=src python3 -m reframe_one.cli generate \
  "path/to/episode.kdenlive" \
  --transcript "path/to/episode-transcricao.json"

# Scene detection only
PYTHONPATH=src python3 -m reframe_one.cli scenes "path/to/video.mp4"

# Karaoke subtitles only
PYTHONPATH=src python3 -m reframe_one.cli subtitles "path/to/transcricao.json"
```

## Stack

Python, FFmpeg, OpenCV (DNN face detection), pysubs2, xml.etree

## License

MIT
