"""ffprobe metadata and frame probing for GIF frame extraction."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gif_constants import COMMAND_TIMEOUT_SEC, MAX_CANVAS_PIXELS, MAX_DECODED_FRAMES
from gif_errors import HelperError
from gif_utils import (
    _is_finite_number,
    first_finite_number,
    parse_frame_rate,
    run_command,
    seconds_to_ms,
)


def probe_gif_container(input_path: Path) -> dict[str, Any]:
    data = json.loads(
        run_command(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "format=format_name,duration:stream=width,height,duration,r_frame_rate,avg_frame_rate,nb_frames",
                "-of",
                "json",
                str(input_path),
            ],
            timeout=COMMAND_TIMEOUT_SEC,
        ).stdout
    )
    stream = (data.get("streams") or [{}])[0]
    duration_ms = seconds_to_ms(
        first_finite_number(
            [stream.get("duration"), data.get("format", {}).get("duration")]
        )
    )
    return {
        "format": data.get("format", {}).get("format_name"),
        "durationMs": duration_ms,
        "width": int(float(stream.get("width", 0) or 0)),
        "height": int(float(stream.get("height", 0) or 0)),
        "fps": parse_frame_rate(stream.get("avg_frame_rate") or stream.get("r_frame_rate")),
        "nbFrames": first_finite_number([stream.get("nb_frames")]),
    }


def ensure_decodable_gif(metadata: dict[str, Any]) -> None:
    width = metadata.get("width") or 0
    height = metadata.get("height") or 0
    if width > 0 and height > 0 and width * height > MAX_CANVAS_PIXELS:
        raise HelperError(
            "GIF_TOO_LARGE",
            f"canvas of {width}x{height} ({width * height} px) exceeds the "
            f"{MAX_CANVAS_PIXELS} px limit; this file cannot be decoded safely",
        )

    duration_seconds = (
        metadata["durationMs"] / 1000
        if _is_finite_number(metadata.get("durationMs"))
        else None
    )
    estimated_frames = (
        duration_seconds * metadata["fps"]
        if duration_seconds is not None and _is_finite_number(metadata.get("fps"))
        else metadata.get("nbFrames")
    )
    if not _is_finite_number(estimated_frames):
        # GIFs are typically small; if the estimate can't be computed from
        # cheap container-level metadata, proceed and rely on the
        # post-probe backstop (ensure_probed_frame_budget) instead of
        # over-blocking ordinary files.
        return
    if estimated_frames > MAX_DECODED_FRAMES:
        raise HelperError(
            "GIF_TOO_LONG",
            f"~{round(estimated_frames)} frames to decode exceeds the "
            f"{MAX_DECODED_FRAMES} limit; this file is too large to analyze "
            "with this workflow",
        )


def ensure_probed_frame_budget(frame_count: int) -> None:
    if frame_count > MAX_DECODED_FRAMES:
        raise HelperError(
            "GIF_TOO_LONG",
            f"probed {frame_count} frames exceeds the {MAX_DECODED_FRAMES} "
            "limit; this file is too large to analyze with this workflow",
        )


def probe_gif_frames(input_path: Path) -> dict[str, Any]:
    data = json.loads(
        run_command(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height:frame=pts_time,pkt_pts_time,best_effort_timestamp_time,pkt_duration_time,duration_time,width,height",
                "-of",
                "json",
                str(input_path),
            ],
            timeout=COMMAND_TIMEOUT_SEC,
        ).stdout
    )
    stream = (data.get("streams") or [{}])[0]
    raw_frames = data.get("frames") if isinstance(data.get("frames"), list) else []
    previous_timestamp_ms = 0
    frames = []
    for index, frame in enumerate(raw_frames):
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
        frames.append(
            {
                "index": index,
                "timestampMs": timestamp_ms,
                "durationMs": duration_ms,
                "width": int(float(frame.get("width", stream.get("width", 0)) or 0)),
                "height": int(
                    float(frame.get("height", stream.get("height", 0)) or 0)
                ),
                "changeScore": 0,
            }
        )

    return {"frames": frames}


def resolve_gif_duration_ms(
    container_duration_ms: int | None, frames: list[dict[str, Any]]
) -> int | None:
    if _is_finite_number(container_duration_ms):
        return container_duration_ms
    last_frame = frames[-1] if frames else None
    if last_frame is None:
        return 0
    return last_frame["timestampMs"] + (
        last_frame["durationMs"] if _is_finite_number(last_frame.get("durationMs")) else 0
    )


def ensure_non_empty_gif_probe(frame_count: int) -> None:
    if frame_count == 0:
        raise HelperError("EXTRACTION_FAILED", "no frames probed from the animated image")
