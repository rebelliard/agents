import json
import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SKILL_DIR = REPO_ROOT / "src/skills/orchestrate"
SKILL_PATH = SKILL_DIR / "SKILL.md"
README_PATH = SKILL_DIR / "README.md"
TASK_PACKETS_PATH = SKILL_DIR / "references/task-packets.md"
PARALLELISM_PATH = SKILL_DIR / "references/parallelism-and-retries.md"
EVALS_PATH = REPO_ROOT / "tests/skills/orchestrate/orchestration_evals.json"

CONCRETE_MODEL_PATTERN = re.compile(
    r"\b(?:[A-Z][A-Za-z]+|[A-Z]{2,}|[a-z][a-z0-9]*)"
    r"(?:[- ](?:[A-Za-z]+[- ])?)?\d+(?:[.-]\d+)+\b|\bo\d+\b",
    re.IGNORECASE,
)
MARKDOWN_LINK_PATTERN = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


class OrchestrateSkillContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.skill = SKILL_PATH.read_text(encoding="utf-8")
        self.readme = README_PATH.read_text(encoding="utf-8")
        self.task_packets = TASK_PACKETS_PATH.read_text(encoding="utf-8")
        self.parallelism = PARALLELISM_PATH.read_text(encoding="utf-8")
        self.operative_paths = [
            SKILL_PATH,
            *sorted((SKILL_DIR / "references").glob("*.md")),
        ]
        self.operative_contents = [
            path.read_text(encoding="utf-8") for path in self.operative_paths
        ]
        self.evals = json.loads(EVALS_PATH.read_text(encoding="utf-8"))

    def test_operative_files_stay_model_agnostic(self) -> None:
        for content in self.operative_contents:
            self.assertIsNone(CONCRETE_MODEL_PATTERN.search(content))

        self.assertIsNotNone(CONCRETE_MODEL_PATTERN.search(self.readme))
        self.assertIn("provenance, not policy", self.readme)

    def test_contains_standalone_role_and_recovery_policy(self) -> None:
        self.assertIn("models the current tooling actually exposes", self.skill)
        self.assertIn("Use higher effort", self.skill)
        self.assertIn("Use higher capability", self.skill)
        self.assertIn("run an independent review", self.skill)
        self.assertIn("Keep retries bounded", self.parallelism)

    def test_parallelism_is_adaptive(self) -> None:
        self.assertIn("There is no fixed worker count", self.parallelism)
        self.assertIn("Fan-out remains adaptive", self.skill)
        self.assertIn("dependency graph", self.parallelism)
        self.assertIn("Assign one worker as the owner", self.parallelism)

    def test_orchestrator_verifies_and_workers_do_not_self_review(self) -> None:
        self.assertIn("The orchestrator owns final judgment and verification", self.skill)
        self.assertIn(
            "Workers never validate their own work as the final gate",
            self.skill,
        )
        self.assertIn("A worker transcript is not evidence", self.skill)
        self.assertRegex(
            self.skill,
            r"final verification must come\s+from an independent context",
        )
        self.assertRegex(self.skill, r"not\s+independently verified")
        self.assertIn("Implementation owner:", self.task_packets)
        self.assertIn("Verification independence:", self.task_packets)

    def test_reference_files_and_relative_links_exist(self) -> None:
        for path in (TASK_PACKETS_PATH, PARALLELISM_PATH):
            self.assertTrue(path.is_file())

        for source_path in (*self.operative_paths, README_PATH):
            content = source_path.read_text(encoding="utf-8")
            for target in MARKDOWN_LINK_PATTERN.findall(content):
                if "://" in target or target.startswith("#"):
                    continue

                relative_path = target.split("#", 1)[0]
                resolved_path = source_path.parent / relative_path
                self.assertTrue(
                    resolved_path.is_file(),
                    f"Broken link in {source_path}: {target}",
                )

    def test_eval_cases_cover_orchestration_guardrails(self) -> None:
        self.assertEqual(self.evals["skill_name"], "orchestrate")
        eval_cases = self.evals["evals"]
        eval_ids = [case["id"] for case in eval_cases]
        required_ids = {
            "ambitious-multi-workstream",
            "sequential-dependency",
            "overlapping-file-ownership",
            "advisor-readonly",
            "worker-failure-routing",
            "orchestrator-takeover",
            "high-risk-review",
            "unavailable-executor",
            "future-model-generation",
            "simple-task-direct",
        }

        self.assertEqual(len(eval_ids), len(set(eval_ids)))
        self.assertTrue(required_ids.issubset(set(eval_ids)))

        for case in eval_cases:
            self.assertEqual(
                set(case),
                {"id", "prompt", "expected_output"},
            )
            for field in ("id", "prompt", "expected_output"):
                self.assertIsInstance(case[field], str)
                self.assertTrue(case[field].strip())

        expected_semantics = {
            "ambitious-multi-workstream": ("task evidence", "centrally"),
            "sequential-dependency": ("upstream dependency",),
            "overlapping-file-ownership": ("one writer",),
            "advisor-readonly": ("consequential decision point", "read-only"),
            "worker-failure-routing": ("failure evidence", "unbounded"),
            "orchestrator-takeover": ("independent context",),
            "high-risk-review": ("independent", "read-only"),
            "unavailable-executor": ("current tooling", "hard-code"),
            "future-model-generation": (
                "current availability",
                "critic roles",
            ),
            "simple-task-direct": ("direct",),
        }
        cases_by_id = {case["id"]: case for case in eval_cases}
        for eval_id, phrases in expected_semantics.items():
            expected_output = cases_by_id[eval_id]["expected_output"].lower()
            for phrase in phrases:
                self.assertIn(phrase.lower(), expected_output)


if __name__ == "__main__":
    unittest.main()
