#!/usr/bin/env python3
"""Extract representative frames from GIF/WebP/APNG animations."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

from gif_changes import (
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
from gif_cli import (
    parse_cli_args,
    read_finite_number_option,
    read_non_negative_number_option,
    read_option_value,
    read_positive_number_option,
)
from gif_constants import (
    ALL_CHANGED_FRAME_CAP,
    DEFAULT_MAX_WIDTH,
    DEFAULT_SCENE_THRESHOLD,
    MAX_CANVAS_PIXELS,
    MAX_DECODED_FRAMES,
    RESULT_VERSION,
)
from gif_errors import (
    HelperError,
    ensure_output_will_not_clobber_input,
    ensure_readable_file,
    ensure_tool,
    error_result,
    safe_resolved_path,
    short_error_message,
)
from gif_probe import (
    ensure_decodable_gif,
    ensure_non_empty_gif_probe,
    ensure_probed_frame_budget,
    probe_gif_container,
    probe_gif_frames,
    resolve_gif_duration_ms,
)
from gif_render import (
    chunk_sampled_for_select,
    create_contact_sheets,
    has_drawtext_filter,
    remove_stale_outputs,
    tile_frames,
    write_labeled_frames,
    write_sampled_frames,
)
from gif_utils import (
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
from select_gif_frames import DEFAULT_MAX_FRAMES, select_gif_frames


def extract_gif_frames(options: dict[str, Any]) -> dict[str, Any]:
    input_path = Path(options["inputPath"]).expanduser().resolve()
    out_dir = Path(
        options.get("outDir") or tempfile.mkdtemp(prefix="frame-analysis-gif-")
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


def main() -> int:
    options = None
    try:
        options = parse_cli_args(sys.argv[1:])
        result = extract_gif_frames(options)
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
