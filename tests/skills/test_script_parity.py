"""Guard against the GIF and video helper scripts silently drifting apart.

Each pair of GIF/video scripts is an independent, self-contained copy (each
skill can be published/installed on its own), but a handful of helper
functions in each pair are meant to stay byte-for-byte identical. This test
parses both files of a pair with `ast` and compares the unparsed source of
each shared function so a future edit to one copy that forgets the other
fails loudly here instead of surfacing as a silent behavioral difference
between the GIF and video skills.

Classification is exhaustive per pair and per node kind: every top-level
function name, top-level class name, and top-level ALL_CAPS constant
assignment that exists in both scripts of a pair must be listed in exactly
one of that pair's SHARED (must match, possibly after normalization) or
ALLOWED_DIVERGENT (must NOT match, for a stated reason) categories — an
unclassified common name fails the test instead of silently going unchecked.

Some shared-in-spirit functions differ only by a fixed set of substitutable
tokens (an install-hint context word, a per-script timeout constant name).
These live in NORMALIZED_SHARED_FUNCTIONS: each entry names the two
functions plus a substitution map (old -> new token) applied to the GIF
copy's source before comparing it to the video copy's — so a one-sided edit
that changes anything else about the function still fails the test.
"""

from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

EXTRACT_GIF_SCRIPT = (
    REPO_ROOT / "src/skills/frame-analysis-gif/scripts/extract_gif_frames.py"
)
EXTRACT_VIDEO_SCRIPT = (
    REPO_ROOT / "src/skills/frame-analysis-video/scripts/extract_video_frames.py"
)
SELECT_GIF_SCRIPT = (
    REPO_ROOT / "src/skills/frame-analysis-gif/scripts/select_gif_frames.py"
)
SELECT_VIDEO_SCRIPT = (
    REPO_ROOT / "src/skills/frame-analysis-video/scripts/select_video_frames.py"
)

# Functions that are intentionally copy-pasted between the two extract
# scripts and must remain textually identical.
EXTRACT_SHARED_FUNCTIONS = [
    "_is_finite_number",
    "apply_scene_scores",
    "chunk_sampled_for_select",
    "create_contact_sheets",
    "ensure_readable_file",
    "ensure_output_will_not_clobber_input",
    "escape_drawtext",
    "first_finite_number",
    "has_drawtext_filter",
    "is_generated_output_name",
    "match_hashes_to_frames",
    "match_tolerance_ms",
    "ms_to_sec",
    "non_negative_number",
    "pad",
    "parse_frame_md5",
    "parse_frame_rate",
    "positive_integer",
    "read_finite_number_option",
    "read_non_negative_number_option",
    "read_option_value",
    "read_positive_number_option",
    "read_png_size",
    "remove_stale_outputs",
    "round_score",
    "run_command",
    "safe_resolved_path",
    "seconds_to_ms",
    "short_error_message",
    "stringify_result",
]

# Functions that are shared in spirit but differ by a small, fixed set of
# substitutable tokens (an install-hint context word, a per-script timeout
# constant name). Each entry gives the substitution map applied to the GIF
# copy's unparsed source before comparing it to the video copy's — any other
# difference still fails the test, so a one-sided edit that changes more
# than the allowed token is caught.
EXTRACT_NORMALIZED_SHARED_FUNCTIONS = {
    # Message differs only by the "GIF"/"video" context word.
    "ensure_tool": {"GIF frame extraction": "video frame extraction"},
    # References a different per-script timeout constant name
    # (COMMAND_TIMEOUT_SEC vs PROBE_TIMEOUT_SEC) — the video script has
    # multiple timeout tiers and the GIF script has one, but both are used
    # identically within the function body.
    "tile_frames": {"COMMAND_TIMEOUT_SEC": "PROBE_TIMEOUT_SEC"},
    "write_labeled_frames": {"COMMAND_TIMEOUT_SEC": "PROBE_TIMEOUT_SEC"},
}

# ALLOWED_DIVERGENT: functions that exist in both extract scripts but are
# deliberately forked and are NOT expected to match. Each entry states why,
# so a reviewer can see the divergence was a choice, not an oversight.
EXTRACT_ALLOWED_DIVERGENT = {
    # Tracks loop-wraparound (trackLoop/loopDuplicate) in the GIF script;
    # the video script has no loop concept and also threads a windowing
    # timestamp offset the GIF script doesn't need.
    "annotate_frame_hashes",
    # Video-only windowing (--start/--duration) prose; the GIF script's note
    # covers loop-closure instead.
    "build_note",
    # Video threads window_input_args(window) through the ffmpeg invocation
    # and uses the DECODE_TIMEOUT_SEC tier; the GIF script has no window
    # concept and uses its single COMMAND_TIMEOUT_SEC.
    "compute_frame_hashes",
    # GIF tracks loop-wraparound and excludes frames past the last
    # non-loop-duplicate position from the dropped-change count; the video
    # script has no loop concept.
    "count_dropped_changes",
    # Video threads window_input_args(window) and an offset_ms into
    # parse_scene_scores, and uses the DECODE_TIMEOUT_SEC tier; the GIF
    # script has no window concept.
    "detect_scene_scores",
    # Fallback error shape differs: the GIF result includes `animated`, the
    # video result includes `fps`/`window`-shaped fields — video-only
    # windowing has no GIF equivalent.
    "error_result",
    # Error code and message text differ (GIF_TOO_LONG, no --start/--duration
    # remedy) since the GIF workflow has no windowing concept; the resource
    # cap they both enforce (MAX_DECODED_FRAMES) is the same by convention,
    # not by shared code.
    "ensure_probed_frame_budget",
    # Entry point: video's argparse/JSON-emit wraps extract_video_frames
    # (windowed), GIF's wraps extract_gif_frames (no window).
    "main",
    # Video-only windowing adds --start/--duration flags and a different
    # usage string; the GIF script has no window flags.
    "parse_cli_args",
    # Video threads an offset_ms (window start) into the parsed
    # timestamps; the GIF script has no window concept.
    "parse_scene_scores",
    # Video threads window_input_args(window) through the ffmpeg invocation
    # and uses the DECODE_TIMEOUT_SEC tier; the GIF script has no window
    # concept.
    "write_sampled_frames",
}

# Top-level classes shared by name between the two extract scripts.
EXTRACT_SHARED_CLASSES: list[str] = []

EXTRACT_ALLOWED_DIVERGENT_CLASSES = {
    # Both scripts define a HelperError(code, message) exception, but the
    # video script's __init__ also threads duration_sec/fps so post-probe
    # error results (VIDEO_TOO_LARGE, VIDEO_TOO_LONG, EMPTY_WINDOW) can
    # carry the already-probed duration/fps for sizing a --start/--duration
    # rerun; the GIF workflow has no windowing concept and so no use for
    # those fields.
    "HelperError",
}

# Top-level ALL_CAPS constants that must hold the same value in both extract
# scripts (shared resource caps / defaults, not implementation-tier knobs).
EXTRACT_SHARED_CONSTANTS = [
    "RESULT_VERSION",
    "DEFAULT_MAX_WIDTH",
    "DEFAULT_SCENE_THRESHOLD",
    "ALL_CHANGED_FRAME_CAP",
    "MAX_DECODED_FRAMES",
    "MAX_CANVAS_PIXELS",
    "TILE_MAX_WIDTH",
    "SHEET_TARGET_WIDTH",
    "MAX_TILES_PER_SHEET",
    "MAX_SELECT_TERMS_PER_PASS",
]

EXTRACT_ALLOWED_DIVERGENT_CONSTANTS: set[str] = set()
# Note: the GIF script has a single COMMAND_TIMEOUT_SEC tier; the video
# script splits probing (PROBE_TIMEOUT_SEC) from decoding
# (DECODE_TIMEOUT_SEC) since decode passes run much longer. Neither name is
# common to both scripts, so there is nothing to classify here — the
# asymmetry never reaches this allowlist in practice.

# Functions that are intentionally copy-pasted between the two select
# scripts and must remain textually identical.
SELECT_SHARED_FUNCTIONS = [
    "_add_coverage_frames",
    "_add_frame",
    "_change_key",
    "_clamp_integer",
    "_fill_evenly_spaced_frames",
    "_is_finite_number",
    "_time_key",
]

SELECT_NORMALIZED_SHARED_FUNCTIONS: dict[str, dict[str, str]] = {}

# ALLOWED_DIVERGENT: functions that exist in both select scripts but are
# deliberately forked and are NOT expected to match. Each entry states why.
SELECT_ALLOWED_DIVERGENT = {
    # GIF tracks loop fields (loopDeltaFromFirst/loopDuplicate) so later
    # loop-dedupe logic can identify wraparound-duplicate frames; the video
    # script has no loop concept and drops those fields entirely.
    "normalize_frames",
}

SELECT_SHARED_CLASSES: list[str] = []
SELECT_ALLOWED_DIVERGENT_CLASSES: set[str] = set()

SELECT_SHARED_CONSTANTS = [
    "DEFAULT_MAX_FRAMES",
    "DEFAULT_MIN_FRAMES",
    "DEFAULT_SCENE_THRESHOLD",
]

SELECT_ALLOWED_DIVERGENT_CONSTANTS: set[str] = set()
# Note: DEFAULT_LOOP_DEDUPE_THRESHOLD exists only in the GIF script (no
# video loop concept), so it is never "common" to both scripts and never
# reaches this allowlist in practice.

PAIRS = [
    {
        "name": "extract",
        "gif_script": EXTRACT_GIF_SCRIPT,
        "video_script": EXTRACT_VIDEO_SCRIPT,
        "shared": EXTRACT_SHARED_FUNCTIONS,
        "normalized_shared": EXTRACT_NORMALIZED_SHARED_FUNCTIONS,
        "allowed_divergent": EXTRACT_ALLOWED_DIVERGENT,
        "shared_classes": EXTRACT_SHARED_CLASSES,
        "allowed_divergent_classes": EXTRACT_ALLOWED_DIVERGENT_CLASSES,
        "shared_constants": EXTRACT_SHARED_CONSTANTS,
        "allowed_divergent_constants": EXTRACT_ALLOWED_DIVERGENT_CONSTANTS,
    },
    {
        "name": "select",
        "gif_script": SELECT_GIF_SCRIPT,
        "video_script": SELECT_VIDEO_SCRIPT,
        "shared": SELECT_SHARED_FUNCTIONS,
        "normalized_shared": SELECT_NORMALIZED_SHARED_FUNCTIONS,
        "allowed_divergent": SELECT_ALLOWED_DIVERGENT,
        "shared_classes": SELECT_SHARED_CLASSES,
        "allowed_divergent_classes": SELECT_ALLOWED_DIVERGENT_CLASSES,
        "shared_constants": SELECT_SHARED_CONSTANTS,
        "allowed_divergent_constants": SELECT_ALLOWED_DIVERGENT_CONSTANTS,
    },
]


def _parse_top_level_functions(path: Path) -> dict[str, str]:
    tree = ast.parse(path.read_text())
    return {
        node.name: ast.unparse(node)
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }


def _parse_top_level_classes(path: Path) -> dict[str, str]:
    tree = ast.parse(path.read_text())
    return {
        node.name: ast.unparse(node)
        for node in tree.body
        if isinstance(node, ast.ClassDef)
    }


def _parse_top_level_constants(path: Path) -> dict[str, str]:
    tree = ast.parse(path.read_text())
    constants: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if isinstance(target, ast.Name) and target.id.isupper():
            constants[target.id] = ast.unparse(node.value)
    return constants


def _normalize(source: str, substitutions: dict[str, str]) -> str:
    normalized = source
    for old, new in substitutions.items():
        normalized = re.sub(re.escape(old), new, normalized)
    return normalized


def _make_pair_test_case(pair: dict) -> type[unittest.TestCase]:
    gif_script = pair["gif_script"]
    video_script = pair["video_script"]
    shared = pair["shared"]
    normalized_shared = pair["normalized_shared"]
    allowed_divergent = pair["allowed_divergent"]
    shared_classes = pair["shared_classes"]
    allowed_divergent_classes = pair["allowed_divergent_classes"]
    shared_constants = pair["shared_constants"]
    allowed_divergent_constants = pair["allowed_divergent_constants"]

    class PairParityTest(unittest.TestCase):
        def test_shared_functions_are_textually_identical(self):
            gif_functions = _parse_top_level_functions(gif_script)
            video_functions = _parse_top_level_functions(video_script)

            for name in shared:
                self.assertIn(name, gif_functions, f"{name} missing from {gif_script}")
                self.assertIn(
                    name, video_functions, f"{name} missing from {video_script}"
                )
                self.assertEqual(
                    gif_functions[name],
                    video_functions[name],
                    f"{gif_script.name} and {video_script.name} copies of "
                    f"'{name}' have drifted apart — keep shared helpers "
                    "byte-for-byte identical or move the function to "
                    "ALLOWED_DIVERGENT with a reason.",
                )

        def test_normalized_shared_functions_match_after_substitution(self):
            gif_functions = _parse_top_level_functions(gif_script)
            video_functions = _parse_top_level_functions(video_script)

            for name, substitutions in normalized_shared.items():
                self.assertIn(name, gif_functions, f"{name} missing from {gif_script}")
                self.assertIn(
                    name, video_functions, f"{name} missing from {video_script}"
                )
                normalized_gif = _normalize(gif_functions[name], substitutions)
                self.assertEqual(
                    normalized_gif,
                    video_functions[name],
                    f"{gif_script.name} and {video_script.name} copies of "
                    f"'{name}' differ by more than the allowed substitution "
                    f"{substitutions} — keep them identical apart from that "
                    "token or update the substitution map.",
                )

        def test_allowed_divergent_list_does_not_overlap_shared_list(self):
            self.assertEqual(set(shared) & allowed_divergent, set())
            self.assertEqual(set(normalized_shared) & allowed_divergent, set())
            self.assertEqual(set(normalized_shared) & set(shared), set())

        def test_allowed_divergent_functions_actually_differ(self):
            gif_functions = _parse_top_level_functions(gif_script)
            video_functions = _parse_top_level_functions(video_script)

            for name in sorted(allowed_divergent):
                if name not in gif_functions or name not in video_functions:
                    # Not common to both scripts (e.g. video-only windowing
                    # helpers); nothing to guard here.
                    continue
                self.assertNotEqual(
                    gif_functions[name],
                    video_functions[name],
                    f"'{name}' is listed in ALLOWED_DIVERGENT but the two "
                    "copies are now textually identical — move it to "
                    "SHARED_FUNCTIONS instead of leaving a stale allowlist "
                    "entry.",
                )

        def test_every_common_function_is_classified(self):
            gif_functions = _parse_top_level_functions(gif_script)
            video_functions = _parse_top_level_functions(video_script)
            common = set(gif_functions) & set(video_functions)
            classified = set(shared) | set(normalized_shared) | allowed_divergent
            unclassified = sorted(common - classified)

            self.assertEqual(
                unclassified,
                [],
                "Functions defined in both scripts are not classified in "
                "SHARED_FUNCTIONS, NORMALIZED_SHARED_FUNCTIONS, or "
                f"ALLOWED_DIVERGENT: {unclassified}. Add each to whichever "
                "category matches its intended behavior (identical, "
                "identical-after-token-substitution, or deliberately "
                "forked with a reason).",
            )

        def test_shared_classes_are_textually_identical(self):
            gif_classes = _parse_top_level_classes(gif_script)
            video_classes = _parse_top_level_classes(video_script)

            for name in shared_classes:
                self.assertIn(name, gif_classes, f"{name} missing from {gif_script}")
                self.assertIn(name, video_classes, f"{name} missing from {video_script}")
                self.assertEqual(
                    gif_classes[name],
                    video_classes[name],
                    f"{gif_script.name} and {video_script.name} copies of "
                    f"class '{name}' have drifted apart — keep shared "
                    "classes byte-for-byte identical or move the class to "
                    "ALLOWED_DIVERGENT_CLASSES with a reason.",
                )

        def test_allowed_divergent_classes_actually_differ(self):
            gif_classes = _parse_top_level_classes(gif_script)
            video_classes = _parse_top_level_classes(video_script)

            for name in sorted(allowed_divergent_classes):
                if name not in gif_classes or name not in video_classes:
                    continue
                self.assertNotEqual(
                    gif_classes[name],
                    video_classes[name],
                    f"'{name}' is listed in ALLOWED_DIVERGENT_CLASSES but "
                    "the two copies are now textually identical — move it "
                    "to SHARED_CLASSES instead of leaving a stale "
                    "allowlist entry.",
                )

        def test_every_common_class_is_classified(self):
            gif_classes = _parse_top_level_classes(gif_script)
            video_classes = _parse_top_level_classes(video_script)
            common = set(gif_classes) & set(video_classes)
            classified = set(shared_classes) | allowed_divergent_classes
            unclassified = sorted(common - classified)

            self.assertEqual(
                unclassified,
                [],
                "Classes defined in both scripts are not classified in "
                "SHARED_CLASSES or ALLOWED_DIVERGENT_CLASSES: "
                f"{unclassified}. Add each to whichever list matches its "
                "intended behavior (identical vs. deliberately forked, "
                "with a reason).",
            )

        def test_shared_constants_are_equal(self):
            gif_constants = _parse_top_level_constants(gif_script)
            video_constants = _parse_top_level_constants(video_script)

            for name in shared_constants:
                self.assertIn(name, gif_constants, f"{name} missing from {gif_script}")
                self.assertIn(
                    name, video_constants, f"{name} missing from {video_script}"
                )
                self.assertEqual(
                    gif_constants[name],
                    video_constants[name],
                    f"{gif_script.name} and {video_script.name} copies of "
                    f"constant '{name}' have drifted apart — keep shared "
                    "resource caps/defaults equal or move the constant to "
                    "ALLOWED_DIVERGENT_CONSTANTS with a reason.",
                )

        def test_allowed_divergent_constants_actually_differ(self):
            gif_constants = _parse_top_level_constants(gif_script)
            video_constants = _parse_top_level_constants(video_script)

            for name in sorted(allowed_divergent_constants):
                if name not in gif_constants or name not in video_constants:
                    continue
                self.assertNotEqual(
                    gif_constants[name],
                    video_constants[name],
                    f"'{name}' is listed in ALLOWED_DIVERGENT_CONSTANTS but "
                    "the two copies now hold the same value — move it to "
                    "SHARED_CONSTANTS instead of leaving a stale allowlist "
                    "entry.",
                )

        def test_every_common_constant_is_classified(self):
            gif_constants = _parse_top_level_constants(gif_script)
            video_constants = _parse_top_level_constants(video_script)
            common = set(gif_constants) & set(video_constants)
            classified = set(shared_constants) | allowed_divergent_constants
            unclassified = sorted(common - classified)

            self.assertEqual(
                unclassified,
                [],
                "Top-level ALL_CAPS constants defined in both scripts are "
                "not classified in SHARED_CONSTANTS or "
                f"ALLOWED_DIVERGENT_CONSTANTS: {unclassified}. Add each to "
                "whichever list matches its intended behavior (must be "
                "equal vs. deliberately different, with a reason).",
            )

    return PairParityTest


for _pair in PAIRS:
    _test_case = _make_pair_test_case(_pair)
    _test_case.__name__ = f"ScriptParityTest_{_pair['name']}"
    _test_case.__qualname__ = _test_case.__name__
    globals()[_test_case.__name__] = _test_case

del _pair, _test_case


if __name__ == "__main__":
    unittest.main()
