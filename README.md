# reframe-one

Automated vertical reframing for podcast videos.

Takes a horizontal podcast recording (1920×1080) with multiple camera angles and generates vertical short clips (1080×1920) with:
- Automatic scene/camera detection
- Speaker-aware pan (zoom + track who's talking)
- Word-highlighted karaoke subtitles (ASS)
- Kdenlive project output (ready to review and render)

## Status

🚧 Early development

## How it works

```
Input: edited episode .kdenlive (horizontal 1920×1080)
  │
  ├── Scene detection (ffmpeg) → identify camera switches
  ├── Speaker detection (MediaPipe lip movement) → who's talking
  ├── Transcription (Whisper) → word-level timestamps
  ├── Karaoke subtitles (pysubs2) → ASS with \k tags
  └── Keyframe generation → pan X based on speaker position
  │
  ▼
Output: cortes .kdenlive (vertical 1080×1920, ready to render)
```

## Requirements

- Python 3.13+
- FFmpeg
- MediaPipe
- faster-whisper / stable-whisper

## License

MIT
