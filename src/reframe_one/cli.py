"""CLI for reframe-one."""

import argparse
import json
import os
import sys

from .kdenlive_gen import CLOSING_DURATION_S, GAP_BLANK_SECONDS, generate_vertical_project
from .parse_kdenlive import parse_project
from .scene_detect import classify_cameras, detect_scenes, save_scenes
from .subtitles import generate_ass, load_whisper_json


def main():
    parser = argparse.ArgumentParser(description="reframe-one: vertical reframing for podcasts")
    sub = parser.add_subparsers(dest="command")

    # Scene detection
    p_scene = sub.add_parser("scenes", help="Detect scene changes")
    p_scene.add_argument("video", help="Input video path")
    p_scene.add_argument("-o", "--output", default="scenes.json")
    p_scene.add_argument("-t", "--threshold", type=float, default=0.3)

    # Karaoke subtitles
    p_subs = sub.add_parser("subtitles", help="Generate karaoke ASS from Whisper JSON")
    p_subs.add_argument("transcript", help="Whisper JSON transcript")
    p_subs.add_argument("-o", "--output", default="subtitles.ass")

    # Generate vertical project
    p_gen = sub.add_parser("generate", help="Generate vertical .kdenlive from source project")
    p_gen.add_argument("input", help="Input .kdenlive project file")
    p_gen.add_argument("--transcript", help="Whisper JSON transcript (optional)")
    p_gen.add_argument("--closing", default=None, help="Closing video path (overrides config)")
    p_gen.add_argument("--threshold", type=float, default=0.3, help="Scene detection threshold")
    p_gen.add_argument("--config", help="Episode config file (JSON/YAML)")
    p_gen.add_argument("--clips", help="Time ranges to include (e.g. '0:30-1:45,3:00-4:20')")
    p_gen.add_argument("--clips-file", help="JSON file with clip selections")
    p_gen.add_argument(
        "--auto-select", action="store_true", help="Use LLM to score and select clips"
    )
    p_gen.add_argument("--steps", help="Run only these steps (comma-separated: 1-6). Default: all")

    # Clips from PDF
    p_clips = sub.add_parser("clips-from-pdf", help="Generate clips.json from PDF suggestions")
    p_clips.add_argument("--pdf", required=True, help="PDF with cut suggestions")
    p_clips.add_argument("--transcript", required=True, help="Whisper JSON transcript")
    p_clips.add_argument("--episode", required=True, help="Episode name to find in PDF")
    p_clips.add_argument("--offset", type=float, default=0.0, help="Source in-point offset (s)")
    p_clips.add_argument("-o", "--output", default="clips.json", help="Output clips JSON")
    p_clips.add_argument("--use-llm", action="store_true", help="Use LLM for exact boundaries")

    args = parser.parse_args()

    if args.command == "scenes":
        print(f"Detecting scenes in {args.video} (threshold={args.threshold})...")
        scenes = detect_scenes(args.video, args.threshold)
        save_scenes(scenes, args.output)
        print(f"Found {len(scenes)} scene changes → {args.output}")

    elif args.command == "subtitles":
        print(f"Generating karaoke ASS from {args.transcript}...")
        segments = load_whisper_json(args.transcript)
        generate_ass(segments, args.output)
        print(f"Generated {args.output}")

    elif args.command == "generate":
        _cmd_generate(args)

    elif args.command == "clips-from-pdf":
        _cmd_clips_from_pdf(args)

    else:
        parser.print_help()
        sys.exit(1)


def _cmd_generate(args):
    """Generate vertical .kdenlive project."""
    import time as _time

    from .config import load_config

    t0 = _time.time()
    ep_config = load_config(args.config)
    input_path = args.input

    # Parse steps
    run_steps = set(range(1, 7))  # default: all
    if args.steps:
        run_steps = {int(s.strip()) for s in args.steps.split(",")}

    # Cache path
    base = os.path.splitext(input_path)[0]
    cache_path = base + "-cache.json"

    print("=" * 60)
    print("  reframe-one — Vertical Reframing Pipeline")
    print("=" * 60)
    print(f"\n📂 Input: {input_path}")
    if args.config:
        print(f"⚙️  Config: {args.config}")
    print()

    # --- Step 1: Parse ---
    t1 = _time.time()
    print("[1/6] Parsing source project...")
    project = parse_project(input_path)

    video_path = project.raw_video_path
    if not os.path.exists(video_path):
        print(f"  ❌ ERROR: Raw video not found: {video_path}")
        sys.exit(1)

    segments = [{"start": s.in_seconds, "end": s.out_seconds} for s in project.segments]
    total_source_dur = sum(s["end"] - s["start"] for s in segments)
    print(f"  📹 Video: {os.path.basename(video_path)}")
    print(f"  🎬 Segments: {len(segments)} ({total_source_dur:.1f}s total)")
    print(f"  ⏱️  {_time.time() - t1:.1f}s")

    # --- Clip selection ---
    if args.clips or args.clips_file:
        from .clip_selector import load_clips_file, parse_time_ranges

        if args.clips_file:
            time_ranges = load_clips_file(args.clips_file)
            print(f"\n  ✂️  Loading clips from: {os.path.basename(args.clips_file)}")
        else:
            time_ranges = parse_time_ranges(args.clips)
            print(f"\n  ✂️  Using time ranges: {args.clips}")
        # Replace segments with clip ranges
        segments = [{"start": s, "end": e} for s, e in time_ranges]
        filtered_dur = sum(s["end"] - s["start"] for s in segments)
        print(f"  → {len(segments)} clips ({filtered_dur:.0f}s total)")

    elif args.auto_select and args.transcript:
        from .clip_selector import select_by_llm
        from .llm import LLMConfig
        from .subtitles import load_whisper_json as _load_wj

        print("\n  🤖 Auto-selecting clips via LLM...")
        transcript_segs = _load_wj(args.transcript)
        segments = select_by_llm(segments, transcript_segs, LLMConfig())
        filtered_dur = sum(s["end"] - s["start"] for s in segments)
        print(f"  → {len(segments)} clips selected ({filtered_dur:.1f}s)")

    # --- Step 2: Scene detection ---
    t2 = _time.time()
    if 2 in run_steps:
        print(f"\n[2/6] Detecting scenes (threshold={args.threshold})...")
        scenes = detect_scenes(video_path, args.threshold)
        # Ensure first segment starts at source in-point (not first scene change)
        seg_start = segments[0]["start"]
        if not scenes or scenes[0].timestamp > seg_start + 0.5:
            from .scene_detect import SceneChange as _SC

            scenes.insert(0, _SC(timestamp=seg_start, score=0.0))
        print(f"  🎞️  {len(scenes)} scene changes detected")
        print(f"  ⏱️  {_time.time() - t2:.1f}s")
    else:
        cache = _load_cache(cache_path)
        scenes_data = cache.get("scenes", [])
        from .scene_detect import SceneChange

        scenes = [SceneChange(timestamp=s["timestamp"], score=s["score"]) for s in scenes_data]
        # Ensure first segment starts at source in-point
        seg_start = segments[0]["start"]
        if not scenes or scenes[0].timestamp > seg_start + 0.5:
            scenes.insert(0, SceneChange(timestamp=seg_start, score=0.0))
        print(f"\n[2/6] Loaded {len(scenes)} scenes from cache")

    # --- Step 3: Camera classification ---
    t3 = _time.time()
    if 3 in run_steps:
        print(f"\n[3/6] Classifying cameras ({len(scenes)} scenes)...")

        def _progress(current, total):
            pct = current * 100 // total
            print(f"\r  [{current}/{total}] {pct}%", end="", flush=True)

        camera_segments = classify_cameras(video_path, scenes, progress_cb=_progress)
    else:
        cache = _load_cache(cache_path)
        camera_segments = cache.get("camera_segments", [])
        print(f"\n[3/6] Loaded {len(camera_segments)} camera segments from cache")
    cam_counts = {}
    for cs in camera_segments:
        cam_counts[cs["camera"]] = cam_counts.get(cs["camera"], 0) + 1
    cam_summary = ", ".join(f"{k}={v}" for k, v in sorted(cam_counts.items()))
    if 3 in run_steps:
        print(f"\r  📷 {len(camera_segments)} segments: {cam_summary}     ")
        print(f"  ⏱️  {_time.time() - t3:.1f}s")

    # --- Step 4: Speaker detection ---
    t4 = _time.time()
    if 4 in run_steps:
        print(f"\n[4/6] Detecting speakers ({len(camera_segments)} segments)...")
        from .speaker_detect import detect_speaker_position, x_position_to_pan

        speaker_count = 0
        total = len(camera_segments)
        for idx, cs in enumerate(camera_segments):
            pct = (idx + 1) * 100 // total
            print(f"\r  [{idx + 1}/{total}] {pct}%", end="", flush=True)
            if cs["end"] is None or (cs["end"] - cs["start"]) < 1.0:
                continue
            face_x = detect_speaker_position(video_path, cs["start"], cs["end"], num_frames=5)
            if face_x is not None:
                cs["pan_x"] = x_position_to_pan(face_x)
                speaker_count += 1
        spk_pct = speaker_count * 100 // max(total, 1)
        print(f"\r  🗣️  Speaker: {speaker_count}/{total} ({spk_pct}%)     ")
        print(f"  ⏱️  {_time.time() - t4:.1f}s")
    else:
        # camera_segments already loaded from cache (includes pan_x)
        speaker_count = sum(1 for cs in camera_segments if "pan_x" in cs)
        total = len(camera_segments)
        print(f"\n[4/6] Loaded speaker data from cache ({speaker_count}/{total})")

    # Save cache after expensive steps
    if run_steps & {2, 3, 4}:
        _save_cache(cache_path, scenes, camera_segments)
        print(f"\n  💾 Cache saved: {os.path.basename(cache_path)}")

    # --- Step 5: Subtitles ---
    t5 = _time.time()
    ass_output = ""
    if args.transcript:
        print(f"\n[5/6] Generating subtitles (style={ep_config.subtitle_style})...")
        whisper_segs = load_whisper_json(args.transcript)
        base = os.path.splitext(input_path)[0]
        ass_output = base + "-cortes.ass"
        # Pass clips for multi-clip timeline remapping
        clips_for_subs = segments if len(segments) > 1 else None
        generate_ass(
            whisper_segs,
            ass_output,
            style=ep_config.subtitle_style,
            max_chars=ep_config.max_chars,
            offset_s=segments[0]["start"],
            sync_offset_ms=ep_config.sync_offset_ms,
            clips=clips_for_subs,
            closing_duration=CLOSING_DURATION_S,
            gap_duration=GAP_BLANK_SECONDS,
        )
        print(f"  📝 {ass_output}")
        print(f"  ⏱️  {_time.time() - t5:.1f}s")
    else:
        print("\n[5/6] Skipping subtitles (no --transcript)")

    # --- Step 6: Generate .kdenlive ---
    t6 = _time.time()
    base = os.path.splitext(input_path)[0]
    output_path = base + "-cortes.kdenlive"
    # ASS uses Kdenlive convention: {project}.kdenlive.ass
    if ass_output:
        ass_final = output_path + ".ass"
        os.replace(ass_output, ass_final)
        ass_output = ass_final
    print("\n[6/6] Generating vertical project...")
    generate_vertical_project(
        video_path=video_path,
        closing_path=args.closing or ep_config.closing,
        segments=segments,
        camera_segments=camera_segments,
        output_path=output_path,
        subtitle_path=ass_output,
        camera_positions=ep_config.cameras,
    )
    print(f"  📄 {output_path}")
    print(f"  ⏱️  {_time.time() - t6:.1f}s")

    # --- Summary ---
    total_time = _time.time() - t0
    print(f"\n{'=' * 60}")
    print(f"  ✅ Pipeline complete in {total_time:.1f}s")
    print(f"{'=' * 60}")
    print(f"  Clips: {len(segments)}")
    print(f"  Cameras: {len(camera_segments)} segments ({cam_summary})")
    print(f"  Speakers: {speaker_count}/{total} detected")
    print(f"  Subtitles: {'yes' if ass_output else 'no'}")
    print(f"  Output: {output_path}")
    print("\n  → Open in Kdenlive to review and render")
    print()


def _cmd_clips_from_pdf(args):
    """Generate clips.json from PDF cut suggestions."""
    from .llm import LLMConfig
    from .pdf_parser import define_boundaries_with_llm, extract_episode_cuts, parse_pdf
    from .subtitles import load_whisper_json

    print(f"📄 Parsing PDF: {args.pdf}")
    pdf_text = parse_pdf(args.pdf)

    print(f"🔍 Extracting cuts for: {args.episode}")
    cuts = extract_episode_cuts(pdf_text, args.episode)
    if not cuts:
        print(f"  ❌ No cuts found for episode '{args.episode}'")
        sys.exit(1)
    print(f"  Found {len(cuts)} cut suggestions")

    print(f"📝 Loading transcript: {args.transcript}")
    transcript_segs = load_whisper_json(args.transcript)

    llm_config = LLMConfig() if args.use_llm else None
    if llm_config:
        print("🤖 Using LLM for exact boundaries...")
    else:
        print("📐 Using heuristic boundaries (add --use-llm for better results)")

    clips = define_boundaries_with_llm(cuts, transcript_segs, args.offset, llm_config)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(clips, f, indent=2, ensure_ascii=False)

    total_dur = sum(c["end"] - c["start"] for c in clips)
    print(f"\n✅ Generated {len(clips)} clips ({total_dur:.0f}s total) → {args.output}")
    for i, c in enumerate(clips):
        dur = c["end"] - c["start"]
        print(f"  {i + 1:02d}. [{dur:3.0f}s] {c['title']}")


def _load_cache(path: str) -> dict:
    """Load cached intermediate results."""
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_cache(path: str, scenes, camera_segments: list[dict]):
    """Save intermediate results for reuse."""
    data = {
        "scenes": [{"timestamp": s.timestamp, "score": s.score} for s in scenes],
        "camera_segments": camera_segments,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


if __name__ == "__main__":
    main()
