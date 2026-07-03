#!/usr/bin/env python3
"""Recover the original animated source behind a flattened editor preview."""

from __future__ import annotations

import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Any

RESULT_VERSION = 1
ASSET_UUID_SUFFIX = re.compile(
    r"-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
GENERIC_STEMS = {"image", "screenshot", "pasted", "clipboard"}
ANIMATED_EXTENSIONS = {".gif", ".webp", ".png", ".apng"}
DEFAULT_WITHIN_HOURS = 48
MAGIC_SNIFF_BYTES = 65_536
WALK_IGNORE_DIRS = {
    "node_modules",
    ".git",
    "dist",
    "build",
    ".next",
    "coverage",
    ".turbo",
    ".cache",
}
WALK_MAX_DEPTH = 6
WALK_MAX_ENTRIES = 20_000
LIST_DIR_MAX_ENTRIES = 2_000


class HelperError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def resolve_gif_source(options: dict[str, Any]) -> dict[str, Any]:
    asset = Path(options["assetPath"]).expanduser().resolve()
    within_hours = _positive_number(options.get("withinHours"), DEFAULT_WITHIN_HOURS)
    within_ms = within_hours * 60 * 60 * 1000

    try:
        asset_stat = asset.stat()
    except OSError as error:
        raise HelperError("NOT_FILE", f"{asset} is not a readable file") from error
    if not asset.is_file():
        raise HelperError("NOT_FILE", f"{asset} is not a readable file")

    asset_format = sniff_file_format(asset)
    stem_info = parse_asset_stem(asset.name)
    anchor_ms = asset_stat.st_mtime * 1000

    cwd = Path(options.get("cwd") or Path.cwd()).expanduser().resolve()
    home = Path(options.get("home") or Path.home()).expanduser().resolve()
    search_dirs = build_search_dirs(asset.parent, cwd, home)

    collected = collect_candidates(
        search_dirs=search_dirs,
        walk_dir_root=cwd,
        walk_max_entries=options.get("walkMaxEntries", WALK_MAX_ENTRIES),
        list_dir_max_entries=options.get("listDirMaxEntries", LIST_DIR_MAX_ENTRIES),
        stem=stem_info["stem"],
        stem_generic=stem_info["generic"],
        asset_path=asset,
    )
    candidates = rank_candidates(
        collected["candidates"],
        {
            "stem": stem_info["stem"],
            "stemGeneric": stem_info["generic"],
            "anchorMs": anchor_ms,
            "withinMs": within_ms,
        },
    )
    resolution = build_resolution(
        {
            "asset": str(asset),
            "assetFormat": asset_format,
            "stemInfo": stem_info,
            "candidates": candidates,
            "home": home,
        }
    )

    return {
        "version": RESULT_VERSION,
        "asset": str(asset),
        "assetFormat": asset_format["format"],
        "assetAnimatedContainer": asset_format["animatedContainer"],
        "stem": stem_info["stem"],
        "stemGeneric": stem_info["generic"],
        "withinHours": within_hours,
        "searchedDirs": [str(entry["path"]) for entry in search_dirs],
        "searchTruncated": collected["searchTruncated"],
        "candidates": [
            {
                "path": candidate["path"],
                "format": candidate["format"],
                "mtimeMs": candidate["mtimeMs"],
                "confidence": candidate["confidence"],
                "reason": candidate["reason"],
            }
            for candidate in candidates
        ],
        "resolved": resolution["resolved"],
        "resolvedConfidence": resolution["resolvedConfidence"],
        "recommendation": resolution["recommendation"],
        "extractTarget": resolution["extractTarget"],
        "note": resolution["note"],
    }


def parse_asset_stem(file_name: str) -> dict[str, Any]:
    path = Path(file_name)
    ext = "".join(path.suffixes[-1:])
    base = file_name[: len(file_name) - len(ext)] if ext else file_name
    if not ASSET_UUID_SUFFIX.search(base):
        return {"stem": None, "generic": False, "isAsset": False}

    stem = ASSET_UUID_SUFFIX.sub("", base)
    if len(stem) == 0:
        return {"stem": None, "generic": True, "isAsset": True}

    return {
        "stem": stem,
        "generic": stem.lower() in GENERIC_STEMS,
        "isAsset": True,
    }


def sniff_format(buffer: bytes) -> dict[str, Any]:
    if len(buffer) >= 6 and buffer[:6] in {b"GIF87a", b"GIF89a"}:
        return {"format": "gif", "animatedContainer": True}

    if len(buffer) >= 3 and buffer[0] == 0xFF and buffer[1] == 0xD8:
        return {"format": "jpeg", "animatedContainer": False}

    if len(buffer) >= 8 and buffer[:4] == b"\x89PNG":
        is_apng = png_has_animation_control(buffer)
        return {"format": "apng" if is_apng else "png", "animatedContainer": is_apng}

    if len(buffer) >= 12 and buffer[:4] == b"RIFF" and buffer[8:12] == b"WEBP":
        return {"format": "webp", "animatedContainer": webp_is_animated(buffer)}

    return {"format": "unknown", "animatedContainer": False}


def png_has_animation_control(buffer: bytes) -> bool:
    offset = 8
    while offset + 8 <= len(buffer):
        length = int.from_bytes(buffer[offset : offset + 4], "big")
        chunk_type = buffer[offset + 4 : offset + 8]
        if chunk_type == b"acTL":
            return True
        if chunk_type == b"IDAT":
            return False
        offset += 12 + length
    return False


def webp_is_animated(buffer: bytes) -> bool:
    offset = 12
    while offset + 8 <= len(buffer):
        chunk_type = buffer[offset : offset + 4]
        size = int.from_bytes(buffer[offset + 4 : offset + 8], "little")
        if chunk_type == b"VP8X":
            if offset + 9 > len(buffer):
                return False
            return (buffer[offset + 8] & 0x02) != 0
        if chunk_type in {b"ANIM", b"ANMF"}:
            return True
        offset += 8 + size + (size % 2)
    return False


def rank_candidates(
    candidates: list[dict[str, Any]], options: dict[str, Any]
) -> list[dict[str, Any]]:
    stem = options.get("stem")
    stem_generic = options.get("stemGeneric", False)
    anchor_ms = options["anchorMs"]
    within_ms = options["withinMs"]
    scored = []

    for candidate in candidates:
        delta = abs(candidate["mtimeMs"] - anchor_ms)
        recent = delta <= within_ms
        stem_match = (
            not stem_generic
            and stem is not None
            and candidate["stem"].lower() == stem.lower()
        )
        if stem_match and recent:
            confidence = "high"
            reason = "filename stem matches and mtime is close to the preview"
        elif stem_match:
            confidence = "medium"
            reason = "filename stem matches but mtime is outside the recent window"
        elif recent:
            confidence = "low"
            reason = "animated file near the preview mtime, no stem match"
        else:
            confidence = "low"
            reason = "animated file found, no stem match and mtime is far off"
        scored.append(
            {
                **candidate,
                "delta": delta,
                "recent": recent,
                "stemMatch": stem_match,
                "confidence": confidence,
                "reason": reason,
            }
        )

    rank = {"high": 0, "medium": 1, "low": 2}
    return sorted(
        scored,
        key=lambda candidate: (
            rank[candidate["confidence"]],
            candidate["delta"],
            candidate["path"],
        ),
    )


def format_display_path(path: str, home: Path) -> str:
    try:
        resolved = Path(path).expanduser().resolve()
        home_resolved = home.expanduser().resolve()
        try:
            relative = resolved.relative_to(home_resolved)
            return f"~/{relative}"
        except ValueError:
            return str(resolved)
    except OSError:
        return path


def build_use_original_note(path: str, home: Path) -> str:
    display_path = format_display_path(path, home)
    return (
        f"Matched the attachment to `{display_path}` and extracted frames "
        "from the original file."
    )


def build_resolution(args: dict[str, Any]) -> dict[str, Any]:
    asset = args["asset"]
    asset_format = args["assetFormat"]
    stem_info = args["stemInfo"]
    candidates = args["candidates"]
    home = Path(args.get("home") or Path.home()).expanduser().resolve()
    high_candidates = [
        candidate for candidate in candidates if candidate["confidence"] == "high"
    ]
    medium_candidates = [
        candidate for candidate in candidates if candidate["confidence"] == "medium"
    ]

    if len(high_candidates) == 1:
        best = high_candidates[0]
        return {
            "resolved": best["path"],
            "resolvedConfidence": "high",
            "recommendation": "use-original",
            "extractTarget": best["path"],
            "note": build_use_original_note(best["path"], home),
        }

    if len(high_candidates) > 1:
        paths = ", ".join(candidate["path"] for candidate in high_candidates)
        return {
            "resolved": None,
            "resolvedConfidence": None,
            "recommendation": "ask-user",
            "extractTarget": None,
            "note": (
                f"Multiple equally likely originals share this stem: {paths}. "
                "Ask the user which one to analyze before describing motion."
            ),
        }

    if len(medium_candidates) == 1:
        best = medium_candidates[0]
        return {
            "resolved": best["path"],
            "resolvedConfidence": "medium",
            "recommendation": "use-original",
            "extractTarget": best["path"],
            "note": build_use_original_note(best["path"], home),
        }

    if len(medium_candidates) > 1:
        paths = ", ".join(candidate["path"] for candidate in medium_candidates)
        return {
            "resolved": None,
            "resolvedConfidence": None,
            "recommendation": "ask-user",
            "extractTarget": None,
            "note": (
                "Multiple stale stem-matching originals were found: "
                f"{paths}. Ask the user which one to analyze before "
                "describing motion."
            ),
        }

    if asset_format["animatedContainer"]:
        stem_hint = f' for stem "{stem_info["stem"]}"' if stem_info["stem"] else ""
        other_candidates = [
            candidate
            for candidate in candidates
            if candidate["confidence"] in ("medium", "low")
        ]
        found_hint = (
            f" ({len(other_candidates)} lower-confidence candidate(s) found on "
            "disk but not trusted)"
            if other_candidates
            else ""
        )
        return {
            "resolved": None,
            "resolvedConfidence": None,
            "recommendation": "use-asset",
            "extractTarget": asset,
            "note": (
                f"No confident original source found on disk{stem_hint}"
                f"{found_hint}, but the attached preview is still a "
                f"{asset_format['format']} animation container. Extract from "
                "the preview directly; note it may be downscaled versus the "
                "original."
            ),
        }

    low_candidates = [
        candidate for candidate in candidates if candidate["confidence"] == "low"
    ]
    found_hint = (
        f" ({len(low_candidates)} weak animated-file lead(s) found on disk "
        "but not trusted)"
        if low_candidates
        else ""
    )
    if not stem_info.get("isAsset"):
        return {
            "resolved": None,
            "resolvedConfidence": None,
            "recommendation": "use-static",
            "extractTarget": None,
            "note": (
                f"The attachment is a static {asset_format['format']} image, "
                "not an animation. Describe it as a static image unless the "
                "user specifically needs motion; if motion matters, ask for "
                f"the original animated file{found_hint}."
            ),
        }
    return {
        "resolved": None,
        "resolvedConfidence": None,
        "recommendation": "ask-user",
        "extractTarget": None,
        "note": (
            f"The attachment looks like a flattened {asset_format['format']} "
            "preview "
            f"and no confident original animated file was found on disk"
            f"{found_hint}. Ask the user for the path to the original "
            ".gif/.webp before describing motion."
        ),
    }


def build_search_dirs(asset_dir: Path, cwd: Path, home: Path) -> list[dict[str, Any]]:
    dirs = [
        {"path": asset_dir, "personal": False},
        {"path": home / "Downloads", "personal": True},
        {"path": home / "Desktop", "personal": True},
        {"path": home / "Pictures", "personal": True},
        {"path": cwd, "personal": False},
    ]
    resolved = []
    seen = set()
    for entry in dirs:
        path = entry["path"].resolve()
        if path not in seen:
            seen.add(path)
            resolved.append({"path": path, "personal": entry["personal"]})
    return resolved


def collect_candidates(
    *,
    search_dirs: list[dict[str, Any]],
    walk_dir_root: Path,
    walk_max_entries: int,
    list_dir_max_entries: int = LIST_DIR_MAX_ENTRIES,
    stem: str | None,
    stem_generic: bool,
    asset_path: Path,
) -> dict[str, Any]:
    found: dict[str, dict[str, Any]] = {}
    accept_stem = stem is not None and not stem_generic
    search_truncated = False

    for entry in search_dirs:
        directory = entry["path"]
        is_personal = entry["personal"]

        # Personal directories (Downloads/Desktop/Pictures) only ever
        # contribute stem-matching candidates: when the stem is generic or
        # absent, listing/walking these dirs would otherwise surface every
        # unrelated animated file a user has (medical/tax scans,
        # screenshots, etc.) as a "low confidence" candidate, leaking its
        # full path into model context. Skip the listing entirely — not
        # just the candidates it would produce — so a personal dir is
        # neither scanned nor able to set the truncation flag for a policy
        # decision that discards its results anyway. The workspace/cwd walk
        # is not subject to this restriction since project files are not
        # the same confidentiality class.
        if is_personal and not accept_stem:
            continue

        if directory == walk_dir_root:
            walked = walk_dir(directory, WALK_MAX_DEPTH, walk_max_entries)
            files = walked["files"]
            search_truncated = search_truncated or walked["truncated"]
        else:
            listed = list_dir(directory, list_dir_max_entries)
            files = listed["files"]
            search_truncated = search_truncated or listed["truncated"]

        for file_path in files:
            if file_path == asset_path or str(file_path) in found:
                continue
            ext = file_path.suffix.lower()
            if ext not in ANIMATED_EXTENSIONS:
                continue
            candidate_stem = file_path.stem
            if accept_stem and candidate_stem.lower() != stem.lower():
                continue
            try:
                file_stat = file_path.stat()
            except OSError:
                continue
            if not file_path.is_file():
                continue
            file_format = sniff_file_format(file_path)
            if not file_format["animatedContainer"]:
                continue
            found[str(file_path)] = {
                "path": str(file_path),
                "stem": candidate_stem,
                "format": file_format["format"],
                "mtimeMs": file_stat.st_mtime * 1000,
            }

    return {
        "candidates": list(found.values()),
        "searchTruncated": search_truncated,
    }


def list_dir(
    directory: Path, max_entries: int = LIST_DIR_MAX_ENTRIES
) -> dict[str, Any]:
    try:
        files = []
        truncated = False
        for index, entry in enumerate(directory.iterdir()):
            if index >= max_entries:
                truncated = True
                break
            if entry.is_file() and not entry.is_symlink():
                files.append(entry)
        return {"files": files, "truncated": truncated}
    except OSError:
        return {"files": [], "truncated": False}


def walk_dir(
    root: Path, max_depth: int, max_entries: int = WALK_MAX_ENTRIES
) -> dict[str, Any]:
    files = []
    visited = 0
    stack = [(root, 0)]

    while stack:
        directory, depth = stack.pop()
        try:
            entries = list(os.scandir(directory))
        except OSError:
            continue

        for entry in entries:
            visited += 1
            if visited > max_entries:
                return {"files": files, "truncated": True}
            entry_path = Path(entry.path)
            if entry.is_dir(follow_symlinks=False):
                if depth >= max_depth or entry.name in WALK_IGNORE_DIRS:
                    continue
                stack.append((entry_path, depth + 1))
            elif entry.is_file(follow_symlinks=False):
                files.append(entry_path)

    return {"files": files, "truncated": False}


def sniff_file_format(file_path: Path) -> dict[str, Any]:
    try:
        with file_path.open("rb") as file:
            return sniff_format(file.read(MAGIC_SNIFF_BYTES))
    except OSError:
        return {"format": "unknown", "animatedContainer": False}


def parse_cli_args(argv: list[str]) -> dict[str, Any]:
    options: dict[str, Any] = {}
    positional = []
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg == "--within-hours":
            options["withinHours"] = _read_positive_number_option(argv, index, arg)
            index += 2
        elif arg.startswith("--"):
            raise HelperError("UNKNOWN_OPTION", f"Unknown option: {arg}")
        else:
            positional.append(arg)
            index += 1

    if len(positional) != 1:
        raise HelperError(
            "USAGE",
            "Usage: resolve_gif_source.py <asset-path> [--within-hours n]",
        )

    return {**options, "assetPath": positional[0]}


def error_result(asset_path: str | None, error: BaseException) -> dict[str, Any]:
    return {
        "version": RESULT_VERSION,
        "asset": safe_resolved_path(asset_path),
        "resolved": None,
        "resolvedConfidence": None,
        "recommendation": "ask-user",
        "extractTarget": None,
        "error": {
            "code": error.code if isinstance(error, HelperError) else "UNKNOWN",
            "message": str(error),
        },
    }


def safe_resolved_path(file_path: str | None) -> str | None:
    if file_path is None:
        return None
    try:
        return str(Path(file_path).expanduser().resolve())
    except (OSError, RuntimeError, ValueError):
        return file_path


def _read_option_value(argv: list[str], index: int, option: str) -> str:
    if index + 1 >= len(argv) or argv[index + 1].startswith("--"):
        raise HelperError("USAGE", f"{option} requires a value")
    return argv[index + 1]


def _read_finite_number_option(argv: list[str], index: int, option: str) -> float:
    value = _read_option_value(argv, index, option)
    try:
        number_value = float(value)
    except ValueError as error:
        raise HelperError("USAGE", f"{option} requires a numeric value") from error
    if not math.isfinite(number_value):
        raise HelperError("USAGE", f"{option} requires a numeric value")
    return number_value


def _read_positive_number_option(argv: list[str], index: int, option: str) -> float:
    number_value = _read_finite_number_option(argv, index, option)
    if number_value <= 0:
        raise HelperError("USAGE", f"{option} requires a positive numeric value")
    return number_value


def _positive_number(value: Any, fallback: float) -> float:
    try:
        number_value = float(value)
    except (TypeError, ValueError):
        return fallback
    if not math.isfinite(number_value) or number_value <= 0:
        return fallback
    return number_value


def main() -> int:
    options = None
    try:
        options = parse_cli_args(sys.argv[1:])
        result = resolve_gif_source(options)
        print(json.dumps(result, indent=2, allow_nan=False))
        return 0
    except Exception as error:
        print(
            json.dumps(
                error_result(options.get("assetPath") if options else None, error),
                indent=2,
                allow_nan=False,
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
