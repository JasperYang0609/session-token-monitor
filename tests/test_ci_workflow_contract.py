from pathlib import Path
import unittest


class CiWorkflowContractTest(unittest.TestCase):
    def test_tiered_ci_contract(self) -> None:
        root = Path(__file__).resolve().parents[1]
        full = (root / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        branch = (root / ".github/workflows/branch-check.yml").read_text(encoding="utf-8")
        for text in ("branches: [main]", "pull_request:", "workflow_dispatch:", "cancel-in-progress: true", "python3 scripts/build_skill_archive.py --check"):
            self.assertIn(text, full)
        for text in ("branches-ignore: [main]", "pull-requests: read", "gh api --method GET", "if: needs.detect-open-pr.outputs.exists != 'true'", "bash scripts/check_push.sh"):
            self.assertIn(text, branch)


if __name__ == "__main__":
    unittest.main()
