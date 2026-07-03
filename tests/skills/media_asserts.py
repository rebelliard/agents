"""Shared test scaffolding for decoding and asserting on extracted PNG frames.

Used by both the GIF and video extract-script test suites, which each render
synthetic fixtures from ffmpeg's lavfi `color=c=<name>` source and need to
verify the resulting PNGs actually contain that color.
"""

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

# Approximate RGB values ffmpeg's lavfi color=c=<name> source decodes to.
# Sampled with `ffmpeg -f lavfi -i color=c=<name> ... -pix_fmt rgb24`.
EXPECTED_COLOR_RGB = {
    "red": (255, 0, 0),
    "blue": (0, 0, 255),
    "green": (0, 128, 0),
    "yellow": (255, 255, 0),
    "magenta": (255, 0, 255),
    "cyan": (0, 255, 255),
}


def decode_average_rgb(png_path: Path) -> tuple[float, float, float]:
    """Decode a PNG with ffmpeg and return its average (r, g, b)."""
    completed = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(png_path),
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-",
        ],
        capture_output=True,
        timeout=30,
        check=True,
    )
    raw = completed.stdout
    pixel_count = len(raw) // 3
    assert pixel_count > 0, f"no pixel data decoded from {png_path}"
    r_total = sum(raw[0::3])
    g_total = sum(raw[1::3])
    b_total = sum(raw[2::3])
    return (r_total / pixel_count, g_total / pixel_count, b_total / pixel_count)


def assert_color_matches(test: unittest.TestCase, png_path: Path, color_name: str) -> None:
    expected = EXPECTED_COLOR_RGB[color_name]
    actual = decode_average_rgb(png_path)
    for channel_index, channel_name in enumerate(("r", "g", "b")):
        test.assertAlmostEqual(
            actual[channel_index],
            expected[channel_index],
            delta=40,
            msg=(
                f"{png_path.name} channel {channel_name}: expected ~{expected} "
                f"for '{color_name}', got {tuple(round(c) for c in actual)}"
            ),
        )
