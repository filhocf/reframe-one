"""Generate Kdenlive project XML for vertical reframed clips."""

import os
import uuid
import xml.etree.ElementTree as ET

# Camera positions for qtblend rect
CAMERA_POSITIONS = {
    "central": (-1200, -2112, 3456, 6144),  # zoom, centered between both
    "entrevistadores": (-1400, -2112, 3456, 6144),
    "entrevistada": (-1900, -2112, 3456, 6144),
    "unknown": (-1400, -2112, 3456, 6144),
}

CLOSING_LENGTH_TC = "00:00:03.800"
CLOSING_LENGTH_FRAMES = 115


def _tc(seconds: float) -> str:
    """Convert seconds to HH:MM:SS.mmm timecode."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def _prop(parent: ET.Element, name: str, text: str = ""):
    p = ET.SubElement(parent, "property", name=name)
    p.text = text
    return p


def _make_chain(
    parent,
    chain_id,
    resource,
    is_video=True,
    kdenlive_id="4",
    out_tc="00:23:32.600",
    length_tc="00:23:32.633",
    test_audio="0",
    test_image="1",
    control_uuid=None,
):
    """Create a chain element for timeline use."""
    chain = ET.SubElement(parent, "chain", id=chain_id, out=out_tc)
    _prop(chain, "length", length_tc)
    _prop(chain, "eof", "pause")
    _prop(chain, "resource", resource)
    _prop(chain, "mlt_service", "avformat-novalidate")
    _prop(chain, "seekable", "1")
    _prop(chain, "format", "3")
    _prop(chain, "audio_index", "1")
    _prop(chain, "video_index", "0")
    _prop(chain, "vstream", "0")
    _prop(chain, "astream", "0")
    _prop(chain, "kdenlive:folderid", "-1")
    _prop(chain, "kdenlive:id", kdenlive_id)
    _prop(chain, "kdenlive:control_uuid", control_uuid or ("{" + str(uuid.uuid4()) + "}"))
    _prop(chain, "mute_on_pause", "0")
    _prop(chain, "kdenlive:clip_type", "0")
    _prop(chain, "set.test_audio", test_audio)
    _prop(chain, "set.test_image", test_image)
    return chain


def _get_camera_at(camera_segments: list[dict], time_s: float) -> str:
    """Find which camera is active at a given time."""
    for seg in camera_segments:
        if seg["start"] <= time_s:
            end = seg.get("end")
            if end is None or time_s < end:
                return seg["camera"]
    return "unknown"


def _make_qtblend_filter(parent, filter_id, seg_start, seg_end, camera_segments):
    """Create a qtblend filter with multiple keyframes based on camera changes within segment."""
    # Find all camera changes within this segment's time range
    keyframes = []
    for cs in camera_segments:
        # Camera segment overlaps with our entry
        if cs["end"] is not None and cs["start"] < seg_end and cs["end"] > seg_start:
            # Keyframe time is relative to the entry's in-point in Kdenlive
            kf_time = max(cs["start"], seg_start)
            x, y, w, h = CAMERA_POSITIONS.get(cs["camera"], CAMERA_POSITIONS["unknown"])
            keyframes.append((kf_time, x, y, w, h))
        elif cs["end"] is None and cs["start"] >= seg_start and cs["start"] < seg_end:
            kf_time = cs["start"]
            x, y, w, h = CAMERA_POSITIONS.get(cs["camera"], CAMERA_POSITIONS["unknown"])
            keyframes.append((kf_time, x, y, w, h))

    # If no keyframes found, use fallback
    if not keyframes:
        x, y, w, h = CAMERA_POSITIONS["unknown"]
        keyframes = [(seg_start, x, y, w, h)]

    filt = ET.SubElement(parent, "filter", id=filter_id)
    _prop(filt, "rotate_center", "1")
    _prop(filt, "mlt_service", "qtblend")
    _prop(filt, "kdenlive_id", "qtblend")
    _prop(filt, "compositing", "0")
    _prop(filt, "distort", "0")

    # Generate rect with all keyframes (each on its own property line, or semicolon-separated)
    # Kdenlive uses ONE rect property with multiple keyframes separated by semicolons
    # Format: "TC1=X Y W H opacity;TC2=X Y W H opacity"
    rect_parts = []
    for kf_time, x, y, w, h in keyframes:
        tc = _tc(kf_time)
        rect_parts.append(f"{tc}={x} {y} {w} {h} 1.000000")

    _prop(filt, "rect", ";".join(rect_parts))
    _prop(filt, "rotation", f"{_tc(seg_start)}=0")
    _prop(filt, "kdenlive:collapsed", "0")
    return filt


def _build_audio_playlist(playlist, segments, camera_segments, video_chain, closing_chain):
    """Build audio playlist mirroring video entries (same cuts as V1)."""
    for seg in segments:
        # Same camera segments as video
        seg_cameras = []
        for cs in camera_segments:
            cs_end = cs["end"] if cs["end"] is not None else seg["end"]
            if cs["start"] < seg["end"] and cs_end > seg["start"]:
                entry_start = max(cs["start"], seg["start"])
                entry_end = min(cs_end, seg["end"])
                if entry_end > entry_start + 0.1:
                    seg_cameras.append({"start": entry_start, "end": entry_end})

        if not seg_cameras:
            seg_cameras = [{"start": seg["start"], "end": seg["end"]}]

        for cam_seg in seg_cameras:
            entry = ET.SubElement(
                playlist,
                "entry",
                **{
                    "in": _tc(cam_seg["start"]),
                    "out": _tc(cam_seg["end"]),
                    "producer": video_chain,
                },
            )
            _prop(entry, "kdenlive:id", "4")

        # Closing after each episode segment
        c_entry = ET.SubElement(
            playlist,
            "entry",
            **{"in": "00:00:00.000", "out": CLOSING_LENGTH_TC, "producer": closing_chain},
        )
        _prop(c_entry, "kdenlive:id", "5")


def _build_video_playlist(
    playlist, segments, camera_segments, video_chain, closing_chain, filter_counter
):
    """Build video playlist with one entry per camera segment (hard cuts)."""
    for seg_idx, seg in enumerate(segments):
        # Find all camera segments that overlap with this episode segment
        seg_cameras = []
        for cs in camera_segments:
            cs_end = cs["end"] if cs["end"] is not None else seg["end"]
            if cs["start"] < seg["end"] and cs_end > seg["start"]:
                # Clip to segment boundaries
                entry_start = max(cs["start"], seg["start"])
                entry_end = min(cs_end, seg["end"])
                if entry_end > entry_start + 0.1:  # skip tiny segments
                    seg_cameras.append(
                        {
                            "start": entry_start,
                            "end": entry_end,
                            "camera": cs["camera"],
                        }
                    )

        # If no camera segments found, use entire segment with fallback
        if not seg_cameras:
            seg_cameras = [{"start": seg["start"], "end": seg["end"], "camera": "unknown"}]

        # Generate one entry per camera segment (hard cut between positions)
        for i, cam_seg in enumerate(seg_cameras):
            in_tc = _tc(cam_seg["start"])
            out_tc = _tc(cam_seg["end"])
            x, y, w, h = CAMERA_POSITIONS.get(cam_seg["camera"], CAMERA_POSITIONS["unknown"])

            entry = ET.SubElement(
                playlist, "entry", **{"in": in_tc, "out": out_tc, "producer": video_chain}
            )
            _prop(entry, "kdenlive:id", "4")

            # Fade from black on first entry of first segment
            if seg_idx == 0 and i == 0:
                f = ET.SubElement(
                    entry,
                    "filter",
                    id=f"filter{filter_counter[0]}",
                    **{"in": in_tc, "out": _tc(cam_seg["start"] + 0.5)},
                )
                filter_counter[0] += 1
                _prop(f, "start", "1")
                _prop(f, "level", "1")
                _prop(f, "mlt_service", "brightness")
                _prop(f, "kdenlive_id", "fade_from_black")
                _prop(f, "alpha", "00:00:00.000=0;00:00:00.501=1")

            # qtblend filter with single fixed position (hard cut, no interpolation)
            fid = f"filter{filter_counter[0]}"
            filter_counter[0] += 1
            filt = ET.SubElement(entry, "filter", id=fid)
            _prop(filt, "rotate_center", "1")
            _prop(filt, "mlt_service", "qtblend")
            _prop(filt, "kdenlive_id", "qtblend")
            _prop(filt, "compositing", "0")
            _prop(filt, "distort", "0")
            _prop(filt, "rect", f"{in_tc}={x} {y} {w} {h} 1.000000")
            _prop(filt, "rotation", f"{in_tc}=0")
            _prop(filt, "kdenlive:collapsed", "0")

        # Fade to black on last camera segment of this episode segment
        last_entry = playlist[-1]
        f = ET.SubElement(
            last_entry,
            "filter",
            id=f"filter{filter_counter[0]}",
            **{"in": _tc(seg["end"] - 0.167), "out": _tc(seg["end"])},
        )
        filter_counter[0] += 1
        _prop(f, "start", "1")
        _prop(f, "level", "1")
        _prop(f, "mlt_service", "brightness")
        _prop(f, "kdenlive_id", "fade_to_black")
        _prop(f, "alpha", "00:00:00.000=1;00:00:00.167=0")

        # Closing entry after each episode segment
        c_entry = ET.SubElement(
            playlist,
            "entry",
            **{"in": "00:00:00.000", "out": CLOSING_LENGTH_TC, "producer": closing_chain},
        )
        _prop(c_entry, "kdenlive:id", "5")
        f = ET.SubElement(c_entry, "filter", id=f"filter{filter_counter[0]}", out="00:00:00.167")
        filter_counter[0] += 1
        _prop(f, "start", "1")
        _prop(f, "level", "1")
        _prop(f, "mlt_service", "brightness")
        _prop(f, "kdenlive_id", "fade_from_black")
        _prop(f, "alpha", "00:00:00.000=0;00:00:00.167=1")
        f = ET.SubElement(
            c_entry,
            "filter",
            id=f"filter{filter_counter[0]}",
            **{"in": "00:00:03.633", "out": CLOSING_LENGTH_TC},
        )
        filter_counter[0] += 1
        _prop(f, "start", "1")
        _prop(f, "level", "1")
        _prop(f, "mlt_service", "brightness")
        _prop(f, "kdenlive_id", "fade_to_black")
        _prop(f, "alpha", "0=1;-1=0")


def generate_vertical_project(
    video_path: str,
    closing_path: str,
    segments: list[dict],
    camera_segments: list[dict],
    output_path: str,
):
    """Generate a complete Kdenlive .kdenlive project for vertical cuts.

    Args:
        video_path: absolute path to raw video
        closing_path: absolute path to closing video
        segments: list of {start: float, end: float} in seconds
        camera_segments: list of {start: float, end: float, camera: str}
        output_path: where to save the .kdenlive file
    """
    root_dir = os.path.dirname(video_path)
    video_basename = os.path.basename(video_path)
    seq_uuid = "{" + str(uuid.uuid4()) + "}"
    doc_id = str(int(__import__("time").time() * 1000))

    # Compute total duration from segments + closings
    last_seg = segments[-1] if segments else {"start": 0, "end": 60}
    video_out_tc = _tc(last_seg["end"])
    video_length_tc = _tc(last_seg["end"] + 0.033)

    # Total timeline duration estimate
    total_dur = sum(s["end"] - s["start"] for s in segments) + 3.8 * len(segments)
    total_out_tc = _tc(total_dur)

    # --- Build MLT root ---
    mlt = ET.Element(
        "mlt",
        {
            "LC_NUMERIC": "C",
            "producer": "main_bin",
            "root": root_dir,
            "version": "7.38.0",
        },
    )

    # Profile
    ET.SubElement(
        mlt,
        "profile",
        {
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
        },
    )

    # --- Fixed UUIDs for clip consistency ---
    video_uuid = "{" + str(uuid.uuid4()) + "}"
    closing_uuid = "{" + str(uuid.uuid4()) + "}"

    # --- Bin chains (chain4=video, chain7=closing) ---
    chain4 = ET.SubElement(mlt, "chain", id="chain4", out=video_out_tc)
    _prop(chain4, "length", video_length_tc)
    _prop(chain4, "eof", "pause")
    _prop(chain4, "resource", video_basename)
    _prop(chain4, "mlt_service", "avformat-novalidate")
    _prop(chain4, "meta.media.nb_streams", "2")
    _prop(chain4, "meta.media.0.stream.type", "video")
    _prop(chain4, "meta.media.0.codec.width", "1920")
    _prop(chain4, "meta.media.0.codec.height", "1080")
    _prop(chain4, "meta.media.0.codec.name", "h264")
    _prop(chain4, "meta.media.1.stream.type", "audio")
    _prop(chain4, "meta.media.1.codec.channels", "2")
    _prop(chain4, "meta.media.1.codec.sample_rate", "48000")
    _prop(chain4, "seekable", "1")
    _prop(chain4, "format", "3")
    _prop(chain4, "audio_index", "1")
    _prop(chain4, "video_index", "0")
    _prop(chain4, "kdenlive:folderid", "-1")
    _prop(chain4, "kdenlive:id", "4")
    _prop(chain4, "kdenlive:clip_type", "0")
    _prop(chain4, "kdenlive:control_uuid", video_uuid)
    _prop(chain4, "mute_on_pause", "0")

    chain7 = ET.SubElement(mlt, "chain", id="chain7", out=CLOSING_LENGTH_TC)
    _prop(chain7, "length", str(CLOSING_LENGTH_FRAMES))
    _prop(chain7, "eof", "pause")
    _prop(chain7, "resource", closing_path)
    _prop(chain7, "mlt_service", "avformat-novalidate")
    _prop(chain7, "meta.media.nb_streams", "2")
    _prop(chain7, "meta.media.0.stream.type", "video")
    _prop(chain7, "meta.media.0.codec.width", "720")
    _prop(chain7, "meta.media.0.codec.height", "1280")
    _prop(chain7, "meta.media.1.stream.type", "audio")
    _prop(chain7, "meta.media.1.codec.channels", "2")
    _prop(chain7, "seekable", "1")
    _prop(chain7, "format", "3")
    _prop(chain7, "audio_index", "1")
    _prop(chain7, "video_index", "0")
    _prop(chain7, "kdenlive:folderid", "-1")
    _prop(chain7, "kdenlive:id", "5")
    _prop(chain7, "kdenlive:clip_type", "0")
    _prop(chain7, "kdenlive:control_uuid", closing_uuid)
    _prop(chain7, "mute_on_pause", "0")

    # --- Black producer ---
    prod0 = ET.SubElement(
        mlt, "producer", id="producer0", **{"in": "00:00:00.000", "out": total_out_tc}
    )
    _prop(prod0, "length", "2147483647")
    _prop(prod0, "eof", "continue")
    _prop(prod0, "resource", "black")
    _prop(prod0, "aspect_ratio", "1")
    _prop(prod0, "mlt_service", "color")
    _prop(prod0, "kdenlive:playlistid", "black_track")
    _prop(prod0, "mlt_image_format", "rgba")
    _prop(prod0, "set.test_audio", "0")

    # --- Audio track chains (chain0=video audio for A2, chain1=video audio for A1) ---
    _make_chain(
        mlt,
        "chain0",
        video_basename,
        kdenlive_id="4",
        control_uuid=video_uuid,
        out_tc=video_out_tc,
        length_tc=video_length_tc,
        test_audio="0",
        test_image="1",
    )

    # --- Audio playlists: A2 (playlist0) = EMPTY, playlist1 = blank ---
    pl0 = ET.SubElement(mlt, "playlist", id="playlist0")
    _prop(pl0, "kdenlive:audio_track", "1")

    pl1 = ET.SubElement(mlt, "playlist", id="playlist1")
    _prop(pl1, "kdenlive:audio_track", "1")

    # --- Audio tractor (tractor0) ---
    tractor0 = ET.SubElement(
        mlt, "tractor", id="tractor0", **{"in": "00:00:00.000", "out": total_out_tc}
    )
    _prop(tractor0, "kdenlive:audio_track", "1")
    _prop(tractor0, "kdenlive:trackheight", "62")
    _prop(tractor0, "kdenlive:timeline_active", "1")
    _prop(tractor0, "kdenlive:collapsed", "0")
    _prop(tractor0, "kdenlive:track_name", "A2")
    ET.SubElement(tractor0, "track", hide="video", producer="playlist0")
    ET.SubElement(tractor0, "track", hide="video", producer="playlist1")
    # Standard audio filters
    f = ET.SubElement(tractor0, "filter", id="filter0")
    _prop(f, "mlt_service", "volume")
    _prop(f, "internal_added", "237")
    _prop(f, "disable", "1")
    f = ET.SubElement(tractor0, "filter", id="filter1")
    _prop(f, "mlt_service", "panner")
    _prop(f, "internal_added", "237")
    _prop(f, "start", "0.5")
    _prop(f, "disable", "1")

    # --- Video timeline chains ---
    # chain1 = video for audio track (playlist2)
    _make_chain(
        mlt,
        "chain1",
        video_basename,
        kdenlive_id="4",
        control_uuid=video_uuid,
        out_tc=video_out_tc,
        length_tc=video_length_tc,
        test_audio="0",
        test_image="1",
    )
    # chain2 = closing for audio track
    _make_chain(
        mlt,
        "chain2",
        closing_path,
        kdenlive_id="5",
        control_uuid=closing_uuid,
        out_tc=CLOSING_LENGTH_TC,
        length_tc=str(CLOSING_LENGTH_FRAMES),
        test_audio="0",
        test_image="1",
    )

    # --- playlist2: audio track for video timeline ---
    pl2 = ET.SubElement(mlt, "playlist", id="playlist2")
    _prop(pl2, "kdenlive:audio_track", "1")
    _build_audio_playlist(pl2, segments, camera_segments, "chain1", "chain2")

    pl3 = ET.SubElement(mlt, "playlist", id="playlist3")
    _prop(pl3, "kdenlive:audio_track", "1")

    # --- tractor1: audio for video timeline ---
    tractor1 = ET.SubElement(
        mlt, "tractor", id="tractor1", **{"in": "00:00:00.000", "out": total_out_tc}
    )
    _prop(tractor1, "kdenlive:audio_track", "1")
    _prop(tractor1, "kdenlive:trackheight", "67")
    _prop(tractor1, "kdenlive:timeline_active", "1")
    _prop(tractor1, "kdenlive:collapsed", "0")
    ET.SubElement(tractor1, "track", hide="video", producer="playlist2")
    ET.SubElement(tractor1, "track", hide="video", producer="playlist3")
    f = ET.SubElement(tractor1, "filter", id="filter2")
    _prop(f, "mlt_service", "volume")
    _prop(f, "internal_added", "237")
    _prop(f, "disable", "1")
    f = ET.SubElement(tractor1, "filter", id="filter3")
    _prop(f, "mlt_service", "panner")
    _prop(f, "internal_added", "237")
    _prop(f, "start", "0.5")
    _prop(f, "disable", "1")

    # --- Video track chains ---
    # chain3 = video for video track (playlist4)
    _make_chain(
        mlt,
        "chain3",
        video_basename,
        kdenlive_id="4",
        control_uuid=video_uuid,
        out_tc=video_out_tc,
        length_tc=video_length_tc,
        test_audio="1",
        test_image="0",
    )
    # chain5 = closing for video track
    _make_chain(
        mlt,
        "chain5",
        closing_path,
        kdenlive_id="5",
        control_uuid=closing_uuid,
        out_tc=CLOSING_LENGTH_TC,
        length_tc=str(CLOSING_LENGTH_FRAMES),
        test_audio="1",
        test_image="0",
    )

    # --- playlist4: video track with qtblend filters ---
    pl4 = ET.SubElement(mlt, "playlist", id="playlist4")
    filter_counter = [10]  # mutable counter for filter IDs
    _build_video_playlist(pl4, segments, camera_segments, "chain3", "chain5", filter_counter)

    _ = ET.SubElement(mlt, "playlist", id="playlist5")

    # --- tractor2: video track V1 ---
    tractor2 = ET.SubElement(
        mlt, "tractor", id="tractor2", **{"in": "00:00:00.000", "out": total_out_tc}
    )
    _prop(tractor2, "kdenlive:trackheight", "67")
    _prop(tractor2, "kdenlive:timeline_active", "1")
    _prop(tractor2, "kdenlive:collapsed", "0")
    ET.SubElement(tractor2, "track", hide="audio", producer="playlist4")
    ET.SubElement(tractor2, "track", hide="audio", producer="playlist5")

    # --- V2 empty (playlist6/7 + tractor3) ---
    _ = ET.SubElement(mlt, "playlist", id="playlist6")
    _ = ET.SubElement(mlt, "playlist", id="playlist7")
    tractor3 = ET.SubElement(
        mlt, "tractor", id="tractor3", **{"in": "00:00:00.000", "out": total_out_tc}
    )
    _prop(tractor3, "kdenlive:trackheight", "67")
    _prop(tractor3, "kdenlive:timeline_active", "1")
    _prop(tractor3, "kdenlive:collapsed", "0")
    ET.SubElement(tractor3, "track", hide="audio", producer="playlist6")
    ET.SubElement(tractor3, "track", hide="audio", producer="playlist7")

    # --- Main sequence tractor (tractor4) ---
    tractor4 = ET.SubElement(
        mlt, "tractor", id="tractor4", **{"in": "00:00:00.000", "out": total_out_tc}
    )
    _prop(tractor4, "kdenlive:duration", _tc(total_dur + 0.033))
    _prop(tractor4, "kdenlive:clipname", "Sequência 1")
    _prop(tractor4, "kdenlive:description", "")
    _prop(tractor4, "kdenlive:uuid", seq_uuid)
    _prop(tractor4, "kdenlive:producer_type", "17")
    _prop(tractor4, "kdenlive:control_uuid", "{" + str(uuid.uuid4()) + "}")
    _prop(tractor4, "kdenlive:id", "3")
    _prop(tractor4, "kdenlive:clip_type", "0")
    _prop(tractor4, "kdenlive:folderid", "2")
    _prop(tractor4, "kdenlive:sequenceproperties.activeTrack", "2")
    _prop(tractor4, "kdenlive:sequenceproperties.audioChannels", "2")
    _prop(tractor4, "kdenlive:sequenceproperties.audioTarget", "1")
    _prop(tractor4, "kdenlive:sequenceproperties.hasAudio", "1")
    _prop(tractor4, "kdenlive:sequenceproperties.hasVideo", "1")
    _prop(tractor4, "kdenlive:sequenceproperties.tracks", "4")
    _prop(tractor4, "kdenlive:sequenceproperties.tracksCount", "4")
    _prop(tractor4, "kdenlive:sequenceproperties.videoTarget", "2")

    ET.SubElement(tractor4, "track", producer="producer0")
    ET.SubElement(tractor4, "track", producer="tractor0")
    ET.SubElement(tractor4, "track", producer="tractor1")
    ET.SubElement(tractor4, "track", producer="tractor2")
    ET.SubElement(tractor4, "track", producer="tractor3")

    # Transitions
    for i, b_track in enumerate(["1", "2", "3", "4"], start=0):
        tr = ET.SubElement(tractor4, "transition", id=f"transition{i}")
        _prop(tr, "a_track", "0")
        _prop(tr, "b_track", b_track)
        _prop(tr, "compositing", "0")
        _prop(tr, "distort", "0")
        _prop(tr, "rotate_center", "0")
        _prop(tr, "mlt_service", "qtblend")
        _prop(tr, "kdenlive_id", "qtblend")
        _prop(tr, "internal_added", "237")
        _prop(tr, "always_active", "1")

    # Master filters
    f = ET.SubElement(tractor4, "filter", id=f"filter{filter_counter[0]}")
    filter_counter[0] += 1
    _prop(f, "mlt_service", "volume")
    _prop(f, "internal_added", "237")
    _prop(f, "disable", "1")
    f = ET.SubElement(tractor4, "filter", id=f"filter{filter_counter[0]}")
    filter_counter[0] += 1
    _prop(f, "mlt_service", "panner")
    _prop(f, "internal_added", "237")
    _prop(f, "start", "0.5")
    _prop(f, "disable", "1")

    # --- main_bin playlist ---
    main_bin = ET.SubElement(mlt, "playlist", id="main_bin")
    _prop(main_bin, "kdenlive:folder.-1.2", "Sequências")
    _prop(main_bin, "kdenlive:docproperties.activetimeline", seq_uuid)
    _prop(main_bin, "kdenlive:docproperties.audioChannels", "2")
    _prop(main_bin, "kdenlive:docproperties.compositing", "1")
    _prop(main_bin, "kdenlive:docproperties.documentid", doc_id)
    _prop(main_bin, "kdenlive:docproperties.kdenliveversion", "25.12.0")
    _prop(main_bin, "kdenlive:docproperties.opensequences", seq_uuid)
    _prop(main_bin, "kdenlive:docproperties.profile", "vertical_hd_30")
    _prop(main_bin, "kdenlive:docproperties.uuid", seq_uuid)
    _prop(main_bin, "kdenlive:docproperties.version", "1.1")
    _prop(main_bin, "xml_retain", "1")
    ET.SubElement(
        main_bin, "entry", **{"in": "00:00:00.000", "out": video_out_tc, "producer": "chain4"}
    )
    ET.SubElement(
        main_bin, "entry", **{"in": "00:00:00.000", "out": CLOSING_LENGTH_TC, "producer": "chain7"}
    )
    ET.SubElement(
        main_bin, "entry", **{"in": "00:00:00.000", "out": total_out_tc, "producer": "tractor4"}
    )

    # --- Project tractor ---
    tractor_proj = ET.SubElement(
        mlt, "tractor", id="tractor5", **{"in": "00:00:00.000", "out": total_out_tc}
    )
    _prop(tractor_proj, "kdenlive:projectTractor", "1")
    ET.SubElement(
        tractor_proj, "track", **{"in": "00:00:00.000", "out": total_out_tc, "producer": "tractor4"}
    )

    # --- Write output ---
    tree = ET.ElementTree(mlt)
    ET.indent(tree, space=" ")
    tree.write(output_path, encoding="utf-8", xml_declaration=True)
    print(f"Generated: {output_path}")
