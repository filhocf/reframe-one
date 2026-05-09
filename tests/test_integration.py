"""Integration tests for the full pipeline output structure."""

import tempfile
import xml.etree.ElementTree as ET

from reframe_one.kdenlive_gen import generate_vertical_project


def _generate_test_project(num_cameras=3):
    """Helper: generate a project with N camera segments."""
    total_dur = num_cameras * 30.0
    segments = [{"start": 0.0, "end": total_dur}]
    camera_segments = []
    cameras = ["entrevistadores", "entrevistada", "central"]
    for i in range(num_cameras):
        camera_segments.append(
            {
                "start": i * 30.0,
                "end": (i + 1) * 30.0,
                "camera": cameras[i % 3],
                "face_count": [2, 1, 3][i % 3],
            }
        )

    with tempfile.NamedTemporaryFile(suffix=".kdenlive", delete=False) as f:
        generate_vertical_project("/tmp/v.mp4", "/tmp/c.mp4", segments, camera_segments, f.name)
        return ET.parse(f.name)


def test_four_tracks_exist():
    """Project must have 4 tracks: A2, A1, V1, V2."""
    tree = _generate_test_project()
    root = tree.getroot()

    playlists = [pl.get("id") for pl in root.iter("playlist") if pl.get("id") != "main_bin"]
    # playlist0/1 = A2, playlist2/3 = A1, playlist4/5 = V1, playlist6/7 = V2
    assert "playlist0" in playlists
    assert "playlist2" in playlists
    assert "playlist4" in playlists
    assert "playlist6" in playlists


def test_a2_is_empty():
    """A2 (playlist0) must have no entries."""
    tree = _generate_test_project()
    pl0 = tree.find('.//playlist[@id="playlist0"]')
    assert len(pl0.findall("entry")) == 0


def test_v2_is_empty():
    """V2 (playlist6) must have no entries."""
    tree = _generate_test_project()
    pl6 = tree.find('.//playlist[@id="playlist6"]')
    assert len(pl6.findall("entry")) == 0


def test_v1_has_one_entry_per_camera():
    """V1 (playlist4) must have 1 entry per camera segment."""
    tree = _generate_test_project(num_cameras=5)
    pl4 = tree.find('.//playlist[@id="playlist4"]')
    video_entries = [e for e in pl4.findall("entry") if "chain3" in (e.get("producer") or "")]
    # 5 camera segments = 5 video entries
    assert len(video_entries) == 5


def test_a1_mirrors_v1_count():
    """A1 (playlist2) must have same number of entries as V1 video entries."""
    tree = _generate_test_project(num_cameras=4)
    pl2 = tree.find('.//playlist[@id="playlist2"]')
    pl4 = tree.find('.//playlist[@id="playlist4"]')

    a1_entries = pl2.findall("entry")
    v1_video_entries = [e for e in pl4.findall("entry") if "chain3" in (e.get("producer") or "")]

    # A1 has video entries + closing entries, V1 has video entries + closing entries
    # They should match
    assert len(a1_entries) == len(pl4.findall("entry"))


def test_each_v1_entry_has_qtblend():
    """Each video entry in V1 must have exactly 1 qtblend filter with 1 rect."""
    tree = _generate_test_project()
    pl4 = tree.find('.//playlist[@id="playlist4"]')
    video_entries = [e for e in pl4.findall("entry") if "chain3" in (e.get("producer") or "")]

    for entry in video_entries:
        qtblends = [
            f
            for f in entry.findall("filter")
            if any(
                p.text == "qtblend" for p in f.findall("property") if p.get("name") == "mlt_service"
            )
        ]
        assert len(qtblends) == 1, f"Expected 1 qtblend, got {len(qtblends)}"

        # Check it has exactly 1 rect (no semicolons = single keyframe)
        rect_prop = qtblends[0].find('.//property[@name="rect"]')
        assert rect_prop is not None
        assert ";" not in rect_prop.text, f"Expected single keyframe, got: {rect_prop.text}"


def test_rect_positions_match_cameras():
    """Rect X positions must correspond to camera type."""
    tree = _generate_test_project()
    pl4 = tree.find('.//playlist[@id="playlist4"]')
    video_entries = [e for e in pl4.findall("entry") if "chain3" in (e.get("producer") or "")]

    expected_x = [-1400, -1900, 0]  # entrevistadores, entrevistada, central

    for i, entry in enumerate(video_entries):
        qtblend = [
            f
            for f in entry.findall("filter")
            if any(
                p.text == "qtblend" for p in f.findall("property") if p.get("name") == "mlt_service"
            )
        ][0]
        rect = qtblend.find('.//property[@name="rect"]').text
        x_val = int(rect.split("=")[1].split()[0])
        assert x_val == expected_x[i], f"Entry {i}: expected X={expected_x[i]}, got X={x_val}"


def test_project_tractor_exists():
    """Must have a projectTractor."""
    tree = _generate_test_project()
    root = tree.getroot()

    project_tractors = []
    for tr in root.iter("tractor"):
        for p in tr.findall("property"):
            if p.get("name") == "kdenlive:projectTractor" and p.text == "1":
                project_tractors.append(tr)

    assert len(project_tractors) == 1


def test_closing_between_segments():
    """Closing video must appear between episode segments."""
    segments = [{"start": 0.0, "end": 30.0}, {"start": 40.0, "end": 70.0}]
    camera_segments = [
        {"start": 0.0, "end": 30.0, "camera": "entrevistadores", "face_count": 2},
        {"start": 40.0, "end": 70.0, "camera": "entrevistada", "face_count": 1},
    ]
    with tempfile.NamedTemporaryFile(suffix=".kdenlive", delete=False) as f:
        generate_vertical_project("/tmp/v.mp4", "/tmp/c.mp4", segments, camera_segments, f.name)
        tree = ET.parse(f.name)

    pl4 = tree.find('.//playlist[@id="playlist4"]')
    entries = pl4.findall("entry")
    producers = [e.get("producer") for e in entries]

    # Should have: chain3 (video), chain5 (closing), chain3 (video), chain5 (closing)
    assert "chain5" in producers, "Closing entry missing from V1"
    # At least 2 closing entries (one after each segment)
    closing_count = producers.count("chain5")
    assert closing_count == 2
