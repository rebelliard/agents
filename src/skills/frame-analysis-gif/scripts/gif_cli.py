"""CLI parsing for GIF frame extraction."""

from __future__ import annotations

import math
from typing import Any

from gif_errors import HelperError


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
