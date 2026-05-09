"""Generate Kdenlive project XML for vertical reframed clips."""

import xml.etree.ElementTree as ET
from dataclasses import dataclass


@dataclass
class PanKeyframe:
    time: str  # "HH:MM:SS.mmm"
    x: int
    y: int = -2112
    w: int = 3456
    h: int = 6144


# Standard positions for 320% zoom on 1920x1080 → 1080x1920
POSITIONS = {
    "central": PanKeyframe(time="", x=0, y=0, w=1080, h=1920),
    "entrevistadores": PanKeyframe(time="", x=-1400),
    "entrevistada": PanKeyframe(time="", x=-1900),
}


def seconds_to_timecode(seconds: float) -> str:
    """Convert seconds to Kdenlive timecode format."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def generate_qtblend_filter(keyframes: list[PanKeyframe]) -> ET.Element:
    """Generate a qtblend filter element with pan keyframes."""
    filt = ET.Element("filter")
    ET.SubElement(filt, "property", name="mlt_service").text = "qtblend"
    ET.SubElement(filt, "property", name="kdenlive_id").text = "qtblend"
    ET.SubElement(filt, "property", name="rotation").text = "0"

    for kf in keyframes:
        prop = ET.SubElement(filt, "property", name="rect")
        prop.text = f"{kf.time}={kf.x} {kf.y} {kf.w} {kf.h} 1.000000"

    return filt


def generate_vertical_project(
    video_path: str,
    closing_path: str,
    clips: list[dict],
    keyframes: list[PanKeyframe],
    output_path: str,
):
    """Generate a Kdenlive project XML for vertical clips.

    Args:
        video_path: path to source video (bruto)
        closing_path: path to closing video (fechamento Instagram)
        clips: list of {start, end, title} for each clip segment
        keyframes: list of PanKeyframe for pan positions
        output_path: where to save the .kdenlive file
    """
    # TODO: implement full MLT XML generation
    # For now, this is the skeleton
    root = ET.Element("mlt", {
        "LC_NUMERIC": "C",
        "producer": "main_bin",
        "root": "",
        "version": "7.38.0",
    })

    # Vertical profile
    ET.SubElement(root, "profile", {
        "colorspace": "709",
        "description": "Vertical HD 30 fps",
        "display_aspect_den": "16",
        "display_aspect_num": "9",
        "frame_rate_den": "1",
        "frame_rate_num": "30",
        "height": "1920",
        "progressive": "1",
        "sample_aspect_den": "1",
        "sample_aspect_num": "1",
        "width": "1080",
    })

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(output_path, encoding="utf-8", xml_declaration=True)
