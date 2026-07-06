"""Scene and hash analysis for GIF frame extraction."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from gif_constants import COMMAND_TIMEOUT_SEC
from gif_utils import _is_finite_number, run_command


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
    opts = options or {}
    if not frames or not hash_entries:
        return {"frames": frames, "hashesUsable": False, "matchedHashes": []}

    offset_ms = opts.get("timestampOffsetMs", 0)
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
        if opts.get("trackLoop") and position > 0 and frame_hash == first_hash:
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
    # count, match by position instead of timestamp - it's exact and immune
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
