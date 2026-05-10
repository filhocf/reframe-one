"""Tests for kdenlive_gen module."""

import tempfile
import xml.etree.ElementTree as ET

from reframe_one.kdenlive_gen import generate_vertical_project


def test_generate_vertical_project_creates_valid_xml():
    segments = [{"start": 2.0, "end": 60.0}]
    camera_segments = [
        {"start": 2.0, "end": 30.0, "camera": "entrevistadores", "face_count": 2},
        {"start": 30.0, "end": 60.0, "camera": "entrevistada", "face_count": 1},
    ]
    with tempfile.NamedTemporaryFile(suffix=".kdenlive", delete=False) as f:
        generate_vertical_project(
            video_path="/tmp/video.mp4",
            closing_path="/tmp/closing.mp4",
            segments=segments,
            camera_segments=camera_segments,
            output_path=f.name,
        )
        tree = ET.parse(f.name)
        root = tree.getroot()

    assert root.tag == "mlt"


def test_vertical_profile():
    segments = [{"start": 0.0, "end": 30.0}]
    camera_segments = [{"start": 0.0, "end": 30.0, "camera": "central", "face_count": 3}]
    with tempfile.NamedTemporaryFile(suffix=".kdenlive", delete=False) as f:
        generate_vertical_project("/tmp/v.mp4", "/tmp/c.mp4", segments, camera_segments, f.name)
        tree = ET.parse(f.name)
        profile = tree.find("profile")

    assert profile.get("width") == "1080"
    assert profile.get("height") == "1920"


def test_hard_cuts_one_entry_per_camera():
    segments = [{"start": 0.0, "end": 60.0}]
    camera_segments = [
        {"start": 0.0, "end": 20.0, "camera": "entrevistadores", "face_count": 2},
        {"start": 20.0, "end": 40.0, "camera": "entrevistada", "face_count": 1},
        {"start": 40.0, "end": 60.0, "camera": "central", "face_count": 3},
    ]
    with tempfile.NamedTemporaryFile(suffix=".kdenlive", delete=False) as f:
        generate_vertical_project("/tmp/v.mp4", "/tmp/c.mp4", segments, camera_segments, f.name)
        tree = ET.parse(f.name)

    # Find video playlist (playlist4)
    pl4 = tree.find('.//playlist[@id="playlist4"]')
    video_entries = [e for e in pl4.findall("entry") if "chain3" in (e.get("producer") or "")]

    # 3 camera segments + 1 closing = 4 entries, but video entries = 3
    assert len(video_entries) == 3


def test_consistent_uuids():
    segments = [{"start": 0.0, "end": 30.0}]
    camera_segments = [{"start": 0.0, "end": 30.0, "camera": "central", "face_count": 3}]
    with tempfile.NamedTemporaryFile(suffix=".kdenlive", delete=False) as f:
        generate_vertical_project("/tmp/v.mp4", "/tmp/c.mp4", segments, camera_segments, f.name)
        tree = ET.parse(f.name)

    # All chains with kdenlive:id=4 should have same control_uuid
    uuids = set()
    for chain in tree.iter("chain"):
        kid = chain.find('.//property[@name="kdenlive:id"]')
        uuid_prop = chain.find('.//property[@name="kdenlive:control_uuid"]')
        if kid is not None and kid.text == "4" and uuid_prop is not None:
            uuids.add(uuid_prop.text)

    assert len(uuids) == 1, f"Expected 1 UUID for video chains, got {len(uuids)}: {uuids}"


def test_subtitle_filter_added_when_path_provided():
    """When subtitle_path is given, avfilter.subtitles should be in tractor."""
    import tempfile
    import xml.etree.ElementTree as ET

    from reframe_one.kdenlive_gen import generate_vertical_project

    segments = [{"start": 0.0, "end": 5.0}]
    cameras = [{"start": 0.0, "end": 5.0, "camera": "central"}]

    with (
        tempfile.NamedTemporaryFile(suffix=".mp4") as vid,
        tempfile.NamedTemporaryFile(suffix=".mp4") as closing,
        tempfile.NamedTemporaryFile(suffix=".kdenlive", delete=False) as out,
    ):
        generate_vertical_project(
            vid.name,
            closing.name,
            segments,
            cameras,
            out.name,
            subtitle_path="/tmp/test.ass",
        )
        tree = ET.parse(out.name)

    root = tree.getroot()
    # Find avfilter.subtitles
    filters = root.findall(".//filter")
    sub_filters = [
        f
        for f in filters
        if f.find('property[@name="mlt_service"]') is not None
        and f.find('property[@name="mlt_service"]').text == "avfilter.subtitles"
    ]
    assert len(sub_filters) == 1
    filename_prop = sub_filters[0].find('property[@name="av.filename"]')
    assert filename_prop.text == "test.ass"


def test_no_subtitle_filter_when_path_empty():
    """When subtitle_path is empty, no subtitle filter should exist."""
    import tempfile
    import xml.etree.ElementTree as ET

    from reframe_one.kdenlive_gen import generate_vertical_project

    segments = [{"start": 0.0, "end": 5.0}]
    cameras = [{"start": 0.0, "end": 5.0, "camera": "central"}]

    with (
        tempfile.NamedTemporaryFile(suffix=".mp4") as vid,
        tempfile.NamedTemporaryFile(suffix=".mp4") as closing,
        tempfile.NamedTemporaryFile(suffix=".kdenlive", delete=False) as out,
    ):
        generate_vertical_project(
            vid.name,
            closing.name,
            segments,
            cameras,
            out.name,
        )
        tree = ET.parse(out.name)

    root = tree.getroot()
    filters = root.findall(".//filter")
    sub_filters = [
        f
        for f in filters
        if f.find('property[@name="mlt_service"]') is not None
        and f.find('property[@name="mlt_service"]').text == "avfilter.subtitles"
    ]
    assert len(sub_filters) == 0
