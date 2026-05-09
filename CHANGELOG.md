# Changelog

## [0.1.0-dev] - 2026-05-09

### Added
- Initial pipeline: parse → scene detect → classify cameras → karaoke subs → kdenlive gen
- CLI commands: `generate`, `scenes`, `subtitles`
- Face count camera classification (OpenCV DNN)
- Karaoke ASS subtitles with `\k` word-level timing
- Multiple pan keyframes per segment (follows camera switches)

### Fixed
- Consistent UUIDs across chain instances (Kdenlive bin errors)
- Multiple keyframes per segment (was single keyframe at midpoint)
