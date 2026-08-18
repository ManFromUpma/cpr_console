import unittest

import pandas as pd

from nse_cpr_scanner import WEB_EXPORT_COLS, web_frame
from wide_cpr_strategy import WIDE_FIELDS, attach_wide_strategy, classify_wide_row, wide_table


class WideCprStrategyTests(unittest.TestCase):
    def base_row(self, **overrides):
        row = {
            "SYMBOL": "TEST",
            "Setup": "No setup",
            "CPR_Class": "Wide",
            "CPR_Width_Pct": 1.10,
            "Price_Position": "Inside CPR",
            "Above_SMA50": True,
            "Above_SMA100": True,
            "Value_Ratio": 1.20,
            "Signal_Score": 72,
        }
        row.update(overrides)
        return row

    def test_wide_inside_is_consolidation_watch(self):
        result = classify_wide_row(self.base_row())
        self.assertEqual(result["Strategy_Type"], "Wide CPR")
        self.assertEqual(result["Strategy_Setup"], "Wide Consolidation")
        self.assertEqual(result["Strategy_Confirmation"], "Watch")
        self.assertIn("inside CPR", result["Strategy_Explanation"])

    def test_wide_upside_breakout_requires_trend_and_participation(self):
        result = classify_wide_row(
            self.base_row(Price_Position="Above CPR", Above_SMA50=True, Above_SMA100=True, Value_Ratio=1.05)
        )
        self.assertEqual(result["Strategy_Setup"], "Wide Upside Breakout")
        self.assertEqual(result["Strategy_Confirmation"], "Confirmed")
        self.assertIn("trend aligned", result["Strategy_Explanation"])
        self.assertIn("participation confirmed", result["Strategy_Explanation"])

    def test_wide_upside_without_confirmation_is_watch_not_breakout(self):
        result = classify_wide_row(
            self.base_row(Price_Position="Above CPR", Above_SMA50=True, Above_SMA100=False, Value_Ratio=0.70)
        )
        self.assertEqual(result["Strategy_Setup"], "Wide Upside Watch")
        self.assertEqual(result["Strategy_Confirmation"], "Watch")
        self.assertNotEqual(result["Strategy_Setup"], "Wide Upside Breakout")

    def test_wide_downside_breakout_is_symmetric(self):
        result = classify_wide_row(
            self.base_row(
                Price_Position="Below CPR",
                Above_SMA50=False,
                Above_SMA100=False,
                Value_Ratio=1.10,
            )
        )
        self.assertEqual(result["Strategy_Setup"], "Wide Downside Breakout")
        self.assertEqual(result["Strategy_Confirmation"], "Confirmed")

    def test_missing_confirmation_is_explicitly_unavailable(self):
        result = classify_wide_row(
            self.base_row(Price_Position="Above CPR", Above_SMA50=None, Above_SMA100=None, Value_Ratio=None)
        )
        self.assertEqual(result["Strategy_Setup"], "Wide Upside Watch")
        self.assertEqual(result["Strategy_Confirmation"], "Unavailable")
        self.assertIn("unavailable", result["Strategy_Explanation"])

    def test_non_wide_rows_are_not_reclassified(self):
        row = self.base_row(CPR_Class="Narrow", Setup="Long", Signal_Score=84)
        result = classify_wide_row(row)
        self.assertEqual(result["Strategy_Type"], "Narrow CPR")
        self.assertEqual(result["Strategy_Setup"], "Not applicable")
        self.assertEqual(row["Setup"], "Long")
        self.assertEqual(row["Signal_Score"], 84)

    def test_attach_is_additive_and_preserves_existing_strategy_fields(self):
        frame = pd.DataFrame(
            [
                self.base_row(),
                self.base_row(CPR_Class="Narrow", Setup="Long"),
            ]
        )
        output = attach_wide_strategy(frame)
        self.assertTrue(set(WIDE_FIELDS).issubset(output.columns))
        self.assertEqual(list(output["Setup"]), ["No setup", "Long"])
        self.assertEqual(list(output["Signal_Score"]), [72, 72])

    def test_wide_table_is_confirmation_first(self):
        frame = pd.DataFrame(
            [
                self.base_row(SYMBOL="WATCH", Price_Position="Inside CPR", Signal_Score=90),
                self.base_row(SYMBOL="CONFIRMED", Price_Position="Above CPR", Signal_Score=70),
            ]
        )
        output = wide_table(attach_wide_strategy(frame))
        self.assertEqual(list(output["SYMBOL"]), ["CONFIRMED", "WATCH"])

    def test_public_web_schema_contains_wide_fields(self):
        self.assertTrue(set(WIDE_FIELDS).issubset(set(WEB_EXPORT_COLS)))
        frame = attach_wide_strategy(pd.DataFrame([self.base_row()]))
        output = web_frame(frame)
        self.assertTrue(set(WIDE_FIELDS).issubset(output.columns))


if __name__ == "__main__":
    unittest.main()
