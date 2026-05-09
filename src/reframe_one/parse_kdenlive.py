"""Parse Kdenlive (.kdenlive) project files (MLT XML format)."""

import json
import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field


@dataclass
class Segment:
    in_seconds: float
    out_seconds: float


@dataclass
class Guide:
    pos_seconds: float
    comment: str


@dataclass
class ProjectInfo:
    root: str
    raw_video_path: str
    abertura_path: str
    segments: list[Segment] = field(default_factory=list)
    guides: list[Guide] = field(default_factory=list)


def _tc_to_seconds(tc: str) -> float:
    """Convert HH:MM:SS.mmm timecode to seconds."""
    h, m, rest = tc.split(":")
    return int(h) * 3600 + int(m) * 60 + float(rest)


def _get_property(element: ET.Element, name: str) -> str | None:
    for prop in element.findall("property"):
        if prop.get("name") == name:
            return prop.text
    return None


def parse_project(path: str) -> ProjectInfo:
    tree = ET.parse(path)
    mlt = tree.getroot()

    root = mlt.get("root", "")

    # FPS from profile
    profile = mlt.find("profile")
    fps = int(profile.get("frame_rate_num", "30000")) / int(profile.get("frame_rate_den", "1001"))

    # Collect chain/producer resources
    chains: dict[str, str] = {}
    for tag in ("chain", "producer"):
        for el in mlt.findall(tag):
            res = _get_property(el, "resource")
            if res:
                chains[el.get("id")] = res

    # Identify abertura and raw video
    abertura_path = ""
    raw_video_path = ""
    raw_video_id = ""

    for cid, res in chains.items():
        if not res.endswith(".mp4"):
            continue
        if "abertura" in res.lower():
            abertura_path = res if os.path.isabs(res) else os.path.join(root, res)
        else:
            raw_video_path = res if os.path.isabs(res) else os.path.join(root, res)
            raw_video_id = cid

    # Find the first playlist that has entries referencing the raw video chain
    # Kdenlive duplicates chains (chain4->chain1, chain5->chain0), so match by kdenlive:id
    raw_kdenlive_id = None
    for tag in ("chain", "producer"):
        for el in mlt.findall(tag):
            if el.get("id") == raw_video_id:
                raw_kdenlive_id = _get_property(el, "kdenlive:id")
                break
        if raw_kdenlive_id:
            break

    # Find all chain IDs that share the same kdenlive:id (duplicates for timeline use)
    raw_chain_ids = set()
    for tag in ("chain", "producer"):
        for el in mlt.findall(tag):
            if _get_property(el, "kdenlive:id") == raw_kdenlive_id:
                raw_chain_ids.add(el.get("id"))

    # Extract segments from the first playlist containing raw video entries
    segments: list[Segment] = []
    for playlist in mlt.iter("playlist"):
        pid = playlist.get("id", "")
        if pid == "main_bin":
            continue
        found = False
        for entry in playlist.findall("entry"):
            if entry.get("producer") in raw_chain_ids:
                found = True
                in_s = _tc_to_seconds(entry.get("in"))
                out_s = _tc_to_seconds(entry.get("out"))
                segments.append(Segment(in_seconds=in_s, out_seconds=out_s))
        if found:
            break

    # Extract guides
    guides: list[Guide] = []
    for prop in mlt.iter("property"):
        if prop.get("name") == "kdenlive:sequenceproperties.guides":
            text = (prop.text or "").strip()
            if text and text != "[]":
                for g in json.loads(text):
                    pos_frames = g.get("pos", 0)
                    guides.append(Guide(
                        pos_seconds=round(pos_frames / fps, 3),
                        comment=g.get("comment", ""),
                    ))
            break

    return ProjectInfo(
        root=root,
        raw_video_path=raw_video_path,
        abertura_path=abertura_path,
        segments=segments,
        guides=guides,
    )
