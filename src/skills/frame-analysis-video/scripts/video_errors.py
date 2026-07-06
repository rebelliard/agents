"""Error and validation helpers for video frame extraction."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from video_constants import RESULT_VERSION
from video_utils import is_generated_output_name, run_command


class HelperError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        duration_sec: float | None = None,
        fps: float | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        # Carried so post-probe error results (VIDEO_TOO_LARGE,
        # VIDEO_TOO_LONG, EMPTY_WINDOW) can surface the probed duration/fps
        # the agent needs to size a --start/--duration rerun - these errors
        # happen after probing succeeds, so the data is known but would
        # otherwise be lost once the exception crosses into error_result(),
        # which only sees the exception.
        self.duration_sec = duration_sec
        self.fps = fps


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
            f"{command} is required for video frame extraction. Install ffmpeg "
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
            f"{command} is required for video frame extraction. Install ffmpeg "
            "(ffprobe ships with it): brew install ffmpeg (macOS), apt-get "
            "update && apt-get install -y ffmpeg (Debian/Ubuntu), apk add "
            "ffmpeg (Alpine), sudo dnf install ffmpeg-free (Fedora), sudo "
            "pacman -S ffmpeg (Arch), or on Windows winget install --id "
            "Gyan.FFmpeg or choco install ffmpeg.",
        ) from error


def ensure_output_will_not_clobber_input(input_path: Path, out_dir: Path) -> None:
    if input_path.parent == out_dir and is_generated_output_name(input_path):
        raise HelperError(
            "OUTPUT_COLLISION",
            f"--out-dir {out_dir} would overwrite input {input_path}; choose "
            "a separate output directory",
        )


def short_error_message(error: BaseException) -> str:
    stderr = getattr(error, "stderr", None)
    if isinstance(stderr, str) and stderr.strip():
        lines = [line for line in stderr.strip().splitlines() if line]
        if lines:
            return lines[-1][:300]
    return str(error)[:300]


def error_result(input_path: str | None, error: BaseException) -> dict:
    fallback_code = (
        "TIMEOUT" if isinstance(error, subprocess.TimeoutExpired) else "EXTRACTION_FAILED"
    )
    code = error.code if isinstance(error, HelperError) else fallback_code
    # Post-probe errors (VIDEO_TOO_LARGE, VIDEO_TOO_LONG, EMPTY_WINDOW) fire
    # after probing already succeeded, so the probed duration/fps are known
    # - surface them here (rather than the usual None, stripped by
    # stringify_result) so the agent can size a --start/--duration rerun
    # from the error JSON alone.
    duration_sec = (
        getattr(error, "duration_sec", None) if isinstance(error, HelperError) else None
    )
    fps = getattr(error, "fps", None) if isinstance(error, HelperError) else None
    return {
        "version": RESULT_VERSION,
        "source": safe_resolved_path(input_path),
        "format": None,
        "durationSec": duration_sec,
        "fps": fps,
        "frameCount": 0,
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
