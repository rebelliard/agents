#!/usr/bin/env python3
"""Manual smoke harness for local media fixtures — NOT part of the automated
test suite.

This script is intentionally outside `python3 -m unittest discover`: it
exercises the frame-extraction scripts against real, hand-picked media files
(GIFs/videos with actual transitions, double-clicks, etc.) that are too large
or too personal to check into the repo as fixtures. Run it manually:

    python3 tests/skills/check_frame_analysis_media.py [fixtures-dir]

The fixtures directory defaults to the `FRAME_ANALYSIS_MEDIA_DIR` environment
variable, then falls back to `~/Downloads`. Any fixture that isn't found is
skipped (printed and treated as a pass) rather than failing the run, since
these files are machine-specific and not guaranteed to exist.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]


def _fixtures_dir(argv: list[str]) -> Path:
    if len(argv) > 1:
        return Path(argv[1]).expanduser()
    env_dir = os.environ.get("FRAME_ANALYSIS_MEDIA_DIR")
    if env_dir:
        return Path(env_dir).expanduser()
    return Path.home() / "Downloads"


def _build_checks(fixtures_dir: Path) -> list[tuple[str, Path, Path]]:
    return [
        (
            "gif-demo",
            REPO / "src/skills/frame-analysis-gif/scripts/extract_gif_frames.py",
            fixtures_dir / "demo.gif",
        ),
        (
            "gif-transition-bug",
            REPO / "src/skills/frame-analysis-gif/scripts/extract_gif_frames.py",
            fixtures_dir / "transition-bug.gif",
        ),
        (
            "gif-double-click",
            REPO / "src/skills/frame-analysis-gif/scripts/extract_gif_frames.py",
            fixtures_dir / "double-click.gif",
        ),
        (
            "video-demo",
            REPO / "src/skills/frame-analysis-video/scripts/extract_video_frames.py",
            fixtures_dir / "demo.mp4",
        ),
    ]


def run_check(name: str, script: Path, media: Path) -> bool:
    print(f"## {name}")
    if not media.is_file():
        print(f"skipped (fixture not found): {media}")
        return True

    completed = subprocess.run(
        [
            "python3",
            "-B",
            str(script),
            str(media),
            "--max-frames",
            "8",
            "--max-width",
            "320",
            "--no-sheet",
        ],
        text=True,
        capture_output=True,
        timeout=180,
    )
    if completed.stderr.strip():
        print(completed.stderr.strip())
    try:
        data = json.loads(completed.stdout)
    except json.JSONDecodeError:
        print(completed.stdout[:1000])
        return False

    summary = {
        "exit": completed.returncode,
        "format": data.get("format"),
        "durationSec": data.get("durationSec"),
        "frameCount": data.get("frameCount"),
        "changedFrameCount": data.get("changedFrameCount"),
        "droppedChangeCount": data.get("droppedChangeCount"),
        "sampledCount": len(data.get("sampled", [])),
        "error": data.get("error"),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return (
        completed.returncode == 0
        and data.get("error") is None
        and isinstance(data.get("frameCount"), int)
        and data["frameCount"] > 0
        and len(data.get("sampled", [])) > 0
    )


def main() -> int:
    fixtures_dir = _fixtures_dir(sys.argv)
    print(f"using fixtures dir: {fixtures_dir}")
    ok = True
    for name, script, media in _build_checks(fixtures_dir):
        ok = run_check(name, script, media) and ok
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
