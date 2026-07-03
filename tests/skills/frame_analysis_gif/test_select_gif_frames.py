from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT_DIR = (
    Path(__file__).resolve().parents[3]
    / "src/skills/frame-analysis-gif/scripts"
)
sys.path.insert(0, str(SCRIPT_DIR))
spec = importlib.util.spec_from_file_location(
    "select_gif_frames", SCRIPT_DIR / "select_gif_frames.py"
)
select_module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(select_module)


def frame(index: int, change_score: float = 0, **extras):
    return {
        "index": index,
        "timestampMs": index * 100,
        "changeScore": change_score,
        **extras,
    }


class SelectGifFramesTest(unittest.TestCase):
    def test_returns_single_frame_unchanged(self):
        self.assertEqual(select_module.select_gif_frames([frame(0)]), [frame(0)])

    def test_dedupes_loop_wraparound(self):
        selected = select_module.select_gif_frames(
            [
                frame(0),
                frame(1, 0.2),
                frame(2, 0.01, loopDeltaFromFirst=0.005),
            ]
        )

        self.assertEqual([item["index"] for item in selected], [0, 1])

    def test_captures_hash_distinct_changes_when_budget_allows(self):
        frames = [
            frame(0),
            *[
                frame(offset + 1, 0.004, hashChanged=True)
                for offset in range(8)
            ],
            frame(9, 0, hashChanged=False),
        ]

        selected = select_module.select_gif_frames(frames, {"maxFrames": 24})

        self.assertEqual([item["index"] for item in selected], list(range(10)))

    def test_spreads_budget_across_time_when_changes_exceed_it(self):
        frames = [
            frame(0),
            *[
                frame(offset + 1, 0.01, hashChanged=True)
                for offset in range(20)
            ],
        ]

        selected = select_module.select_gif_frames(frames, {"maxFrames": 6})

        self.assertEqual([item["index"] for item in selected], [0, 1, 5, 10, 15, 20])

    def test_normalizes_missing_indexes_and_timestamps(self):
        selected = select_module.select_gif_frames(
            [{}, {"changeScore": 0.4}, {}], {"maxFrames": 3}
        )

        self.assertEqual([item["index"] for item in selected], [0, 1, 2])
        self.assertEqual([item["timestampMs"] for item in selected], [0, 1, 2])


if __name__ == "__main__":
    unittest.main()
