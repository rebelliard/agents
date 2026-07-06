"""Frame image rendering and contact sheet generation."""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

from gif_constants import (
    COMMAND_TIMEOUT_SEC,
    MAX_SELECT_TERMS_PER_PASS,
    MAX_TILES_PER_SHEET,
    SHEET_TARGET_WIDTH,
    TILE_MAX_WIDTH,
)
from gif_errors import short_error_message
from gif_utils import (
    escape_drawtext,
    is_generated_output_name,
    ms_to_sec,
    pad,
    read_png_size,
    round_score,
    run_command,
)


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


def remove_stale_outputs(out_dir: Path) -> None:
    for entry in out_dir.iterdir():
        if is_generated_output_name(entry):
            entry.unlink(missing_ok=True)
