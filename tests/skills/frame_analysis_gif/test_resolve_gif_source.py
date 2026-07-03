from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT_DIR = (
    Path(__file__).resolve().parents[3]
    / "src/skills/frame-analysis-gif/scripts"
)
sys.path.insert(0, str(SCRIPT_DIR))
spec = importlib.util.spec_from_file_location(
    "resolve_gif_source", SCRIPT_DIR / "resolve_gif_source.py"
)
resolve_module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(resolve_module)

GIF_HEADER = b"GIF89a"
JPEG_HEADER = bytes([0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10])
PNG_SIGNATURE = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A])


def png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + chunk_type + data + bytes(4)


def build_png(chunks: list[bytes]) -> bytes:
    return PNG_SIGNATURE + b"".join(chunks)


def webp_chunk(chunk_type: bytes, data: bytes) -> bytes:
    padding = b"\x00" if len(data) % 2 else b""
    return chunk_type + struct.pack("<I", len(data)) + data + padding


def build_webp(chunks: list[bytes]) -> bytes:
    body = b"WEBP" + b"".join(chunks)
    return b"RIFF" + struct.pack("<I", len(body)) + body


def write_fixture(file_path: Path, header: bytes, mtime_ms: float | None = None):
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(header + bytes(64))
    if mtime_ms is not None:
        seconds = mtime_ms / 1000
        os.utime(file_path, (seconds, seconds))


class ResolveGifSourceTest(unittest.TestCase):
    def test_error_result_survives_path_resolution_failure(self):
        error = resolve_module.HelperError("USAGE", "bad input")

        with mock.patch.object(
            resolve_module.Path, "resolve", side_effect=OSError("cwd missing")
        ):
            result = resolve_module.error_result("relative.png", error)

        self.assertEqual(result["asset"], "relative.png")
        self.assertEqual(result["error"]["code"], "USAGE")

    def test_cli_rejects_non_finite_within_hours_as_json(self):
        run = subprocess.run(
            [
                "python3",
                "-B",
                str(SCRIPT_DIR / "resolve_gif_source.py"),
                "--within-hours",
                "inf",
                "asset.png",
            ],
            text=True,
            capture_output=True,
        )
        parsed = json.loads(run.stdout)

        self.assertNotEqual(run.returncode, 0)
        self.assertEqual(parsed["error"]["code"], "USAGE")
        self.assertIn("--within-hours requires a numeric value", parsed["error"]["message"])

    def test_parse_asset_stem(self):
        self.assertEqual(
            resolve_module.parse_asset_stem(
                "demo-283c7eb0-7c22-401d-acee-f381a167f8cd.png"
            ),
            {"stem": "demo", "generic": False, "isAsset": True},
        )
        self.assertTrue(
            resolve_module.parse_asset_stem(
                "image-11bbe11d-8a54-4957-b457-85dd810d43c5.png"
            )["generic"]
        )
        self.assertEqual(
            resolve_module.parse_asset_stem("demo.gif"),
            {"stem": None, "generic": False, "isAsset": False},
        )

    def test_sniff_format_walks_containers(self):
        plain_png = build_png(
            [png_chunk(b"IHDR", bytes(13)), png_chunk(b"IDAT", b"....acTL....")]
        )
        apng = build_png(
            [
                png_chunk(b"IHDR", bytes(13)),
                png_chunk(b"acTL", bytes(8)),
                png_chunk(b"IDAT", bytes(8)),
            ]
        )
        static_webp = build_webp([webp_chunk(b"VP8 ", b"....ANIM....")])
        vp8x_flags = bytearray(10)
        vp8x_flags[0] = 0x02
        animated_webp = build_webp([webp_chunk(b"VP8X", bytes(vp8x_flags))])

        self.assertEqual(
            resolve_module.sniff_format(GIF_HEADER),
            {"format": "gif", "animatedContainer": True},
        )
        self.assertFalse(resolve_module.sniff_format(plain_png)["animatedContainer"])
        self.assertEqual(resolve_module.sniff_format(apng)["format"], "apng")
        self.assertFalse(resolve_module.sniff_format(static_webp)["animatedContainer"])
        self.assertTrue(resolve_module.sniff_format(animated_webp)["animatedContainer"])

    def test_rank_candidates_demotes_generic_stems(self):
        anchor_ms = 1_000_000_000_000
        ranked = resolve_module.rank_candidates(
            [
                {
                    "path": "/x/image.gif",
                    "stem": "image",
                    "format": "gif",
                    "mtimeMs": anchor_ms,
                }
            ],
            {
                "stem": "image",
                "stemGeneric": True,
                "anchorMs": anchor_ms,
                "withinMs": 48 * 60 * 60 * 1000,
            },
        )

        self.assertEqual(ranked[0]["confidence"], "low")

    def test_recovers_original_gif_by_stem(self):
        with tempfile.TemporaryDirectory() as home_dir, tempfile.TemporaryDirectory() as cwd_dir, tempfile.TemporaryDirectory() as asset_dir:
            home = Path(home_dir)
            cwd = Path(cwd_dir)
            downloads = home / "Downloads"
            downloads.mkdir()
            now = 1_700_000_000_000
            asset_path = (
                Path(asset_dir)
                / "demo-283c7eb0-7c22-401d-acee-f381a167f8cd.png"
            )
            write_fixture(asset_path, JPEG_HEADER, now)
            write_fixture(downloads / "demo.gif", GIF_HEADER, now - 60 * 60 * 1000)

            result = resolve_module.resolve_gif_source(
                {"assetPath": str(asset_path), "home": str(home), "cwd": str(cwd)}
            )

            self.assertEqual(result["assetFormat"], "jpeg")
            self.assertEqual(result["resolved"], str((downloads / "demo.gif").resolve()))
            self.assertEqual(result["recommendation"], "use-original")
            self.assertEqual(
                result["note"],
                "Matched the attachment to `~/Downloads/demo.gif` and extracted "
                "frames from the original file.",
            )

    def test_recovers_single_stale_stem_match_without_confirmation(self):
        with tempfile.TemporaryDirectory() as home_dir, tempfile.TemporaryDirectory() as cwd_dir, tempfile.TemporaryDirectory() as asset_dir:
            home = Path(home_dir)
            cwd = Path(cwd_dir)
            downloads = home / "Downloads"
            downloads.mkdir()
            now = 1_700_000_000_000
            asset_path = (
                Path(asset_dir)
                / "demo-283c7eb0-7c22-401d-acee-f381a167f8cd.png"
            )
            write_fixture(asset_path, JPEG_HEADER, now)
            write_fixture(downloads / "demo.gif", GIF_HEADER, now - 72 * 60 * 60 * 1000)

            result = resolve_module.resolve_gif_source(
                {"assetPath": str(asset_path), "home": str(home), "cwd": str(cwd)}
            )

            self.assertEqual(result["resolved"], str((downloads / "demo.gif").resolve()))
            self.assertEqual(result["resolvedConfidence"], "medium")
            self.assertEqual(result["recommendation"], "use-original")
            self.assertEqual(
                result["note"],
                "Matched the attachment to `~/Downloads/demo.gif` and extracted "
                "frames from the original file.",
            )

    def test_multiple_stale_stem_matches_still_ask_user(self):
        with tempfile.TemporaryDirectory() as home_dir, tempfile.TemporaryDirectory() as cwd_dir, tempfile.TemporaryDirectory() as asset_dir:
            home = Path(home_dir)
            cwd = Path(cwd_dir)
            downloads = home / "Downloads"
            downloads.mkdir()
            desktop = home / "Desktop"
            desktop.mkdir()
            now = 1_700_000_000_000
            asset_path = (
                Path(asset_dir)
                / "demo-283c7eb0-7c22-401d-acee-f381a167f8cd.png"
            )
            write_fixture(asset_path, JPEG_HEADER, now)
            write_fixture(downloads / "demo.gif", GIF_HEADER, now - 72 * 60 * 60 * 1000)
            write_fixture(desktop / "demo.gif", GIF_HEADER, now - 96 * 60 * 60 * 1000)

            result = resolve_module.resolve_gif_source(
                {"assetPath": str(asset_path), "home": str(home), "cwd": str(cwd)}
            )

            self.assertIsNone(result["resolved"])
            self.assertEqual(result["recommendation"], "ask-user")
            self.assertIn("Multiple stale stem-matching originals", result["note"])

    def test_generic_stem_does_not_auto_resolve_same_name_decoy(self):
        with tempfile.TemporaryDirectory() as home_dir, tempfile.TemporaryDirectory() as cwd_dir, tempfile.TemporaryDirectory() as asset_dir:
            home = Path(home_dir)
            cwd = Path(cwd_dir)
            downloads = home / "Downloads"
            downloads.mkdir()
            now = 1_700_000_000_000
            asset_path = (
                Path(asset_dir)
                / "image-283c7eb0-7c22-401d-acee-f381a167f8cd.png"
            )
            write_fixture(asset_path, JPEG_HEADER, now)
            write_fixture(downloads / "image.gif", GIF_HEADER, now)

            result = resolve_module.resolve_gif_source(
                {"assetPath": str(asset_path), "home": str(home), "cwd": str(cwd)}
            )

            self.assertTrue(result["stemGeneric"])
            self.assertIsNone(result["resolved"])
            self.assertEqual(result["recommendation"], "ask-user")

    def test_non_harness_static_image_recommends_static_description(self):
        with tempfile.TemporaryDirectory() as home_dir, tempfile.TemporaryDirectory() as cwd_dir, tempfile.TemporaryDirectory() as asset_dir:
            home = Path(home_dir)
            cwd = Path(cwd_dir)
            asset_path = Path(asset_dir) / "plain.png"
            plain_png = build_png(
                [png_chunk(b"IHDR", bytes(13)), png_chunk(b"IDAT", bytes(8))]
            )
            write_fixture(asset_path, plain_png)

            result = resolve_module.resolve_gif_source(
                {"assetPath": str(asset_path), "home": str(home), "cwd": str(cwd)}
            )

            self.assertFalse(result["stemGeneric"])
            self.assertEqual(result["recommendation"], "use-static")
            self.assertIn("Describe it as a static image", result["note"])

    def test_generic_stem_does_not_leak_unrelated_personal_dir_filenames(self):
        # A generic-stem asset (the ordinary clipboard-paste case) must not
        # surface unrelated animated files from Downloads/Desktop/Pictures as
        # low-confidence candidates — that would leak unrelated personal
        # filenames (e.g. medical/tax scans) into model context. Only
        # stem-matching files from those directories may appear.
        with tempfile.TemporaryDirectory() as home_dir, tempfile.TemporaryDirectory() as cwd_dir, tempfile.TemporaryDirectory() as asset_dir:
            home = Path(home_dir)
            cwd = Path(cwd_dir)
            downloads = home / "Downloads"
            downloads.mkdir()
            desktop = home / "Desktop"
            desktop.mkdir()
            pictures = home / "Pictures"
            pictures.mkdir()
            now = 1_700_000_000_000
            asset_path = (
                Path(asset_dir)
                / "image-283c7eb0-7c22-401d-acee-f381a167f8cd.png"
            )
            write_fixture(asset_path, JPEG_HEADER, now)
            write_fixture(downloads / "tax-return-2023.gif", GIF_HEADER, now)
            write_fixture(desktop / "mri-scan.gif", GIF_HEADER, now)
            write_fixture(pictures / "vacation.gif", GIF_HEADER, now)

            result = resolve_module.resolve_gif_source(
                {"assetPath": str(asset_path), "home": str(home), "cwd": str(cwd)}
            )

            self.assertTrue(result["stemGeneric"])
            candidate_paths = {candidate["path"] for candidate in result["candidates"]}
            self.assertEqual(candidate_paths, set())
            self.assertEqual(result["recommendation"], "ask-user")
            self.assertNotIn("tax-return", result["note"])
            self.assertNotIn("mri-scan", result["note"])
            self.assertNotIn("vacation", result["note"])

    def test_multiple_high_candidates_ask_user_even_for_animated_asset(self):
        with tempfile.TemporaryDirectory() as home_dir, tempfile.TemporaryDirectory() as cwd_dir, tempfile.TemporaryDirectory() as asset_dir:
            home = Path(home_dir)
            cwd = Path(cwd_dir)
            downloads = home / "Downloads"
            downloads.mkdir()
            desktop = home / "Desktop"
            desktop.mkdir()
            now = 1_700_000_000_000
            # The asset itself is an animated GIF (animatedContainer=True), but
            # there are two equally-likely high-confidence originals on disk.
            asset_path = (
                Path(asset_dir)
                / "demo-283c7eb0-7c22-401d-acee-f381a167f8cd.gif"
            )
            write_fixture(asset_path, GIF_HEADER, now)
            write_fixture(downloads / "demo.gif", GIF_HEADER, now - 60 * 60 * 1000)
            write_fixture(desktop / "demo.gif", GIF_HEADER, now - 30 * 60 * 1000)

            result = resolve_module.resolve_gif_source(
                {"assetPath": str(asset_path), "home": str(home), "cwd": str(cwd)}
            )

            self.assertTrue(result["assetAnimatedContainer"])
            self.assertEqual(result["recommendation"], "ask-user")
            self.assertIsNone(result["resolved"])
            candidate_paths = {candidate["path"] for candidate in result["candidates"]}
            self.assertIn(str((downloads / "demo.gif").resolve()), candidate_paths)
            self.assertIn(str((desktop / "demo.gif").resolve()), candidate_paths)

    def test_use_asset_note_counts_low_candidates_together(self):
        # build_resolution is exercised directly (rather than through the
        # full resolve_gif_source pipeline) because generic/absent stems
        # skip personal dirs before listing them, so low-confidence personal
        # candidates do not normally reach build_resolution. The note still
        # needs to count any low-confidence leads it is handed.
        candidates = [
            {
                "path": "/found/low-one.gif",
                "format": "gif",
                "mtimeMs": 0,
                "confidence": "low",
                "reason": "animated file found, no stem match and mtime is far off",
            },
            {
                "path": "/found/low-two.gif",
                "format": "gif",
                "mtimeMs": 0,
                "confidence": "low",
                "reason": "animated file found, no stem match and mtime is far off",
            },
        ]

        resolution = resolve_module.build_resolution(
            {
                "asset": "/asset/demo-uuid.gif",
                "assetFormat": {"format": "gif", "animatedContainer": True},
                "stemInfo": {"stem": "demo", "generic": False, "isAsset": True},
                "candidates": candidates,
            }
        )

        self.assertEqual(resolution["recommendation"], "use-asset")
        self.assertIn("2 lower-confidence candidate(s)", resolution["note"])

    def test_generic_stem_skips_personal_dirs_without_scanning_them(self):
        # For a generic/absent stem, personal dirs (Downloads/Desktop/
        # Pictures) must be skipped before listing — not merely have their
        # results discarded afterward. Prove it by setting an artificially
        # low listDirMaxEntries: if a personal dir were still being listed,
        # it would trip its own truncation flag even though the policy
        # throws its candidates away. searchTruncated must stay False.
        with tempfile.TemporaryDirectory() as home_dir, tempfile.TemporaryDirectory() as cwd_dir, tempfile.TemporaryDirectory() as asset_dir:
            home = Path(home_dir)
            cwd = Path(cwd_dir)
            downloads = home / "Downloads"
            downloads.mkdir()
            now = 1_700_000_000_000
            asset_path = (
                Path(asset_dir)
                / "image-283c7eb0-7c22-401d-acee-f381a167f8cd.png"
            )
            write_fixture(asset_path, JPEG_HEADER, now)
            write_fixture(downloads / "one.gif", GIF_HEADER, now)
            write_fixture(downloads / "two.gif", GIF_HEADER, now)

            collected = resolve_module.collect_candidates(
                search_dirs=[{"path": downloads, "personal": True}],
                walk_dir_root=cwd,
                walk_max_entries=resolve_module.WALK_MAX_ENTRIES,
                list_dir_max_entries=1,
                stem=None,
                stem_generic=False,
                asset_path=asset_path,
            )

            self.assertEqual(collected["candidates"], [])
            self.assertFalse(collected["searchTruncated"])

            result = resolve_module.resolve_gif_source(
                {"assetPath": str(asset_path), "home": str(home), "cwd": str(cwd)}
            )
            self.assertFalse(result["searchTruncated"])

    def test_search_truncated_emitted_at_top_level_for_cwd_walk(self):
        with tempfile.TemporaryDirectory() as home_dir, tempfile.TemporaryDirectory() as cwd_dir, tempfile.TemporaryDirectory() as asset_dir:
            home = Path(home_dir)
            cwd = Path(cwd_dir)
            now = 1_700_000_000_000
            asset_path = (
                Path(asset_dir)
                / "demo-283c7eb0-7c22-401d-acee-f381a167f8cd.png"
            )
            write_fixture(asset_path, JPEG_HEADER, now)
            write_fixture(cwd / "one.gif", GIF_HEADER, now)
            write_fixture(cwd / "two.gif", GIF_HEADER, now)

            result = resolve_module.resolve_gif_source(
                {
                    "assetPath": str(asset_path),
                    "home": str(home),
                    "cwd": str(cwd),
                    "walkMaxEntries": 1,
                }
            )

            self.assertTrue(result["searchTruncated"])

    def test_search_truncated_emitted_at_top_level_for_dir_listing(self):
        with tempfile.TemporaryDirectory() as home_dir, tempfile.TemporaryDirectory() as cwd_dir, tempfile.TemporaryDirectory() as asset_dir:
            home = Path(home_dir)
            cwd = Path(cwd_dir)
            downloads = home / "Downloads"
            downloads.mkdir()
            now = 1_700_000_000_000
            asset_path = (
                Path(asset_dir)
                / "demo-283c7eb0-7c22-401d-acee-f381a167f8cd.png"
            )
            write_fixture(asset_path, JPEG_HEADER, now)
            write_fixture(downloads / "demo.gif", GIF_HEADER, now)
            write_fixture(downloads / "demo-two.gif", GIF_HEADER, now)

            result = resolve_module.resolve_gif_source(
                {
                    "assetPath": str(asset_path),
                    "home": str(home),
                    "cwd": str(cwd),
                    "listDirMaxEntries": 1,
                }
            )

            # Non-generic stem ("demo") means Downloads is scanned (not
            # skipped), so a low listDirMaxEntries trips searchTruncated.
            self.assertFalse(result["stemGeneric"])
            self.assertTrue(result["searchTruncated"])

    def test_walk_dir_reports_truncation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_fixture(root / "one.gif", GIF_HEADER)
            write_fixture(root / "two.gif", GIF_HEADER)

            self.assertTrue(resolve_module.walk_dir(root, 4, 1)["truncated"])
            complete = resolve_module.walk_dir(root, 4, 100)
            self.assertFalse(complete["truncated"])
            self.assertEqual(len(complete["files"]), 2)

    def test_list_dir_reports_truncation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_fixture(root / "one.gif", GIF_HEADER)
            write_fixture(root / "two.gif", GIF_HEADER)

            truncated = resolve_module.list_dir(root, 1)
            self.assertTrue(truncated["truncated"])
            self.assertEqual(len(truncated["files"]), 1)

            complete = resolve_module.list_dir(root, 100)
            self.assertFalse(complete["truncated"])
            self.assertEqual(len(complete["files"]), 2)


if __name__ == "__main__":
    unittest.main()
