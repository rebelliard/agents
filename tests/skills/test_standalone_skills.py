import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_ROOT = REPO_ROOT / "src/skills"


class StandaloneSkillsContractTest(unittest.TestCase):
    def test_skills_do_not_reference_other_repo_skills(self) -> None:
        skill_dirs = sorted(
            path.parent for path in SKILLS_ROOT.glob("*/SKILL.md")
        )
        skill_names = {path.name for path in skill_dirs}

        for skill_dir in skill_dirs:
            other_skill_names = skill_names - {skill_dir.name}
            for source_path in skill_dir.rglob("*.md"):
                content = source_path.read_text(encoding="utf-8")
                for other_skill_name in other_skill_names:
                    with self.subTest(
                        skill=skill_dir.name,
                        source=source_path,
                        referenced_skill=other_skill_name,
                    ):
                        self.assertNotIn(other_skill_name, content)


if __name__ == "__main__":
    unittest.main()
