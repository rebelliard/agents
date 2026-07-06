"""Window helpers for video frame extraction."""

from __future__ import annotations

from typing import Any

from video_utils import _is_finite_number, non_negative_number


def resolve_window(options: dict[str, Any]) -> dict[str, Any] | None:
    start_seconds = non_negative_number(options.get("startSeconds"), 0)
    duration_seconds = (
        options.get("durationSeconds")
        if _is_finite_number(options.get("durationSeconds"))
        and options["durationSeconds"] > 0
        else None
    )
    if start_seconds == 0 and duration_seconds is None:
        return None
    return {"startSeconds": start_seconds, "durationSeconds": duration_seconds}


def window_input_args(window: dict[str, Any] | None) -> list[str]:
    if not window:
        return []
    args = ["-ss", str(window["startSeconds"])]
    if _is_finite_number(window.get("durationSeconds")):
        args.extend(["-t", str(window["durationSeconds"])])
    return args


def window_probe_args(window: dict[str, Any] | None) -> list[str]:
    if not window:
        return []
    if _is_finite_number(window.get("durationSeconds")):
        # Use an absolute end (`start%end`), not a `+duration` relative end:
        # in ffprobe, `+OFFSET` is relative to where the demuxer seek LANDS
        # (the keyframe at/before start), not to the requested start. On
        # normal-GOP H.264 that silently truncates or empties the window
        # whenever the seek lands well before `start`. An absolute end is
        # not keyframe-relative, so it always covers the full requested
        # range; the `timestamp_ms < start_ms` filter below still discards
        # the keyframe-to-start lead-in frames.
        start = window["startSeconds"]
        end = start + window["durationSeconds"]
        return ["-read_intervals", f"{start}%{end}"]
    return ["-read_intervals", f"{window['startSeconds']}%"]
