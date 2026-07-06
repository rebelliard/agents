"""ffprobe metadata and frame probing for video frame extraction."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from video_constants import (
    DECODE_TIMEOUT_SEC,
    MAX_CANVAS_PIXELS,
    MAX_DECODED_FRAMES,
    PROBE_TIMEOUT_SEC,
)
from video_errors import HelperError
from video_utils import (
    _is_finite_number,
    first_finite_number,
    ms_to_sec,
    parse_frame_rate,
    run_command,
    seconds_to_ms,
)
from video_window import window_probe_args


def probe_video_metadata(input_path: Path) -> dict[str, Any]:
    data = json.loads(
        run_command(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=format_name,duration:stream=codec_type,codec_name,width,height,r_frame_rate,avg_frame_rate,nb_frames,duration",
                "-of",
                "json",
                str(input_path),
            ],
            timeout=PROBE_TIMEOUT_SEC,
        ).stdout
    )
    streams = data.get("streams") if isinstance(data.get("streams"), list) else []
    video_stream = next(
        (stream for stream in streams if stream.get("codec_type") == "video"), None
    )
    if video_stream is None:
        raise HelperError(
            "NO_VIDEO_STREAM",
            f"{input_path} has no video stream (format: {data.get('format', {}).get('format_name', 'unknown')})",
        )
    audio_stream = next(
        (stream for stream in streams if stream.get("codec_type") == "audio"), None
    )
    duration_ms = seconds_to_ms(
        first_finite_number(
            [data.get("format", {}).get("duration"), video_stream.get("duration")]
        )
    )
    return {
        "format": data.get("format", {}).get("format_name"),
        "durationMs": duration_ms,
        "width": int(float(video_stream.get("width", 0) or 0)),
        "height": int(float(video_stream.get("height", 0) or 0)),
        "fps": parse_frame_rate(
            video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate")
        ),
        "nbFrames": first_finite_number([video_stream.get("nb_frames")]),
        "audio": (
            {"present": True, "codec": audio_stream.get("codec_name")}
            if audio_stream
            else {"present": False}
        ),
    }


def ensure_video_source(input_path: Path, metadata: dict[str, Any]) -> None:
    format_names = {
        name.strip()
        for name in str(metadata.get("format") or "").split(",")
        if name.strip()
    }
    still_formats = {
        "apng",
        "gif",
        "image2",
        "jpeg_pipe",
        "mjpeg",
        "png_pipe",
        "webp_pipe",
    }
    if format_names & still_formats:
        raise HelperError(
            "STILL_IMAGE",
            f"{input_path} is a still or animated image source, not a video "
            "container; use the animated-image workflow or provide the "
            "original video file",
            duration_sec=ms_to_sec(metadata.get("durationMs")),
            fps=metadata.get("fps"),
        )


def ensure_decodable_canvas(metadata: dict[str, Any]) -> None:
    width = metadata.get("width") or 0
    height = metadata.get("height") or 0
    if width > 0 and height > 0 and width * height > MAX_CANVAS_PIXELS:
        raise HelperError(
            "VIDEO_TOO_LARGE",
            f"canvas of {width}x{height} ({width * height} px) exceeds the "
            f"{MAX_CANVAS_PIXELS} px limit; this file cannot be decoded safely",
            duration_sec=ms_to_sec(metadata.get("durationMs")),
            fps=metadata.get("fps"),
        )


def ensure_decodable_window(
    metadata: dict[str, Any], window: dict[str, Any] | None
) -> None:
    total_seconds = (
        metadata["durationMs"] / 1000
        if _is_finite_number(metadata.get("durationMs"))
        else None
    )
    start_seconds = window["startSeconds"] if window else 0
    has_bounded_window = bool(window and _is_finite_number(window.get("durationSeconds")))
    if total_seconds is not None:
        remaining = max(0, total_seconds - start_seconds)
    else:
        remaining = math.inf
    window_seconds = min(
        window["durationSeconds"] if has_bounded_window else math.inf,
        remaining,
    )
    estimated_frames = (
        window_seconds * metadata["fps"]
        if math.isfinite(window_seconds) and _is_finite_number(metadata.get("fps"))
        else metadata.get("nbFrames")
    )
    if not _is_finite_number(estimated_frames):
        if not has_bounded_window:
            raise HelperError(
                "VIDEO_TOO_LONG",
                "frame count cannot be estimated for the unbounded video; "
                "analyze a window with --start <seconds> and --duration <seconds>",
                duration_sec=ms_to_sec(metadata.get("durationMs")),
                fps=metadata.get("fps"),
            )
        return
    if estimated_frames > MAX_DECODED_FRAMES:
        raise HelperError(
            "VIDEO_TOO_LONG",
            f"~{round(estimated_frames)} frames to decode exceeds the "
            f"{MAX_DECODED_FRAMES} limit; analyze a window with --start "
            "<seconds> and --duration <seconds>",
            duration_sec=ms_to_sec(metadata.get("durationMs")),
            fps=metadata.get("fps"),
        )


def ensure_probed_frame_budget(frame_count: int, metadata: dict[str, Any]) -> None:
    if frame_count > MAX_DECODED_FRAMES:
        raise HelperError(
            "VIDEO_TOO_LONG",
            f"probed {frame_count} frames exceeds the {MAX_DECODED_FRAMES} "
            "limit; analyze a window with --start <seconds> and --duration <seconds>",
            duration_sec=ms_to_sec(metadata.get("durationMs")),
            fps=metadata.get("fps"),
        )


def probe_video_frames(
    input_path: Path, metadata: dict[str, Any], window: dict[str, Any] | None
) -> dict[str, Any]:
    start_ms = window["startSeconds"] * 1000 if window else 0
    end_ms = (
        start_ms + window["durationSeconds"] * 1000
        if window and _is_finite_number(window.get("durationSeconds"))
        else math.inf
    )
    data = json.loads(
        run_command(
            [
                "ffprobe",
                "-v",
                "error",
                *window_probe_args(window),
                "-select_streams",
                "v:0",
                "-show_entries",
                "frame=pts_time,pkt_pts_time,best_effort_timestamp_time,pkt_duration_time,duration_time,width,height",
                "-of",
                "json",
                str(input_path),
            ],
            timeout=DECODE_TIMEOUT_SEC,
        ).stdout
    )
    raw_frames = data.get("frames") if isinstance(data.get("frames"), list) else []
    previous_timestamp_ms = start_ms
    frames = []
    for frame in raw_frames:
        timestamp_ms = seconds_to_ms(
            first_finite_number(
                [
                    frame.get("pts_time"),
                    frame.get("pkt_pts_time"),
                    frame.get("best_effort_timestamp_time"),
                ]
            )
        )
        if timestamp_ms is None:
            timestamp_ms = previous_timestamp_ms
        duration_ms = seconds_to_ms(
            first_finite_number(
                [frame.get("pkt_duration_time"), frame.get("duration_time")]
            )
        )
        previous_timestamp_ms = timestamp_ms + (
            duration_ms if _is_finite_number(duration_ms) else 1
        )
        if timestamp_ms < start_ms or timestamp_ms >= end_ms:
            continue
        frames.append(
            {
                "index": len(frames),
                "timestampMs": timestamp_ms,
                "durationMs": duration_ms,
                "width": int(float(frame.get("width", metadata.get("width", 0)) or 0)),
                "height": int(
                    float(frame.get("height", metadata.get("height", 0)) or 0)
                ),
                "changeScore": 0,
            }
        )
    return {"frames": frames}
