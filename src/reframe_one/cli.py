"""CLI for reframe-one."""

import argparse
import os
import sys

from .kdenlive_gen import generate_vertical_project
from .parse_kdenlive import parse_project
from .scene_detect import classify_cameras, detect_scenes, save_scenes
from .subtitles import generate_karaoke_ass, load_whisper_json

CLOSING_PATH = "/home/claudio/Insync/ssd/papo-saude/00 Comum/fechamento papo podcast Insta.mp4"


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
    p_gen.add_argument("--closing", default=CLOSING_PATH, help="Closing video path")
    p_gen.add_argument("--threshold", type=float, default=0.3, help="Scene detection threshold")
    p_gen.add_argument("--clips", help="Time ranges to include (e.g. '0:30-1:45,3:00-4:20')")
    p_gen.add_argument("--clips-file", help="JSON file with clip selections")

    args = parser.parse_args()

    if args.command == "scenes":
        print(f"Detecting scenes in {args.video} (threshold={args.threshold})...")
        scenes = detect_scenes(args.video, args.threshold)
        save_scenes(scenes, args.output)
        print(f"Found {len(scenes)} scene changes → {args.output}")

    elif args.command == "subtitles":
        print(f"Generating karaoke ASS from {args.transcript}...")
        segments = load_whisper_json(args.transcript)
        generate_karaoke_ass(segments, args.output)
        print(f"Generated {args.output}")

    elif args.command == "generate":
        _cmd_generate(args)

    else:
        parser.print_help()
        sys.exit(1)


def _cmd_generate(args):
    """Generate vertical .kdenlive project."""
    input_path = args.input
    print(f"[1/5] Parsing project: {input_path}")
    project = parse_project(input_path)

    video_path = project.raw_video_path
    if not os.path.exists(video_path):
        print(f"ERROR: Raw video not found: {video_path}")
        sys.exit(1)

    segments = [{"start": s.in_seconds, "end": s.out_seconds} for s in project.segments]
    print(f"  Found {len(segments)} segments in source project")

    # Filter clips if specified
    if args.clips or args.clips_file:
        from .clip_selector import load_clips_file, parse_time_ranges, select_by_time_ranges

        if args.clips_file:
            time_ranges = load_clips_file(args.clips_file)
        else:
            time_ranges = parse_time_ranges(args.clips)
        segments = select_by_time_ranges(segments, time_ranges)
        print(f"  Filtered to {len(segments)} clips")

    print(f"[2/5] Detecting scenes in: {os.path.basename(video_path)}")
    scenes = detect_scenes(video_path, args.threshold)
    print(f"  Found {len(scenes)} scene changes")

    print("[3/6] Classifying cameras...")
    camera_segments = classify_cameras(video_path, scenes)
    print(f"  Classified {len(camera_segments)} camera segments")

    print("[4/6] Detecting speakers (lip movement)...")
    from .speaker_detect import detect_speaker_position, x_position_to_pan

    speaker_count = 0
    total = len(camera_segments)
    for idx, cs in enumerate(camera_segments):
        print(f"\r  [{idx + 1}/{total}] Analyzing...", end="", flush=True)
        if cs["end"] is None or (cs["end"] - cs["start"]) < 1.0:
            continue
        face_x = detect_speaker_position(video_path, cs["start"], cs["end"], num_frames=5)
        if face_x is not None:
            cs["pan_x"] = x_position_to_pan(face_x)
            speaker_count += 1
    print(f"\r  Detected speaker in {speaker_count}/{total} segments     ")

    # Generate ASS if transcript provided
    ass_output = ""
    if args.transcript:
        print("[5/6] Generating karaoke subtitles...")
        whisper_segs = load_whisper_json(args.transcript)
        base = os.path.splitext(input_path)[0]
        ass_output = base + "-cortes.ass"
        generate_karaoke_ass(whisper_segs, ass_output)
        print(f"  Generated: {ass_output}")
    else:
        print("[5/6] Skipping subtitles (no --transcript)")

    # Generate output path
    base = os.path.splitext(input_path)[0]
    output_path = base + "-cortes.kdenlive"

    print("[6/6] Generating vertical project...")
    generate_vertical_project(
        video_path=video_path,
        closing_path=args.closing,
        segments=segments,
        camera_segments=camera_segments,
        output_path=output_path,
        subtitle_path=ass_output,
    )
    print(f"  Output: {output_path}")
    print("Done!")


if __name__ == "__main__":
    main()
