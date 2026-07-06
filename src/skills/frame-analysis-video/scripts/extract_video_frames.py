#!/usr/bin/env python3
"""Extract representative frames from video files."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

from select_video_frames import DEFAULT_MAX_FRAMES, select_video_frames
from video_changes import (
    annotate_frame_hashes,
    apply_scene_scores,
    compute_frame_hashes,
    count_dropped_changes,
    detect_scene_scores,
    match_hashes_to_frames,
    match_tolerance_ms,
    parse_frame_md5,
    parse_scene_scores,
)
from video_cli import (
    parse_cli_args,
    read_finite_number_option,
    read_non_negative_number_option,
    read_option_value,
    read_positive_number_option,
)
from video_constants import (
    ALL_CHANGED_FRAME_CAP,
    DEFAULT_MAX_WIDTH,
    DEFAULT_SCENE_THRESHOLD,
    MAX_CANVAS_PIXELS,
    MAX_DECODED_FRAMES,
    RESULT_VERSION,
)
from video_errors import (
    HelperError,
    ensure_output_will_not_clobber_input,
    ensure_readable_file,
    ensure_tool,
    error_result,
    safe_resolved_path,
    short_error_message,
)
from video_probe import (
    ensure_decodable_canvas,
    ensure_decodable_window,
    ensure_probed_frame_budget,
    ensure_video_source,
    probe_video_frames,
    probe_video_metadata,
)
from video_render import (
    chunk_sampled_for_select,
    create_contact_sheets,
    has_drawtext_filter,
    remove_stale_outputs,
    tile_frames,
    write_labeled_frames,
    write_sampled_frames,
)
from video_utils import (
    _is_finite_number,
    escape_drawtext,
    first_finite_number,
    is_generated_output_name,
    ms_to_sec,
    non_negative_number,
    pad,
    parse_frame_rate,
    positive_integer,
    read_png_size,
    round_score,
    run_command,
    seconds_to_ms,
    stringify_result,
)
from video_window import resolve_window, window_input_args, window_probe_args


def extract_video_frames(options: dict[str, Any]) -> dict[str, Any]:
    input_path = Path(options["inputPath"]).expanduser().resolve()
    out_dir = Path(
        options.get("outDir") or tempfile.mkdtemp(prefix="frame-analysis-video-")
    ).expanduser().resolve()
    requested_max_frames = positive_integer(
        options.get("maxFrames"), DEFAULT_MAX_FRAMES
    )
    max_width = positive_integer(options.get("maxWidth"), DEFAULT_MAX_WIDTH)
    scene_threshold = non_negative_number(
        options.get("sceneThreshold"), DEFAULT_SCENE_THRESHOLD
    )
    sheet_enabled = options.get("sheet") is not False
    window = resolve_window(options)

    out_dir.mkdir(parents=True, exist_ok=True)
    ensure_readable_file(input_path)
    ensure_output_will_not_clobber_input(input_path, out_dir)
    ensure_tool("ffmpeg")
    ensure_tool("ffprobe")

    metadata = probe_video_metadata(input_path)
    ensure_video_source(input_path, metadata)
    ensure_decodable_canvas(metadata)
    ensure_decodable_window(metadata, window)
    probed = probe_video_frames(input_path, metadata, window)
    if len(probed["frames"]) == 0:
        probed_duration_sec = ms_to_sec(metadata["durationMs"])
        raise HelperError(
            "EMPTY_WINDOW",
            "no frames in the analyzed window — --start "
            f"{window['startSeconds'] if window else 0}s may be at or past "
            f"the end of the source ({probed_duration_sec or 'unknown'}s), or "
            "the window may be shorter than the source's frame interval",
            duration_sec=probed_duration_sec,
            fps=metadata.get("fps"),
        )
    ensure_probed_frame_budget(len(probed["frames"]), metadata)

    scene_scores = detect_scene_scores(input_path, window)
    hash_entries = compute_frame_hashes(input_path, window)
    scored_frames = apply_scene_scores(probed["frames"], scene_scores)
    annotated = annotate_frame_hashes(
        scored_frames,
        hash_entries,
        {"timestampOffsetMs": window["startSeconds"] * 1000 if window else 0},
    )
    frames = annotated["frames"]
    hashes_usable = annotated["hashesUsable"]
    matched_hashes = annotated["matchedHashes"]
    distinct_frame_count = len(set(matched_hashes)) if hashes_usable else None

    max_frames = (
        min(ALL_CHANGED_FRAME_CAP, max(2, len(frames)))
        if options.get("allChanged") is True
        else requested_max_frames
    )
    sampled = select_video_frames(
        frames, {"maxFrames": max_frames, "sceneThreshold": scene_threshold}
    )
    remove_stale_outputs(out_dir)
    written = write_sampled_frames(input_path, out_dir, sampled, max_width, window)
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
        "format": metadata["format"],
        "durationSec": ms_to_sec(metadata["durationMs"]),
        "fps": metadata["fps"],
        "window": (
            {
                "startSec": window["startSeconds"],
                "durationSec": (
                    window["durationSeconds"]
                    if _is_finite_number(window.get("durationSeconds"))
                    else None
                ),
            }
            if window
            else None
        ),
        "frameCount": len(frames),
        "distinctFrameCount": distinct_frame_count,
        "changedFrameCount": changed_frame_count,
        "droppedChangeCount": dropped_change_count,
        "audio": metadata["audio"],
        "outDir": str(out_dir),
        "frameSize": written["frameSize"],
        "labeled": sheet_result["labeled"],
        "note": build_note(
            {
                "sampledCount": len(sampled_frames),
                "changedFrameCount": changed_frame_count,
                "droppedChangeCount": dropped_change_count,
                "labeled": sheet_result["labeled"],
                "labelError": sheet_result.get("labelError"),
                "window": window,
                "sourceDurationSec": ms_to_sec(metadata["durationMs"]),
                "audio": metadata["audio"],
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
    window = args.get("window")
    source_duration_sec = args.get("sourceDurationSec")
    audio = args.get("audio")
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
            f"{changed_frame_count} changed frames exceed the exhaustive cap "
            "— narrow the analyzed time window to recover them."
        )
    elif isinstance(dropped_change_count, int) and dropped_change_count > 0:
        parts.append(
            f"Sampled {sampled_count} frames but {dropped_change_count} of "
            f"{changed_frame_count} changed frames were not included; request "
            "an exhaustive changed-frame pass or narrower time window if every "
            "step matters."
        )
    else:
        parts.append(
            f"Sampled {sampled_count} frames; per-frame hashing unavailable — "
            "small changes (typed text, cursor moves) may be missing; treat "
            "the step sequence as incomplete unless scene scores captured the deltas."
        )

    if window:
        window_end = (
            f"for {window['durationSeconds']}s"
            if _is_finite_number(window.get("durationSeconds"))
            else "to the end"
        )
        total = f" (source is {source_duration_sec}s total)" if source_duration_sec else ""
        parts.append(
            f"Analyzed only the window from {window['startSeconds']}s "
            f"{window_end}{total}; timestamps are source times."
        )
    if audio and audio.get("present"):
        parts.append("An audio track exists but was not analyzed.")

    return " ".join(parts)


def main() -> int:
    options = None
    try:
        options = parse_cli_args(sys.argv[1:])
        result = extract_video_frames(options)
        print(stringify_result(result))
        return 0
    except Exception as error:
        print(
            stringify_result(
                error_result(options.get("inputPath") if options else None, error)
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
