from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.skills.media_asserts import assert_color_matches


SCRIPT_DIR = REPO_ROOT / "src/skills/frame-analysis-video/scripts"
sys.path.insert(0, str(SCRIPT_DIR))
spec = importlib.util.spec_from_file_location(
    "extract_video_frames", SCRIPT_DIR / "extract_video_frames.py"
)
extract_module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(extract_module)


HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _has_libx264() -> bool:
    if not HAS_FFMPEG:
        return False
    try:
        completed = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception:
        return False
    return "libx264" in completed.stdout


HAS_LIBX264 = _has_libx264()


class VideoExtractorContractTest(unittest.TestCase):
    def test_error_result_survives_path_resolution_failure(self):
        error = extract_module.HelperError("USAGE", "bad input")

        with mock.patch.object(
            extract_module.Path, "resolve", side_effect=OSError("cwd missing")
        ):
            result = extract_module.error_result("relative.mp4", error)

        self.assertEqual(result["source"], "relative.mp4")
        self.assertEqual(result["error"]["code"], "USAGE")

    def test_rejects_output_collision_without_deleting_input(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)
            input_path = out_dir / "frame-000.png"
            input_path.write_bytes(b"not a video")

            with self.assertRaises(extract_module.HelperError) as ctx:
                extract_module.extract_video_frames(
                    {"inputPath": str(input_path), "outDir": str(out_dir)}
                )

            self.assertEqual(ctx.exception.code, "OUTPUT_COLLISION")
            self.assertTrue(input_path.is_file())

    def test_cli_rejects_invalid_numeric_options_as_json(self):
        cases = [
            ("--max-frames", "0", "positive numeric value"),
            ("--start", "-1", "non-negative numeric value"),
            ("--duration", "0", "positive numeric value"),
        ]
        for option, value, expected_message in cases:
            with self.subTest(option=option):
                run = subprocess.run(
                    [
                        "python3",
                        "-B",
                        str(SCRIPT_DIR / "extract_video_frames.py"),
                        option,
                        value,
                        "input.mp4",
                    ],
                    text=True,
                    capture_output=True,
                )
                parsed = json.loads(run.stdout)

                self.assertNotEqual(run.returncode, 0)
                self.assertEqual(parsed["error"]["code"], "USAGE")
                self.assertIn(expected_message, parsed["error"]["message"])


def create_synthetic_video(
    directory: Path,
    *,
    colors=None,
    extension: str = "mp4",
    with_audio: bool = False,
    codec: str | None = None,
) -> Path:
    colors = colors or ["red", "red", "blue", "green"]
    video_path = directory / f"synthetic.{extension}"
    inputs = []
    for color in colors:
        inputs.extend(["-f", "lavfi", "-i", f"color=c={color}:s=120x80:d=0.3"])
    labels = "".join(f"[{index}:v]" for index in range(len(colors)))
    args = ["ffmpeg", "-y", *inputs]
    if with_audio:
        args.extend(
            [
                "-f",
                "lavfi",
                "-i",
                f"sine=frequency=440:duration={len(colors) * 0.3:.1f}",
            ]
        )
    args.extend(
        [
            "-filter_complex",
            f"{labels}concat=n={len(colors)}:v=1:a=0,fps=10[v]",
            "-map",
            "[v]",
        ]
    )
    if with_audio:
        args.extend(["-map", f"{len(colors)}:a", "-c:a", "aac"])
    if codec == "libx264":
        # Normal-GOP encode (libx264 defaults: keyint=250, B/P-frame
        # reordering). This is the realistic case for screen recordings —
        # a keyframe only at t=0, everything after is inter-predicted — and
        # is exactly the case where ffprobe's `-read_intervals` must use an
        # absolute end (not a `+duration` end, which is relative to where
        # the demuxer seek lands rather than to the requested start) to
        # avoid truncating or emptying a mid-GOP window.
        args.extend(
            [
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-preset",
                "ultrafast",
            ]
        )
    else:
        args.extend(["-c:v", "mpeg4", "-qscale:v", "2"])
    args.append(str(video_path))
    subprocess.run(args, check=True, capture_output=True, text=True, timeout=30)
    return video_path


def create_static_png(directory: Path) -> Path:
    png_path = directory / "static.png"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=red:s=120x80:d=0.1",
            "-frames:v",
            "1",
            str(png_path),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return png_path


@unittest.skipUnless(HAS_FFMPEG, "ffmpeg/ffprobe not installed")
class ExtractVideoFramesTest(unittest.TestCase):
    def test_extracts_synthetic_mp4_fixture(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            # Fixture colors are ["red", "red", "blue", "green"], each a
            # 0.3s segment: red spans [0, 0.6), blue [0.6, 0.9), green
            # [0.9, 1.2).
            video_path = create_synthetic_video(directory)
            out_dir = directory / "out"

            result = extract_module.extract_video_frames(
                {
                    "inputPath": str(video_path),
                    "outDir": str(out_dir),
                    "maxFrames": 4,
                    "maxWidth": 160,
                }
            )

            self.assertEqual(result["version"], 2)
            self.assertEqual(result["source"], str(video_path.resolve()))
            self.assertIn("mp4", result["format"])
            self.assertAlmostEqual(result["fps"], 10, delta=1)
            self.assertIsNone(result["window"])
            self.assertGreater(result["frameCount"], 1)
            self.assertEqual(result["changedFrameCount"], 2)
            self.assertEqual(result["droppedChangeCount"], 0)
            self.assertEqual(result["audio"], {"present": False})
            self.assertGreaterEqual(len(result["sampled"]), 3)
            self.assertTrue((out_dir / result["sheets"][0]["file"]).is_file())

            # Core alignment property: a sampled frame's PNG content must
            # match the color scheduled at its claimed timestamp.
            by_t = {sampled["t"]: sampled for sampled in result["sampled"]}
            red_sample = by_t.get(0.0)
            self.assertIsNotNone(red_sample, "expected a sampled frame at t=0.0")
            assert_color_matches(self, out_dir / red_sample["file"], "red")

            green_sample = next(
                (sampled for sampled in result["sampled"] if 0.9 < sampled["t"] < 1.2),
                None,
            )
            self.assertIsNotNone(
                green_sample, "expected a sampled frame inside the green segment"
            )
            assert_color_matches(self, out_dir / green_sample["file"], "green")

    def test_reports_audio_presence(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            video_path = create_synthetic_video(
                directory, extension="mov", with_audio=True
            )

            result = extract_module.extract_video_frames(
                {"inputPath": str(video_path), "outDir": str(directory / "out")}
            )

            self.assertIn("mov", result["format"])
            self.assertTrue(result["audio"]["present"])
            self.assertEqual(result["changedFrameCount"], 2)

    def test_windows_analysis_with_start_and_duration(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            # Colors ["red", "yellow", "blue", "green"], each a 0.3s
            # segment: red [0, 0.3), yellow [0.3, 0.6), blue [0.6, 0.9),
            # green [0.9, 1.2). The window [0.6, 1.2) starts right at the
            # blue cut, so only assert on a timestamp safely inside green.
            video_path = create_synthetic_video(
                directory, colors=["red", "yellow", "blue", "green"]
            )
            out_dir = directory / "out"

            result = extract_module.extract_video_frames(
                {
                    "inputPath": str(video_path),
                    "outDir": str(out_dir),
                    "startSeconds": 0.6,
                    "durationSeconds": 0.6,
                }
            )

            self.assertEqual(result["window"], {"startSec": 0.6, "durationSec": 0.6})
            self.assertIn("window", result["note"])
            self.assertEqual(result["frameCount"], 6)
            self.assertEqual(result["changedFrameCount"], 1)
            self.assertEqual(result["droppedChangeCount"], 0)
            for sampled in result["sampled"]:
                self.assertGreaterEqual(sampled["t"], 0.6)
                self.assertLess(sampled["t"], 1.2)

            # Core alignment property under windowing: this is the risky
            # case where ffprobe (used to pick frame indexes/timestamps) and
            # ffmpeg (used to render the PNG) must agree on frame alignment
            # after seeking with -ss/-t.
            green_sample = next(
                (sampled for sampled in result["sampled"] if 0.9 < sampled["t"] < 1.2),
                None,
            )
            self.assertIsNotNone(
                green_sample, "expected a sampled frame inside the green segment"
            )
            assert_color_matches(self, out_dir / green_sample["file"], "green")

    @unittest.skipUnless(HAS_LIBX264, "ffmpeg build lacks libx264 encoder")
    def test_windows_analysis_alignment_with_h264(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            # Same schedule as the windowed test above, but encoded with a
            # normal GOP (libx264 defaults: a keyframe only at t=0, then
            # B/P-frames). The window [0.6, 1.2) starts mid-GOP — well past
            # the only keyframe — and crosses the blue/green color boundary
            # at t=0.9, which is exactly the scenario where ffprobe's
            # `-read_intervals` must use an absolute end instead of a
            # `+duration` relative-to-seek-landing end: with the relative
            # form, the demuxer seeks back to the t=0 keyframe and `+0.6`
            # covers only [0.0, 0.6), which the helper's `timestamp_ms <
            # start_ms` filter then discards entirely, producing a false
            # EMPTY_WINDOW. This test pins both that the window isn't
            # truncated/emptied and that ffprobe (frame indexing) and ffmpeg
            # (PNG rendering) agree on frame alignment after seeking.
            video_path = create_synthetic_video(
                directory,
                colors=["red", "yellow", "blue", "green"],
                codec="libx264",
            )
            out_dir = directory / "out"

            result = extract_module.extract_video_frames(
                {
                    "inputPath": str(video_path),
                    "outDir": str(out_dir),
                    "startSeconds": 0.6,
                    "durationSeconds": 0.6,
                }
            )

            self.assertEqual(result["window"], {"startSec": 0.6, "durationSec": 0.6})
            for sampled in result["sampled"]:
                self.assertGreaterEqual(sampled["t"], 0.6)
                self.assertLess(sampled["t"], 1.2)

            blue_sample = next(
                (sampled for sampled in result["sampled"] if 0.6 <= sampled["t"] < 0.9),
                None,
            )
            self.assertIsNotNone(
                blue_sample, "expected a sampled frame inside the blue segment"
            )
            assert_color_matches(self, out_dir / blue_sample["file"], "blue")

            green_sample = next(
                (sampled for sampled in result["sampled"] if 0.9 < sampled["t"] < 1.2),
                None,
            )
            self.assertIsNotNone(
                green_sample,
                "expected a sampled frame inside the green segment — the "
                "trailing part of the window must actually be covered, not "
                "silently truncated at the keyframe-relative end",
            )
            assert_color_matches(self, out_dir / green_sample["file"], "green")

    def test_cli_reports_usage_errors_as_json(self):
        run = subprocess.run(
            [
                "python3",
                "-B",
                str(SCRIPT_DIR / "extract_video_frames.py"),
                "--duration",
            ],
            text=True,
            capture_output=True,
        )
        parsed = json.loads(run.stdout)

        self.assertNotEqual(run.returncode, 0)
        self.assertEqual(parsed["error"]["code"], "USAGE")
        self.assertIn("--duration requires a value", parsed["error"]["message"])

    def test_window_probe_args(self):
        self.assertEqual(extract_module.window_probe_args(None), [])
        self.assertEqual(
            extract_module.window_probe_args(
                {"startSeconds": 0.6, "durationSeconds": 0.6}
            ),
            ["-read_intervals", "0.6%1.2"],
        )
        self.assertEqual(
            extract_module.window_probe_args({"startSeconds": 5}),
            ["-read_intervals", "5%"],
        )

    def test_parse_frame_md5_csv_timebase(self):
        stdout = """#format: frame checksums
#version: 2
#tb 0: 1/25
#stream#, dts,        pts, duration,     size, hash
0,          0,          0,        1,    38400, aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
0,          1,          1,        1,    38400, bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
"""

        self.assertEqual(
            extract_module.parse_frame_md5(stdout),
            [
                {"timestampMs": 0, "hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},
                {"timestampMs": 40, "hash": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"},
            ],
        )

    def test_build_note_for_complete_coverage(self):
        note = extract_module.build_note(
            {
                "sampledCount": 18,
                "changedFrameCount": 17,
                "droppedChangeCount": 0,
                "window": None,
                "audio": {"present": False},
            }
        )

        self.assertIn(
            "All image changes were detected and included in the analysis.",
            note,
        )
        self.assertNotIn("step sequence is complete", note)

    def test_build_note_omits_unlabeled_sheet_detail(self):
        note = extract_module.build_note(
            {
                "sampledCount": 24,
                "changedFrameCount": 351,
                "droppedChangeCount": 328,
                "labeled": False,
                "labelError": "drawtext filter not available in this ffmpeg build",
                "window": None,
                "audio": {"present": False},
            }
        )

        self.assertIn("changed frames were not included", note)
        self.assertNotIn("Sheets are unlabeled", note)

    def test_video_too_long_error_result_json_includes_duration_and_fps(self):
        # ensure_decodable_window runs after probe_video_metadata already
        # succeeded, so durationSec/fps are known — the error must carry
        # them (both on the raised exception and in the error_result JSON)
        # so the agent can size a --start/--duration rerun without
        # re-probing.
        metadata = {
            "format": "mov,mp4,m4a,3gp,3g2,mj2",
            "durationMs": 3_000_000,
            "width": 1920,
            "height": 1080,
            "fps": 30,
            "nbFrames": None,
            "audio": {"present": False},
        }

        with self.assertRaises(extract_module.HelperError) as ctx:
            extract_module.ensure_decodable_window(metadata, None)

        self.assertEqual(ctx.exception.code, "VIDEO_TOO_LONG")
        self.assertEqual(ctx.exception.duration_sec, 3000.0)
        self.assertEqual(ctx.exception.fps, 30)

        result = extract_module.error_result("video.mp4", ctx.exception)

        self.assertEqual(result["error"]["code"], "VIDEO_TOO_LONG")
        self.assertEqual(result["durationSec"], 3000.0)
        self.assertEqual(result["fps"], 30)

    def test_empty_window_end_to_end_carries_duration_and_fps(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            # A 1.2s video; a window starting past the end produces
            # EMPTY_WINDOW via the real extract_video_frames() path.
            video_path = create_synthetic_video(directory)

            with self.assertRaises(extract_module.HelperError) as ctx:
                extract_module.extract_video_frames(
                    {
                        "inputPath": str(video_path),
                        "outDir": str(directory / "out"),
                        "startSeconds": 10,
                    }
                )

            self.assertEqual(ctx.exception.code, "EMPTY_WINDOW")
            self.assertIsNotNone(ctx.exception.duration_sec)
            self.assertIsNotNone(ctx.exception.fps)

            result = extract_module.error_result(str(video_path), ctx.exception)
            self.assertEqual(result["error"]["code"], "EMPTY_WINDOW")
            self.assertEqual(result["durationSec"], ctx.exception.duration_sec)
            self.assertEqual(result["fps"], ctx.exception.fps)

    def test_static_png_reports_still_image_instead_of_video_too_long(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            png_path = create_static_png(directory)

            with self.assertRaises(extract_module.HelperError) as ctx:
                extract_module.extract_video_frames(
                    {"inputPath": str(png_path), "outDir": str(directory / "out")}
                )

            self.assertEqual(ctx.exception.code, "STILL_IMAGE")
            result = extract_module.error_result(str(png_path), ctx.exception)
            self.assertEqual(result["error"]["code"], "STILL_IMAGE")


class EnsureDecodableCanvasTest(unittest.TestCase):
    """Resource-budget guard — no ffmpeg required, runs on plain metadata
    dicts shaped like probe_video_metadata's return value."""

    def test_allows_ordinary_metadata(self):
        extract_module.ensure_decodable_canvas(
            {"width": 1920, "height": 1080, "durationMs": 5_000, "fps": 30}
        )

    def test_rejects_absurd_canvas(self):
        with self.assertRaises(extract_module.HelperError) as ctx:
            extract_module.ensure_decodable_canvas(
                {
                    "width": 20_000,
                    "height": 20_000,
                    "durationMs": 1_000,
                    "fps": 1,
                }
            )
        self.assertEqual(ctx.exception.code, "VIDEO_TOO_LARGE")
        self.assertEqual(ctx.exception.duration_sec, 1.0)
        self.assertEqual(ctx.exception.fps, 1)

    def test_allows_zero_or_unknown_dimensions(self):
        extract_module.ensure_decodable_canvas(
            {"width": 0, "height": 0, "durationMs": 1_000, "fps": 1}
        )


class MatchHashesToFramesTest(unittest.TestCase):
    """Pure-logic tests for match_hashes_to_frames — no ffmpeg required.

    Guards the VFR fix: when the framemd5 pass emits timestamps quantized to
    the muxer's coarse timebase (derived from avg_frame_rate on variable
    frame rate sources), tolerance matching can collapse entirely even
    though the hash and frame passes decoded the exact same frames. Matching
    by position when counts are equal sidesteps timebase quantization.
    """

    def test_equal_counts_match_by_position_despite_quantized_timestamps(self):
        # Frames carry precise VFR timestamps; hash entries carry the same
        # frames' timestamps quantized to a coarse timebase (~17.46ms units,
        # mimicking demo.mov's 647/37050 muxer timebase), off by more than
        # the adaptive tolerance (median/2) would otherwise allow.
        frames = [
            {"index": 0, "timestampMs": 0},
            {"index": 1, "timestampMs": 12},
            {"index": 2, "timestampMs": 24},
            {"index": 3, "timestampMs": 36},
        ]
        tolerance_ms = extract_module.match_tolerance_ms(frames)
        self.assertLess(tolerance_ms, 8.7)

        hash_entries = [
            {"timestampMs": 0, "hash": "a" * 32},
            {"timestampMs": 17, "hash": "b" * 32},
            {"timestampMs": 17, "hash": "c" * 32},
            {"timestampMs": 35, "hash": "d" * 32},
        ]

        matched = extract_module.match_hashes_to_frames(
            frames, hash_entries, tolerance_ms
        )

        self.assertEqual(matched, ["a" * 32, "b" * 32, "c" * 32, "d" * 32])
        self.assertTrue(all(frame_hash is not None for frame_hash in matched))

    def test_unequal_counts_fall_back_to_tolerance_matching(self):
        frames = [
            {"index": 0, "timestampMs": 0},
            {"index": 1, "timestampMs": 100},
        ]
        hash_entries = [
            {"timestampMs": 0, "hash": "a" * 32},
            {"timestampMs": 50, "hash": "b" * 32},
            {"timestampMs": 100, "hash": "c" * 32},
        ]

        matched = extract_module.match_hashes_to_frames(frames, hash_entries, 10)

        self.assertEqual(matched, ["a" * 32, "c" * 32])

    def test_unequal_counts_still_respect_tolerance(self):
        frames = [{"index": 0, "timestampMs": 0}, {"index": 1, "timestampMs": 100}]
        hash_entries = [
            {"timestampMs": 0, "hash": "a" * 32},
            {"timestampMs": 50, "hash": "b" * 32},
            {"timestampMs": 60, "hash": "c" * 32},
        ]

        matched = extract_module.match_hashes_to_frames(frames, hash_entries, 10)

        self.assertEqual(matched, ["a" * 32, None])


if __name__ == "__main__":
    unittest.main()
