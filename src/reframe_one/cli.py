"""CLI for reframe-one."""

import argparse
import sys

from .scene_detect import detect_scenes, save_scenes
from .subtitles import generate_karaoke_ass, load_whisper_json


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

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
