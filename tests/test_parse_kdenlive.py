"""Tests for parse_kdenlive module."""

import tempfile
import xml.etree.ElementTree as ET

from reframe_one.parse_kdenlive import parse_project


def _make_minimal_kdenlive(video_path="video.mp4", abertura_path="abertura.mp4"):
    """Create a minimal .kdenlive XML for testing."""
    root = ET.Element("mlt", root="/tmp/test", version="7.38.0", producer="main_bin")
    ET.SubElement(
        root, "profile", frame_rate_num="30000", frame_rate_den="1001", width="1920", height="1080"
    )

    # Abertura chain
    c0 = ET.SubElement(root, "chain", id="chain0", out="00:00:03.704")
    p = ET.SubElement(c0, "property", name="resource")
    p.text = abertura_path

    # Video chain
    c1 = ET.SubElement(root, "chain", id="chain1", out="00:23:00.000")
    p = ET.SubElement(c1, "property", name="resource")
    p.text = video_path

    # Playlist with entries
    pl = ET.SubElement(root, "playlist", id="playlist0")
    ET.SubElement(
        pl, "entry", **{"in": "00:00:02.000", "out": "00:10:00.000", "producer": "chain1"}
    )
    ET.SubElement(
        pl, "entry", **{"in": "00:10:30.000", "out": "00:20:00.000", "producer": "chain1"}
    )

    return ET.tostring(root, encoding="unicode")


def test_parse_project_extracts_video_path():
    xml = _make_minimal_kdenlive("bruto.mp4", "abertura papo podcast YT.mp4")
    with tempfile.NamedTemporaryFile(suffix=".kdenlive", mode="w", delete=False) as f:
        f.write(xml)
        f.flush()
        info = parse_project(f.name)

    assert info.raw_video_path.endswith("bruto.mp4")


def test_parse_project_identifies_abertura():
    xml = _make_minimal_kdenlive("bruto.mp4", "abertura papo podcast YT.mp4")
    with tempfile.NamedTemporaryFile(suffix=".kdenlive", mode="w", delete=False) as f:
        f.write(xml)
        f.flush()
        info = parse_project(f.name)

    assert "abertura" in info.abertura_path


def test_parse_project_extracts_segments():
    xml = _make_minimal_kdenlive()
    with tempfile.NamedTemporaryFile(suffix=".kdenlive", mode="w", delete=False) as f:
        f.write(xml)
        f.flush()
        info = parse_project(f.name)

    assert len(info.segments) == 2
    assert info.segments[0].in_seconds < info.segments[0].out_seconds
