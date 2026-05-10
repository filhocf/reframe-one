"""Tests for clip_selector module."""

from reframe_one.clip_selector import (
    parse_time_ranges,
    select_by_time_ranges,
)

SEGMENTS = [
    {"start": 0.0, "end": 30.0},
    {"start": 30.0, "end": 90.0},
    {"start": 90.0, "end": 150.0},
    {"start": 150.0, "end": 210.0},
    {"start": 210.0, "end": 300.0},
]


def test_parse_time_ranges_basic():
    ranges = parse_time_ranges("0:30-1:45,3:00-4:20")
    assert len(ranges) == 2
    assert ranges[0] == (30.0, 105.0)
    assert ranges[1] == (180.0, 260.0)


def test_parse_time_ranges_single():
    ranges = parse_time_ranges("1:00-2:00")
    assert ranges == [(60.0, 120.0)]


def test_select_by_time_ranges_filters():
    ranges = [(25.0, 100.0)]  # overlaps segments 0,1,2
    selected = select_by_time_ranges(SEGMENTS, ranges)
    assert len(selected) == 3
    assert selected[0]["start"] == 0.0  # overlaps at 25-30
    assert selected[1]["start"] == 30.0
    assert selected[2]["start"] == 90.0


def test_select_by_time_ranges_no_overlap():
    ranges = [(500.0, 600.0)]
    selected = select_by_time_ranges(SEGMENTS, ranges)
    assert len(selected) == 0


def test_select_by_time_ranges_multiple():
    ranges = [(0.0, 35.0), (200.0, 250.0)]
    selected = select_by_time_ranges(SEGMENTS, ranges)
    # seg 0 (0-30 overlaps 0-35), seg 1 (30-90 overlaps 0-35),
    # seg 3 (150-210 overlaps 200-250), seg 4 (210-300 overlaps 200-250)
    assert len(selected) == 4


def test_select_all_when_range_covers_everything():
    ranges = [(0.0, 999.0)]
    selected = select_by_time_ranges(SEGMENTS, ranges)
    assert len(selected) == 5
