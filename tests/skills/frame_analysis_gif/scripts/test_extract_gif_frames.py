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


SCRIPT_DIR = REPO_ROOT / "src/skills/frame-analysis-gif/scripts"
sys.path.insert(0, str(SCRIPT_DIR))
spec = importlib.util.spec_from_file_location(
    "extract_gif_frames", SCRIPT_DIR / "extract_gif_frames.py"
)
extract_module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(extract_module)


HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


class GifExtractorContractTest(unittest.TestCase):
    def test_error_result_survives_path_resolution_failure(self):
        error = extract_module.HelperError("USAGE", "bad input")

        with mock.patch.object(
            extract_module.Path, "resolve", side_effect=OSError("cwd missing")
        ):
            result = extract_module.error_result("relative.gif", error)

        self.assertEqual(result["source"], "relative.gif")
        self.assertEqual(result["error"]["code"], "USAGE")

    def test_rejects_output_collision_without_deleting_input(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)
            input_path = out_dir / "frame-000.png"
            input_path.write_bytes(b"not a gif")

            with self.assertRaises(extract_module.HelperError) as ctx:
                extract_module.extract_gif_frames(
                    {"inputPath": str(input_path), "outDir": str(out_dir)}
                )

            self.assertEqual(ctx.exception.code, "OUTPUT_COLLISION")
            self.assertTrue(input_path.is_file())

    def test_cli_rejects_non_positive_max_frames_as_json(self):
        run = subprocess.run(
            [
                "python3",
                "-B",
                str(SCRIPT_DIR / "extract_gif_frames.py"),
                "--max-frames",
                "0",
                "input.gif",
            ],
            text=True,
            capture_output=True,
        )
        parsed = json.loads(run.stdout)

        self.assertNotEqual(run.returncode, 0)
        self.assertEqual(parsed["error"]["code"], "USAGE")
        self.assertIn("positive numeric value", parsed["error"]["message"])


def create_synthetic_gif(directory: Path, colors=None) -> Path:
    colors = colors or ["red", "red", "blue", "green"]
    gif_path = directory / "synthetic.gif"
    inputs = []
    for color in colors:
        inputs.extend(["-f", "lavfi", "-i", f"color=c={color}:s=120x80:d=0.3"])
    labels = "".join(f"[{index}:v]" for index in range(len(colors)))
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            *inputs,
            "-filter_complex",
            f"{labels}concat=n={len(colors)}:v=1:a=0,fps=10,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse",
            str(gif_path),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return gif_path


@unittest.skipUnless(HAS_FFMPEG, "ffmpeg/ffprobe not installed")
class ExtractGifFramesTest(unittest.TestCase):
    def test_extracts_synthetic_gif_fixture(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            # Fixture colors are ["red", "red", "blue", "green"], each a
            # 0.3s segment: red spans [0, 0.6), blue [0.6, 0.9), green
            # [0.9, 1.2).
            gif_path = create_synthetic_gif(directory)
            out_dir = directory / "out"

            result = extract_module.extract_gif_frames(
                {
                    "inputPath": str(gif_path),
                    "outDir": str(out_dir),
                    "maxFrames": 4,
                    "maxWidth": 160,
                }
            )

            self.assertEqual(result["version"], 2)
            self.assertEqual(result["source"], str(gif_path.resolve()))
            self.assertTrue(result["animated"])
            self.assertGreater(result["durationSec"], 0)
            self.assertGreater(result["frameCount"], 1)
            self.assertEqual(result["changedFrameCount"], 2)
            self.assertEqual(result["droppedChangeCount"], 0)
            self.assertEqual(result["frameSize"], {"width": 120, "height": 80})
            self.assertGreaterEqual(len(result["sampled"]), 3)
            self.assertLessEqual(len(result["sampled"]), 4)
            self.assertTrue((out_dir / result["sheets"][0]["file"]).is_file())

            # Core alignment property: a sampled frame's PNG content must
            # match the color scheduled at its claimed timestamp. Pick
            # timestamps safely inside a segment, away from cut boundaries.
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

    def test_recovers_dropped_changes_with_all_changed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            colors = ["red", "yellow", "blue", "green", "magenta", "cyan"]
            gif_path = create_synthetic_gif(directory, colors)

            truncated = extract_module.extract_gif_frames(
                {
                    "inputPath": str(gif_path),
                    "outDir": str(directory / "truncated"),
                    "maxFrames": 3,
                }
            )
            complete = extract_module.extract_gif_frames(
                {
                    "inputPath": str(gif_path),
                    "outDir": str(directory / "complete"),
                    "maxFrames": 3,
                    "allChanged": True,
                }
            )

            self.assertEqual(truncated["changedFrameCount"], len(colors) - 1)
            self.assertGreater(truncated["droppedChangeCount"], 0)
            self.assertEqual(complete["droppedChangeCount"], 0)
            self.assertGreaterEqual(len(complete["sampled"]), len(colors))

    def test_cli_reports_usage_errors_as_json(self):
        run = subprocess.run(
            [
                "python3",
                "-B",
                str(SCRIPT_DIR / "extract_gif_frames.py"),
                "--max-frames",
            ],
            text=True,
            capture_output=True,
        )
        parsed = json.loads(run.stdout)

        self.assertNotEqual(run.returncode, 0)
        self.assertEqual(parsed["error"]["code"], "USAGE")
        self.assertIn("--max-frames requires a value", parsed["error"]["message"])

    # test_parse_frame_md5_csv_timebase lives only in the video test suite
    # (tests/skills/frame_analysis_video/scripts/test_extract_video_frames.py) —
    # test_script_parity.py pins the GIF and video copies of parse_frame_md5
    # byte-for-byte identical, so a verbatim duplicate here cannot fail
    # independently of that one.

    def test_build_note_for_complete_coverage(self):
        note = extract_module.build_note(
            {
                "sampledCount": 18,
                "changedFrameCount": 17,
                "droppedChangeCount": 0,
                "loopClosed": False,
            }
        )

        self.assertIn(
            "All image changes were detected and included in the analysis.",
            note,
        )
        self.assertNotIn("step sequence is complete", note)
        self.assertIn("Animation does not loop.", note)

    def test_build_note_for_all_changed_cap(self):
        note = extract_module.build_note(
            {
                "sampledCount": 200,
                "changedFrameCount": 320,
                "droppedChangeCount": 120,
                "loopClosed": False,
                "labeled": False,
                "labelError": "drawtext filter not available in this ffmpeg build",
                "allChanged": True,
            }
        )

        self.assertIn("exceed the exhaustive cap", note)
        self.assertNotIn("--all-changed", note)
        self.assertIn("Animation does not loop.", note)
        self.assertNotIn("Sheets are unlabeled", note)


class EnsureDecodableGifTest(unittest.TestCase):
    """Resource-budget guards do not require ffmpeg — they run on plain
    metadata dicts shaped like probe_gif_container's return value."""

    def test_allows_ordinary_metadata(self):
        extract_module.ensure_decodable_gif(
            {"width": 480, "height": 270, "durationMs": 5_000, "fps": 10, "nbFrames": None}
        )

    def test_rejects_estimate_over_cap_from_duration_and_fps(self):
        # 3000s * 10fps = 30,000 estimated frames, over MAX_DECODED_FRAMES.
        with self.assertRaises(extract_module.HelperError) as ctx:
            extract_module.ensure_decodable_gif(
                {
                    "width": 480,
                    "height": 270,
                    "durationMs": 3_000_000,
                    "fps": 10,
                    "nbFrames": None,
                }
            )
        self.assertEqual(ctx.exception.code, "GIF_TOO_LONG")

    def test_rejects_absurd_canvas(self):
        with self.assertRaises(extract_module.HelperError) as ctx:
            extract_module.ensure_decodable_gif(
                {
                    "width": 20_000,
                    "height": 20_000,
                    "durationMs": 1_000,
                    "fps": 1,
                    "nbFrames": None,
                }
            )
        self.assertEqual(ctx.exception.code, "GIF_TOO_LARGE")

    def test_proceeds_when_estimate_is_unavailable(self):
        # Neither duration/fps nor nb_frames are known — GIFs are typically
        # small, so this must not over-block; the post-probe backstop
        # (ensure_probed_frame_budget) is the real guard in this case.
        extract_module.ensure_decodable_gif(
            {"width": 480, "height": 270, "durationMs": None, "fps": None, "nbFrames": None}
        )

    def test_falls_back_to_nb_frames_when_fps_unknown(self):
        with self.assertRaises(extract_module.HelperError) as ctx:
            extract_module.ensure_decodable_gif(
                {
                    "width": 480,
                    "height": 270,
                    "durationMs": 1_000,
                    "fps": None,
                    "nbFrames": 50_000,
                }
            )
        self.assertEqual(ctx.exception.code, "GIF_TOO_LONG")


class EnsureProbedFrameBudgetTest(unittest.TestCase):
    def test_allows_frame_count_at_or_under_cap(self):
        extract_module.ensure_probed_frame_budget(extract_module.MAX_DECODED_FRAMES)

    def test_rejects_frame_count_over_cap(self):
        with self.assertRaises(extract_module.HelperError) as ctx:
            extract_module.ensure_probed_frame_budget(
                extract_module.MAX_DECODED_FRAMES + 1
            )
        self.assertEqual(ctx.exception.code, "GIF_TOO_LONG")


class ResolveGifDurationMsTest(unittest.TestCase):
    """probe_gif_container is the sole source of durationSec (mirroring the
    video script's probe_video_metadata/probe_video_frames split); this
    fallback only kicks in when the container-level duration is missing."""

    def test_prefers_container_duration_when_available(self):
        frames = [{"timestampMs": 0, "durationMs": 100}, {"timestampMs": 100, "durationMs": 100}]
        self.assertEqual(extract_module.resolve_gif_duration_ms(5_000, frames), 5_000)

    def test_falls_back_to_last_frame_timestamp_plus_duration(self):
        frames = [{"timestampMs": 0, "durationMs": 100}, {"timestampMs": 100, "durationMs": 150}]
        self.assertEqual(extract_module.resolve_gif_duration_ms(None, frames), 250)

    def test_falls_back_to_last_frame_timestamp_when_duration_unknown(self):
        frames = [{"timestampMs": 0, "durationMs": 100}, {"timestampMs": 100, "durationMs": None}]
        self.assertEqual(extract_module.resolve_gif_duration_ms(None, frames), 100)

    def test_returns_zero_when_no_frames_and_no_container_duration(self):
        self.assertEqual(extract_module.resolve_gif_duration_ms(None, []), 0)


if __name__ == "__main__":
    unittest.main()
