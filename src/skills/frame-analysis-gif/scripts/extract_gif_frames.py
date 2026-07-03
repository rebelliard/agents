#!/usr/bin/env python3
"""Extract representative frames from GIF/WebP/APNG animations."""

from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

from select_gif_frames import DEFAULT_MAX_FRAMES, select_gif_frames

RESULT_VERSION = 2
DEFAULT_MAX_WIDTH = 960
DEFAULT_SCENE_THRESHOLD = 0.08
ALL_CHANGED_FRAME_CAP = 200
MAX_DECODED_FRAMES = 20_000
MAX_CANVAS_PIXELS = 100_000_000
COMMAND_TIMEOUT_SEC = 30
TILE_MAX_WIDTH = 480
SHEET_TARGET_WIDTH = 1440
MAX_TILES_PER_SHEET = 12
MAX_SELECT_TERMS_PER_PASS = 24


class HelperError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def extract_gif_frames(options: dict[str, Any]) -> dict[str, Any]:
    input_path = Path(options["inputPath"]).expanduser().resolve()
    out_dir = Path(
        options.get("outDir")
        or tempfile.mkdtemp(prefix="frame-analysis-gif-")
    ).expanduser().resolve()
    requested_max_frames = positive_integer(
        options.get("maxFrames"), DEFAULT_MAX_FRAMES
    )
    max_width = positive_integer(options.get("maxWidth"), DEFAULT_MAX_WIDTH)
    scene_threshold = non_negative_number(
        options.get("sceneThreshold"), DEFAULT_SCENE_THRESHOLD
    )
    sheet_enabled = options.get("sheet") is not False

    out_dir.mkdir(parents=True, exist_ok=True)
    ensure_readable_file(input_path)
    ensure_output_will_not_clobber_input(input_path, out_dir)
    ensure_tool("ffmpeg")
    ensure_tool("ffprobe")

    container_metadata = probe_gif_container(input_path)
    ensure_decodable_gif(container_metadata)

    probed = probe_gif_frames(input_path)
    ensure_non_empty_gif_probe(len(probed["frames"]))
    ensure_probed_frame_budget(len(probed["frames"]))
    duration_ms = resolve_gif_duration_ms(
        container_metadata.get("durationMs"), probed["frames"]
    )
    scene_scores = detect_scene_scores(input_path)
    hash_entries = compute_frame_hashes(input_path)
    scored_frames = apply_scene_scores(probed["frames"], scene_scores)
    annotated = annotate_frame_hashes(
        scored_frames, hash_entries, {"trackLoop": True}
    )
    frames = annotated["frames"]
    hashes_usable = annotated["hashesUsable"]
    matched_hashes = annotated["matchedHashes"]
    distinct_frame_count = len(set(matched_hashes)) if hashes_usable else None
    loop_closed = (
        matched_hashes[-1] == matched_hashes[0]
        if hashes_usable and len(matched_hashes) > 1
        else None
    )

    max_frames = (
        min(ALL_CHANGED_FRAME_CAP, max(2, len(frames)))
        if options.get("allChanged") is True
        else requested_max_frames
    )
    sampled = select_gif_frames(
        frames, {"maxFrames": max_frames, "sceneThreshold": scene_threshold}
    )
    remove_stale_outputs(out_dir)
    written = write_sampled_frames(input_path, out_dir, sampled, max_width)
    sampled_frames = written["sampled"]
    sheet_result = (
        create_contact_sheets(out_dir, sampled_frames)
        if sheet_enabled
        else {"sheets": [], "labeled": None, "labelError": None}
    )

    changed_frame_count = (
        len([frame for frame in frames if frame.get("hashChanged") is True])
        if hashes_usable
        else None
    )
    dropped_change_count = (
        count_dropped_changes(frames, sampled_frames) if hashes_usable else None
    )

    return {
        "version": RESULT_VERSION,
        "source": str(input_path),
        "format": container_metadata["format"],
        "durationSec": ms_to_sec(duration_ms),
        "frameCount": len(frames),
        "distinctFrameCount": distinct_frame_count,
        "changedFrameCount": changed_frame_count,
        "droppedChangeCount": dropped_change_count,
        "loopClosed": loop_closed,
        "animated": len(frames) > 1,
        "outDir": str(out_dir),
        "frameSize": written["frameSize"],
        "labeled": sheet_result["labeled"],
        "note": build_note(
            {
                "sampledCount": len(sampled_frames),
                "changedFrameCount": changed_frame_count,
                "droppedChangeCount": dropped_change_count,
                "loopClosed": loop_closed,
                "labeled": sheet_result["labeled"],
                "labelError": sheet_result.get("labelError"),
                "allChanged": options.get("allChanged") is True,
            }
        ),
        "sheets": sheet_result["sheets"],
        "sampled": sampled_frames,
    }


def build_note(args: dict[str, Any]) -> str:
    sampled_count = args["sampledCount"]
    changed_frame_count = args.get("changedFrameCount")
    dropped_change_count = args.get("droppedChangeCount")
    loop_closed = args.get("loopClosed")
    all_changed = args.get("allChanged", False)
    parts = []

    if changed_frame_count == 0:
        parts.append("No frame-to-frame changes detected (static or single-frame).")
    elif dropped_change_count == 0:
        parts.append("All image changes were detected and included in the analysis.")
    elif (
        isinstance(dropped_change_count, int)
        and dropped_change_count > 0
        and all_changed
    ):
        parts.append(
            f"Sampled {sampled_count} frames; {dropped_change_count} of "
            f"{changed_frame_count} changed frames exceed the exhaustive "
            "cap — coverage is partial."
        )
    elif isinstance(dropped_change_count, int) and dropped_change_count > 0:
        parts.append(
            f"Sampled {sampled_count} frames but {dropped_change_count} of "
            f"{changed_frame_count} changed frames were not included; request "
            "an exhaustive changed-frame pass if every step matters."
        )
    else:
        parts.append(
            f"Sampled {sampled_count} frames; per-frame hashing unavailable — "
            "small changes (typed text, cursor moves) may be missing; treat "
            "the step sequence as incomplete unless scene scores captured the deltas."
        )

    if loop_closed is True:
        parts.append("The animation loops back to its first frame.")
    elif loop_closed is False:
        parts.append("Animation does not loop.")

    return " ".join(parts)


def count_dropped_changes(
    frames: list[dict[str, Any]], sampled: list[dict[str, Any]]
) -> int:
    sampled_indexes = {frame["index"] for frame in sampled}
    last_non_loop_position = len(frames) - 1
    while (
        last_non_loop_position > 0
        and frames[last_non_loop_position].get("loopDuplicate") is True
    ):
        last_non_loop_position -= 1

    return len(
        [
            frame
            for position, frame in enumerate(frames)
            if position <= last_non_loop_position
            and frame.get("hashChanged") is True
            and frame["index"] not in sampled_indexes
        ]
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


def detect_scene_scores(input_path: Path) -> list[dict[str, Any]]:
    try:
        completed = run_command(
            [
                "ffmpeg",
                "-hide_banner",
                "-nostdin",
                "-i",
                str(input_path),
                "-vf",
                "select='gt(scene,0)',metadata=print",
                "-an",
                "-f",
                "null",
                "-",
            ],
            timeout=COMMAND_TIMEOUT_SEC,
            check=True,
        )
        return parse_scene_scores(completed.stderr)
    except Exception:
        return []


def parse_scene_scores(stderr: str) -> list[dict[str, Any]]:
    scores = []
    current_timestamp_ms = None
    for line in stderr.splitlines():
        timestamp_match = re.search(r"pts_time:([0-9.]+)", line)
        if timestamp_match:
            current_timestamp_ms = float(timestamp_match.group(1)) * 1000
        score_match = re.search(r"lavfi\.scene_score=([0-9.]+)", line)
        if score_match and _is_finite_number(current_timestamp_ms):
            scores.append(
                {
                    "timestampMs": current_timestamp_ms,
                    "changeScore": float(score_match.group(1)),
                }
            )
    return scores


def apply_scene_scores(
    frames: list[dict[str, Any]], scene_scores: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    if not scene_scores:
        return frames
    tolerance_ms = match_tolerance_ms(frames)
    cursor = 0
    scored = []
    for frame in frames:
        while (
            cursor + 1 < len(scene_scores)
            and abs(scene_scores[cursor + 1]["timestampMs"] - frame["timestampMs"])
            <= abs(scene_scores[cursor]["timestampMs"] - frame["timestampMs"])
        ):
            cursor += 1
        nearest = scene_scores[cursor]
        matches = abs(nearest["timestampMs"] - frame["timestampMs"]) <= tolerance_ms
        scored.append(
            {
                **frame,
                "changeScore": nearest["changeScore"] if matches else frame["changeScore"],
            }
        )
    return scored


def chunk_sampled_for_select(
    sampled: list[dict[str, Any]], max_terms_per_pass: int = MAX_SELECT_TERMS_PER_PASS
) -> list[list[dict[str, Any]]]:
    return [
        sampled[start : start + max_terms_per_pass]
        for start in range(0, len(sampled), max_terms_per_pass)
    ]


def write_sampled_frames(
    input_path: Path,
    out_dir: Path,
    sampled: list[dict[str, Any]],
    max_width: int,
) -> dict[str, Any]:
    if not sampled:
        return {"sampled": [], "frameSize": None}

    batches = chunk_sampled_for_select(sampled)
    for batch_start, batch in enumerate(batches):
        output_start = batch_start * MAX_SELECT_TERMS_PER_PASS
        select_expression = "+".join(f"eq(n\\,{frame['index']})" for frame in batch)
        run_command(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-nostdin",
                "-i",
                str(input_path),
                "-vf",
                f"select={select_expression},scale=w='min({max_width},iw)':h=-2",
                "-vsync",
                "vfr",
                "-start_number",
                str(output_start),
                str(out_dir / "frame-%03d.png"),
            ],
            timeout=COMMAND_TIMEOUT_SEC,
        )

    frame_size = read_png_size(out_dir / f"frame-{pad(0)}.png") or {
        "width": sampled[0].get("width"),
        "height": sampled[0].get("height"),
    }
    sampled_frames = [
        {
            "tile": position + 1,
            "index": frame["index"],
            "t": ms_to_sec(frame["timestampMs"]),
            "file": f"frame-{pad(position)}.png",
            "changeScore": round_score(frame["changeScore"]),
        }
        for position, frame in enumerate(sampled)
    ]
    return {"sampled": sampled_frames, "frameSize": frame_size}


def compute_frame_hashes(input_path: Path) -> list[dict[str, Any]]:
    try:
        return parse_frame_md5(
            run_command(
                [
                    "ffmpeg",
                    "-hide_banner",
                    "-nostdin",
                    "-loglevel",
                    "error",
                    "-i",
                    str(input_path),
                    "-f",
                    "framemd5",
                    "-",
                ],
                timeout=COMMAND_TIMEOUT_SEC,
            ).stdout
        )
    except Exception:
        return []


def parse_frame_md5(stdout: str) -> list[dict[str, Any]]:
    seconds_per_unit = None
    tb_match = re.search(r"^#tb 0: (\d+)/(\d+)", stdout, flags=re.MULTILINE)
    if tb_match:
        seconds_per_unit = int(tb_match.group(1)) / int(tb_match.group(2))

    entries = []
    for line in stdout.splitlines():
        trimmed = line.strip()
        if not trimmed or trimmed.startswith("#"):
            continue
        legacy_pts = re.search(r"pts_time:([0-9.]+)", trimmed)
        if legacy_pts:
            frame_hash = trimmed.split(",")[-1].strip()
            if frame_hash:
                entries.append(
                    {
                        "timestampMs": round(float(legacy_pts.group(1)) * 1000),
                        "hash": frame_hash,
                    }
                )
            continue
        csv_match = re.match(
            r"^(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*([0-9a-f]{32})",
            trimmed,
            flags=re.IGNORECASE,
        )
        if csv_match and seconds_per_unit is not None:
            entries.append(
                {
                    "timestampMs": round(int(csv_match.group(3)) * seconds_per_unit * 1000),
                    "hash": csv_match.group(6),
                }
            )
    return entries


def annotate_frame_hashes(
    frames: list[dict[str, Any]],
    hash_entries: list[dict[str, Any]],
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    options = options or {}
    if not frames or not hash_entries:
        return {"frames": frames, "hashesUsable": False, "matchedHashes": []}

    offset_ms = options.get("timestampOffsetMs", 0)
    entries = [
        {"timestampMs": entry["timestampMs"] + offset_ms, "hash": entry["hash"]}
        for entry in hash_entries
    ]
    tolerance_ms = match_tolerance_ms(frames)
    matched_hashes = match_hashes_to_frames(frames, entries, tolerance_ms)
    hashes_usable = all(frame_hash is not None for frame_hash in matched_hashes)
    first_hash = matched_hashes[0]
    annotated_frames = []

    for position, frame in enumerate(frames):
        frame_hash = matched_hashes[position]
        if frame_hash is None:
            annotated_frames.append(frame)
            continue
        prev_hash = matched_hashes[position - 1] if position > 0 else None
        annotated = {
            **frame,
            "hashChanged": position > 0 and prev_hash is not None and frame_hash != prev_hash,
        }
        if options.get("trackLoop") and position > 0 and frame_hash == first_hash:
            annotated["loopDuplicate"] = True
            annotated["loopDeltaFromFirst"] = 0
        annotated_frames.append(annotated)

    return {
        "frames": annotated_frames,
        "hashesUsable": hashes_usable,
        "matchedHashes": matched_hashes,
    }


def match_hashes_to_frames(
    frames: list[dict[str, Any]],
    hash_entries: list[dict[str, Any]],
    tolerance_ms: float,
) -> list[str | None]:
    if not hash_entries:
        return [None for _ in frames]
    # VFR sources (e.g. macOS screen recordings) can have the framemd5 pass
    # emit pts in the muxer's coarse timebase (derived from avg_frame_rate),
    # quantizing true variable-rate timestamps with error up to half the
    # adaptive tolerance below. When the probe and hash passes agree on frame
    # count, match by position instead of timestamp — it's exact and immune
    # to timebase quantization. Timestamp-tolerance matching remains the
    # fallback for windows where ffprobe (-read_intervals) and ffmpeg (-ss/
    # -t) could legitimately disagree on frame count.
    if len(frames) == len(hash_entries):
        return [entry["hash"] for entry in hash_entries]
    cursor = 0
    matched = []
    for frame in frames:
        while (
            cursor + 1 < len(hash_entries)
            and abs(hash_entries[cursor + 1]["timestampMs"] - frame["timestampMs"])
            <= abs(hash_entries[cursor]["timestampMs"] - frame["timestampMs"])
        ):
            cursor += 1
        nearest = hash_entries[cursor]
        matches = abs(nearest["timestampMs"] - frame["timestampMs"]) <= tolerance_ms
        matched.append(nearest["hash"] if matches else None)
    return matched


def match_tolerance_ms(frames: list[dict[str, Any]]) -> float:
    intervals = [
        frames[position]["timestampMs"] - frames[position - 1]["timestampMs"]
        for position in range(1, len(frames))
        if frames[position]["timestampMs"] - frames[position - 1]["timestampMs"] > 0
    ]
    if not intervals:
        return 50
    intervals.sort()
    median = intervals[len(intervals) // 2]
    return max(1, min(50, median / 2))


def create_contact_sheets(
    out_dir: Path, sampled: list[dict[str, Any]]
) -> dict[str, Any]:
    if not sampled:
        return {"sheets": [], "labeled": None, "labelError": None}

    page_layouts = []
    for start_position in range(0, len(sampled), MAX_TILES_PER_SHEET):
        page_frames = sampled[start_position : start_position + MAX_TILES_PER_SHEET]
        cols = math.ceil(math.sqrt(len(page_frames)))
        page_layouts.append(
            {
                "pageFrames": page_frames,
                "startPosition": start_position,
                "cols": cols,
                "rows": math.ceil(len(page_frames) / cols),
                "tileWidth": min(TILE_MAX_WIDTH, math.floor(SHEET_TARGET_WIDTH / cols)),
            }
        )

    labeled = has_drawtext_filter()
    label_error = None if labeled else "drawtext filter not available in this ffmpeg build"
    if labeled:
        try:
            for layout in page_layouts:
                write_labeled_frames(out_dir, layout["pageFrames"], layout["tileWidth"])
        except Exception as error:
            labeled = False
            label_error = short_error_message(error)

    sheets = []
    for page_index, layout in enumerate(page_layouts):
        sheet_name = (
            "contact-sheet.png"
            if len(page_layouts) == 1
            else f"contact-sheet-{pad(page_index)}.png"
        )
        tile_frames(
            input_pattern=out_dir / ("labeled-%03d.png" if labeled else "frame-%03d.png"),
            start_number=layout["startPosition"],
            tile_width=None if labeled else layout["tileWidth"],
            sheet_path=out_dir / sheet_name,
            cols=layout["cols"],
            rows=layout["rows"],
        )
        sheets.append(
            {
                "file": sheet_name,
                "tiles": f"{layout['startPosition'] + 1}-{layout['startPosition'] + len(layout['pageFrames'])}",
                "cols": layout["cols"],
                "rows": layout["rows"],
            }
        )
    return {"sheets": sheets, "labeled": labeled, "labelError": label_error}


def has_drawtext_filter() -> bool:
    try:
        stdout = run_command(
            ["ffmpeg", "-hide_banner", "-filters"], timeout=5
        ).stdout
        return re.search(r"\bdrawtext\b", stdout) is not None
    except Exception:
        return False


def write_labeled_frames(
    out_dir: Path, sampled: list[dict[str, Any]], tile_width: int
) -> None:
    for frame in sampled:
        input_path = out_dir / frame["file"]
        output_path = out_dir / f"labeled-{pad(frame['tile'] - 1)}.png"
        label = f"tile {frame['tile']}  t={frame['t']}s"
        run_command(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-nostdin",
                "-i",
                str(input_path),
                "-vf",
                f"scale=w='min({tile_width},iw)':h=-2,drawtext=text='{escape_drawtext(label)}':x=8:y=8:fontcolor=white:fontsize=24:box=1:boxcolor=black@0.65",
                "-frames:v",
                "1",
                str(output_path),
            ],
            timeout=COMMAND_TIMEOUT_SEC,
        )


def tile_frames(
    *,
    input_pattern: Path,
    start_number: int,
    tile_width: int | None,
    sheet_path: Path,
    cols: int,
    rows: int,
) -> None:
    scale = f"scale=w='min({tile_width},iw)':h=-2," if tile_width else ""
    run_command(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-framerate",
            "1",
            "-start_number",
            str(start_number),
            "-i",
            str(input_pattern),
            "-filter_complex",
            f"{scale}tile={cols}x{rows}:padding=12:margin=12",
            "-frames:v",
            "1",
            str(sheet_path),
        ],
        timeout=COMMAND_TIMEOUT_SEC,
    )


def ensure_readable_file(file_path: Path) -> None:
    try:
        if not file_path.is_file():
            raise HelperError("NOT_FILE", f"{file_path} is not a file")
    except OSError as error:
        raise HelperError("NOT_FILE", str(error)) from error


def ensure_tool(command: str) -> None:
    if shutil.which(command) is None:
        raise HelperError(
            "MISSING_TOOL",
            f"{command} is required for GIF frame extraction. Install ffmpeg "
            "(ffprobe ships with it): brew install ffmpeg (macOS), apt-get "
            "update && apt-get install -y ffmpeg (Debian/Ubuntu), apk add "
            "ffmpeg (Alpine), sudo dnf install ffmpeg-free (Fedora), sudo "
            "pacman -S ffmpeg (Arch), or on Windows winget install --id "
            "Gyan.FFmpeg or choco install ffmpeg.",
        )
    try:
        run_command([command, "-version"], timeout=5)
    except Exception as error:
        raise HelperError(
            "MISSING_TOOL",
            f"{command} is required for GIF frame extraction. Install ffmpeg "
            "(ffprobe ships with it): brew install ffmpeg (macOS), apt-get "
            "update && apt-get install -y ffmpeg (Debian/Ubuntu), apk add "
            "ffmpeg (Alpine), sudo dnf install ffmpeg-free (Fedora), sudo "
            "pacman -S ffmpeg (Arch), or on Windows winget install --id "
            "Gyan.FFmpeg or choco install ffmpeg.",
        ) from error


def remove_stale_outputs(out_dir: Path) -> None:
    for entry in out_dir.iterdir():
        if is_generated_output_name(entry):
            entry.unlink(missing_ok=True)


def is_generated_output_name(file_path: Path) -> bool:
    return (
        re.search(
            r"^(frame|labeled)-\d{3}\.png$|^contact-sheet(-\d{3})?\.png$",
            file_path.name,
        )
        is not None
    )


def ensure_output_will_not_clobber_input(input_path: Path, out_dir: Path) -> None:
    if input_path.parent == out_dir and is_generated_output_name(input_path):
        raise HelperError(
            "OUTPUT_COLLISION",
            f"--out-dir {out_dir} would overwrite input {input_path}; choose "
            "a separate output directory",
        )


def read_png_size(file_path: Path) -> dict[str, int] | None:
    try:
        data = file_path.read_bytes()[:24]
    except OSError:
        return None
    if len(data) < 24:
        return None
    return {
        "width": int.from_bytes(data[16:20], "big"),
        "height": int.from_bytes(data[20:24], "big"),
    }


def short_error_message(error: BaseException) -> str:
    stderr = getattr(error, "stderr", None)
    if isinstance(stderr, str) and stderr.strip():
        lines = [line for line in stderr.strip().splitlines() if line]
        if lines:
            return lines[-1][:300]
    return str(error)[:300]


def parse_cli_args(argv: list[str]) -> dict[str, Any]:
    options: dict[str, Any] = {"sheet": True}
    positional = []
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg == "--out-dir":
            options["outDir"] = read_option_value(argv, index, arg)
            index += 2
        elif arg == "--max-frames":
            options["maxFrames"] = read_positive_number_option(argv, index, arg)
            index += 2
        elif arg == "--max-width":
            options["maxWidth"] = read_positive_number_option(argv, index, arg)
            index += 2
        elif arg == "--scene-threshold":
            options["sceneThreshold"] = read_non_negative_number_option(argv, index, arg)
            index += 2
        elif arg == "--all-changed":
            options["allChanged"] = True
            index += 1
        elif arg == "--sheet":
            options["sheet"] = True
            index += 1
        elif arg == "--no-sheet":
            options["sheet"] = False
            index += 1
        elif arg.startswith("--"):
            raise HelperError("UNKNOWN_OPTION", f"Unknown option: {arg}")
        else:
            positional.append(arg)
            index += 1

    if len(positional) != 1:
        raise HelperError(
            "USAGE",
            "Usage: extract_gif_frames.py <input.gif> [--out-dir dir] "
            "[--max-frames n] [--all-changed] [--max-width px] "
            "[--scene-threshold n] [--sheet|--no-sheet]",
        )
    return {**options, "inputPath": positional[0]}


def read_option_value(argv: list[str], index: int, option: str) -> str:
    if index + 1 >= len(argv) or argv[index + 1].startswith("--"):
        raise HelperError("USAGE", f"{option} requires a value")
    return argv[index + 1]


def read_finite_number_option(argv: list[str], index: int, option: str) -> float:
    value = read_option_value(argv, index, option)
    try:
        number_value = float(value)
    except ValueError as error:
        raise HelperError("USAGE", f"{option} requires a numeric value") from error
    if not math.isfinite(number_value):
        raise HelperError("USAGE", f"{option} requires a numeric value")
    return number_value


def read_positive_number_option(argv: list[str], index: int, option: str) -> float:
    number_value = read_finite_number_option(argv, index, option)
    if number_value <= 0:
        raise HelperError("USAGE", f"{option} requires a positive numeric value")
    return number_value


def read_non_negative_number_option(argv: list[str], index: int, option: str) -> float:
    number_value = read_finite_number_option(argv, index, option)
    if number_value < 0:
        raise HelperError("USAGE", f"{option} requires a non-negative numeric value")
    return number_value


def positive_integer(value: Any, fallback: int) -> int:
    if not _is_finite_number(value) or value < 1:
        return fallback
    return math.floor(value)


def non_negative_number(value: Any, fallback: float) -> float:
    if not _is_finite_number(value) or value < 0:
        return fallback
    return value


def first_finite_number(values: list[Any]) -> float | None:
    for value in values:
        try:
            number_value = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number_value):
            return number_value
    return None


def parse_frame_rate(rate: str | None) -> float | None:
    if not isinstance(rate, str):
        return None
    numerator, _, denominator = rate.partition("/")
    denominator = denominator or "1"
    try:
        fps = float(numerator) / float(denominator)
    except ValueError:
        return None
    return fps if math.isfinite(fps) and fps > 0 else None


def seconds_to_ms(seconds: float | None) -> int | None:
    if not _is_finite_number(seconds):
        return None
    return round(seconds * 1000)


def ms_to_sec(ms: float | None) -> float | None:
    if not _is_finite_number(ms):
        return None
    return round(ms / 1000, 2)


def round_score(score: float) -> float:
    return round(score, 3) if _is_finite_number(score) else 0


def stringify_result(result: dict[str, Any]) -> str:
    return json.dumps(
        {key: value for key, value in result.items() if value is not None},
        indent=2,
        allow_nan=False,
    )


def pad(number: int) -> str:
    return str(number).zfill(3)


def escape_drawtext(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "\\'")
        .replace("%", "\\%")
    )


def error_result(input_path: str | None, error: BaseException) -> dict[str, Any]:
    fallback_code = "TIMEOUT" if isinstance(error, subprocess.TimeoutExpired) else "EXTRACTION_FAILED"
    code = error.code if isinstance(error, HelperError) else fallback_code
    return {
        "version": RESULT_VERSION,
        "source": safe_resolved_path(input_path),
        "format": None,
        "durationSec": None,
        "frameCount": 0,
        "animated": False,
        "sheets": [],
        "sampled": [],
        "error": {"code": code, "message": short_error_message(error)},
    }


def safe_resolved_path(file_path: str | None) -> str | None:
    if file_path is None:
        return None
    try:
        return str(Path(file_path).expanduser().resolve())
    except (OSError, RuntimeError, ValueError):
        return file_path


def run_command(
    args: list[str], *, timeout: int, check: bool = True
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=check,
    )


def _is_finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def main() -> int:
    options = None
    try:
        options = parse_cli_args(sys.argv[1:])
        result = extract_gif_frames(options)
        print(stringify_result(result))
        return 0
    except Exception as error:
        print(stringify_result(error_result(options.get("inputPath") if options else None, error)))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
