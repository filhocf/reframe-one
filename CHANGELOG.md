# Changelog

## [0.2.0-dev] - 2026-05-10

### Added
- **Smart subtitles**: 3 visual styles (karaoke, hormozi, word-pop) + custom style support
- **Papo Saúde style**: per-word background highlight (green #85a95f box on active word)
- **LLM text cleanup**: remove fillers (né, tipo, ah) and stutters via configurable LLM
- **Local cleanup fallback**: regex-based filler removal without LLM
- **Line breaking**: ~50 chars per line with word timestamp preservation
- **LLM interface** (`llm.py`): pluggable providers (ollama, groq, openai)
- **ASS integration**: subtitles embedded in .kdenlive as avfilter.subtitles
- **Clip selection**: manual (--clips '0:30-1:45') or LLM-scored (--auto-select)
- **Per-episode config**: cameras, closing, subtitle_style, sync_offset via JSON/YAML
- **Timeline guides**: green (start) and red (end) markers at clip boundaries
- **Automatic gap**: 5s blank inserted between consecutive clips
- **Selective steps**: --steps flag to skip expensive recomputation (uses cache)
- **Intermediate cache**: scenes + cameras + speakers saved as JSON
- **Progress display**: percentage shown during camera classification and speaker detection
- **Sync offset**: configurable ms offset to fine-tune subtitle timing

### Fixed
- First entry now starts at source project in-point (not first scene change)
- Subtitle timestamps relative to timeline (offset subtracted)
- Closing path correctly referenced in generated .kdenlive
- Pre-existing lint issues (import sort, unused imports)

## [0.1.0-dev] - 2026-05-09

### Added
- Initial pipeline: parse → scene detect → classify cameras → karaoke subs → kdenlive gen
- CLI commands: `generate`, `scenes`, `subtitles`
- Face count camera classification (OpenCV DNN)
- Speaker detection via MediaPipe FaceLandmarker (lip movement)
- Karaoke ASS subtitles with `\k` word-level timing
- Multiple pan keyframes per segment (follows camera switches)
- CI: GitHub Actions (ruff + pytest), Gemini Code Assist

### Fixed
- Consistent UUIDs across chain instances
- Hard cuts (1 entry per camera segment, no interpolation)
- A2 empty, A1 mirrors V1 (correct track layout)
- Central camera with zoom (X=-1200)
