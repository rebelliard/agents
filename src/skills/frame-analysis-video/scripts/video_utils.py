"""Shared pure helpers for video frame extraction."""

from __future__ import annotations

import json
import math
import re
import subprocess
from pathlib import Path
from typing import Any


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


def is_generated_output_name(file_path: Path) -> bool:
    return (
        re.search(
            r"^(frame|labeled)-\d{3}\.png$|^contact-sheet(-\d{3})?\.png$",
            file_path.name,
        )
        is not None
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


def _is_finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
