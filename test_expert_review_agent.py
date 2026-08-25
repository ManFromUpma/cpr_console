from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from expert_review_agent import EvidenceCollector, ProfessionalReviewAgent, run_review


class ExpertReviewAgentTests(unittest.TestCase):
    def make_repo(self, root: Path) -> None:
        (root / ".git").mkdir()
        (root / "cpr_output").mkdir()
        (root / "requirements.txt").write_text("pytz>=2023.3\n", encoding="utf-8")
        (root / "requirements-ci.txt").write_text("pandas\n", encoding="utf-8")
        (root / "README.md").write_text("Corporate actions may not be adjusted.\n", encoding="utf-8")
        (root / "cpr_output" / "cpr_full_20260101.csv").write_text("SYMBOL,CLOSE\nABC,1\n", encoding="utf-8")
        (root / "sample.py").write_text("def hello():\n    return 'ok'\n", encoding="utf-8")

    def test_collects_bounded_inventory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_repo(root)
            evidence = EvidenceCollector(root).collect()
            self.assertEqual(evidence["tracked_file_count"], 5)
            self.assertEqual(evidence["generated_summary"]["cpr_output"]["count"], 1)
            self.assertEqual(evidence["generated_summary"]["cpr_output"]["examples"], ["cpr_output/cpr_full_20260101.csv"])

    def test_report_has_structured_findings_and_boundaries(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_repo(root)
            agent = ProfessionalReviewAgent(root)
            findings = agent.analyze()
            report = agent.render_markdown()
            self.assertTrue(findings)
            self.assertIn("review-only", report.lower())
            self.assertIn("Repository evidence", report)
            payload = agent.report_payload()
            self.assertIn("findings", payload)
            self.assertTrue(all(item["files"] for item in payload["findings"]))

    def test_run_review_writes_markdown_and_json(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_repo(root)
            report, evidence = run_review(root)
            self.assertTrue(report.exists())
            self.assertTrue(evidence.exists())
            json.loads(evidence.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
