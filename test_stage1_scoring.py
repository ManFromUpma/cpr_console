import unittest

import pandas as pd

from cpr_scoring import SCORE_FIELDS, attach_confirmation_score, score_row
from nse_cpr_scanner import web_frame


class Stage1ScoringTests(unittest.TestCase):
    def base_row(self, **overrides):
        row = {
            "Setup": "Long",
            "CPR_Class": "Narrow",
            "CPR_Width_Pct": 0.12,
            "Price_Position": "Above CPR",
            "Above_SMA50": True,
            "Above_SMA100": True,
            "Value_Ratio": 1.25,
            "Confluence_Score": 5,
        }
        row.update(overrides)
        return row

    def test_strong_long_score_is_explainable(self):
        result = score_row(self.base_row())
        self.assertEqual(result["Signal_Direction"], "Long")
        self.assertGreaterEqual(result["Signal_Score"], 80)
        self.assertEqual(result["Signal_Grade"], "Strong confirmation")
        self.assertIn("Narrow", result["Signal_Explanation"])
        self.assertIn("aligned", result["Signal_Explanation"])
        self.assertIn("confirmed", result["Signal_Explanation"])

    def test_short_score_requires_short_aligned_confirmations(self):
        result = score_row(
            self.base_row(
                Setup="Short",
                Price_Position="Below CPR",
                Above_SMA50=False,
                Above_SMA100=False,
                Confluence_Score=-4,
            )
        )
        self.assertEqual(result["Signal_Direction"], "Short")
        self.assertGreaterEqual(result["Signal_Score"], 80)
        self.assertEqual(result["Signal_Grade"], "Strong confirmation")

    def test_opposing_trend_and_confluence_reduce_score(self):
        result = score_row(
            self.base_row(
                Above_SMA50=False,
                Above_SMA100=False,
                Confluence_Score=-4,
                Value_Ratio=0.40,
            )
        )
        self.assertLess(result["Signal_Score"], 50)
        self.assertIn("opposes", result["Signal_Explanation"])
        self.assertIn("light", result["Signal_Explanation"])

    def test_missing_confirmation_is_explicit_not_bullish(self):
        result = score_row(
            self.base_row(
                Above_SMA50=None,
                Above_SMA100=None,
                Value_Ratio=None,
                Confluence_Score=None,
            )
        )
        self.assertEqual(result["Signal_Score"], 70)
        self.assertIn("unavailable", result["Signal_Explanation"])
        self.assertNotEqual(result["Signal_Grade"], "Strong confirmation")

    def test_neutral_setup_is_not_scored_as_directional(self):
        result = score_row(self.base_row(Setup="No setup"))
        self.assertEqual(result["Signal_Direction"], "Neutral")
        self.assertEqual(result["Signal_Score"], 0)
        self.assertEqual(result["Signal_Grade"], "Not applicable")

    def test_score_is_bounded(self):
        result = score_row(self.base_row(Confluence_Score=999))
        self.assertGreaterEqual(result["Signal_Score"], 0)
        self.assertLessEqual(result["Signal_Score"], 100)

    def test_web_frame_includes_stage1_fields(self):
        frame = pd.DataFrame(
            [
                {
                    "SYMBOL": "TEST",
                    "Setup": "Long",
                    "Signal_Direction": "Long",
                    "Signal_Score": 80,
                    "Signal_Grade": "Strong confirmation",
                    "Signal_Explanation": "Narrow CPR + price above CPR + trend aligned",
                }
            ]
        )
        output = web_frame(frame)
        self.assertTrue(set(SCORE_FIELDS).issubset(output.columns))
        self.assertEqual(output.loc[0, "Signal_Score"], 80)

    def test_attach_is_additive_and_does_not_replace_existing_columns(self):
        frame = pd.DataFrame([self.base_row(), self.base_row(Setup="No setup")])
        output = attach_confirmation_score(frame)
        self.assertEqual(list(output["Setup"]), ["Long", "No setup"])
        self.assertTrue(set(SCORE_FIELDS).issubset(output.columns))
        self.assertEqual(output.loc[0, "Signal_Direction"], "Long")
        self.assertEqual(output.loc[1, "Signal_Direction"], "Neutral")


if __name__ == "__main__":
    unittest.main()
