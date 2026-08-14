"""History-based EOD CPR features — overlay, own-narrow, setups. No network."""

from __future__ import annotations

import unittest

import pandas as pd

from nse_cpr_scanner import (
    MIN_VALUE_TOP20,
    apply_bullish_cpr_filters,
    attach_history_features,
    compute_cpr,
    cpr_overlay,
    split_shortlists,
)


def _bar(symbol: str, session: str, high: float, low: float, close: float, value: float = 50_000_000) -> dict:
    return {
        "SYMBOL": symbol,
        "session": session,
        "OPEN": low,
        "HIGH": high,
        "LOW": low,
        "CLOSE": close,
        "VALUE": value,
    }


class TestCprOverlay(unittest.TestCase):
    def test_higher_lower_inside_outside(self):
        self.assertEqual(cpr_overlay(110, 108, 100, 98), "Higher")
        self.assertEqual(cpr_overlay(90, 88, 100, 98), "Lower")
        self.assertEqual(cpr_overlay(99, 98.5, 100, 98), "Inside")
        self.assertEqual(cpr_overlay(101, 97, 100, 98), "Outside")
        self.assertEqual(cpr_overlay(101, 99, 100, 98), "Overlapping")
        self.assertEqual(cpr_overlay(100, 99, None, 98), "Unknown")


class TestHistoryFeatures(unittest.TestCase):
    def test_own_narrow_and_long_setup(self):
        rows = []
        # 19 wide sessions, then a tight higher CPR close above the band.
        for i in range(19):
            rows.append(_bar("AAA", f"202607{i+1:02d}", 120, 80, 110))
        rows.append(_bar("AAA", "20260814", 110.4, 109.6, 110.4))
        hist = compute_cpr(pd.DataFrame(rows))
        scan = apply_bullish_cpr_filters(hist[hist["session"] == "20260814"].copy())
        out = attach_history_features(scan, hist)
        self.assertTrue(bool(out.iloc[0]["Own_Narrow"]))
        self.assertEqual(out.iloc[0]["Overlay"], "Higher")
        self.assertEqual(out.iloc[0]["Price_Position"], "Above CPR")
        self.assertEqual(out.iloc[0]["Setup"], "Long")
        self.assertGreaterEqual(int(out.iloc[0]["History_Days"]), 10)
        self.assertLessEqual(float(out.iloc[0]["Width_Rank_Pct"]), 0.25)

    def test_short_setup_on_lower_overlay(self):
        rows = []
        for i in range(19):
            rows.append(_bar("BBB", f"202607{i+1:02d}", 120, 80, 110))
        rows.append(_bar("BBB", "20260814", 90.4, 89.6, 89.6))
        hist = compute_cpr(pd.DataFrame(rows))
        scan = apply_bullish_cpr_filters(hist[hist["session"] == "20260814"].copy())
        out = attach_history_features(scan, hist)
        self.assertEqual(out.iloc[0]["Overlay"], "Lower")
        self.assertEqual(out.iloc[0]["Price_Position"], "Below CPR")
        self.assertEqual(out.iloc[0]["Setup"], "Short")

    def test_top20_prefers_liquid_setups(self):
        rows = [
            {
                "SYMBOL": "LIQUID",
                "CLOSE": 100,
                "CPR_Width_Pct": 0.10,
                "Width_Rank_Pct": 0.05,
                "CPR_Class": "Narrow",
                "Bullish_CPR": False,
                "Bearish_CPR": False,
                "Setup": "Long",
                "Own_Narrow": True,
                "VALUE": MIN_VALUE_TOP20 * 2,
                "Bias": "Bullish",
                "Price_Position": "Above CPR",
                "Segment": "F&O + Cash",
                "Overlay": "Higher",
                "Industry": "Banks",
                "Pivot": 100.1,
                "BC": 100.0,
                "TC": 100.2,
            },
            {
                "SYMBOL": "THIN",
                "CLOSE": 12,
                "CPR_Width_Pct": 0.01,
                "Width_Rank_Pct": 0.01,
                "CPR_Class": "Narrow",
                "Bullish_CPR": True,
                "Bearish_CPR": False,
                "Setup": "Long",
                "Own_Narrow": True,
                "VALUE": 100_000,
                "Bias": "Bullish",
                "Price_Position": "Above CPR",
                "Segment": "Cash Only",
                "Overlay": "Higher",
                "Industry": "Unclassified",
                "Pivot": 12.0,
                "BC": 12.0,
                "TC": 12.0,
            },
        ]
        _, _, _, _, top20 = split_shortlists(pd.DataFrame(rows))
        self.assertEqual(list(top20["SYMBOL"]), ["LIQUID"])
        for col in ("Pivot", "BC", "TC"):
            self.assertIn(col, top20.columns)


class TestHigherTimeframe(unittest.TestCase):
    def test_friday_completes_the_week(self):
        from nse_cpr_scanner import last_complete_period_end, htf_applies_label

        self.assertEqual(last_complete_period_end("20260814", "W-FRI"), "20260814")
        self.assertEqual(last_complete_period_end("20260812", "W-FRI"), "20260807")
        self.assertEqual(last_complete_period_end("20260814", "M"), "20260731")
        self.assertIn("17 Aug", htf_applies_label("20260814", "W-FRI"))
        self.assertEqual(htf_applies_label("20260731", "M"), "Aug 2026")

    def test_weekly_bar_uses_week_high_low_close(self):
        from nse_cpr_scanner import aggregate_htf_bars, build_htf_frame

        rows = []
        # Week ending 7 Aug: high 120, low 80, close 110 on Friday
        rows.append(_bar("AAA", "20260803", 100, 90, 95))
        rows.append(_bar("AAA", "20260807", 120, 80, 110))
        # Week ending 14 Aug: high 130, low 100, close 128 on Friday
        rows.append(_bar("AAA", "20260810", 110, 100, 105))
        rows.append(_bar("AAA", "20260814", 130, 105, 128))
        hist = pd.DataFrame(rows)
        weekly = aggregate_htf_bars(hist, "W-FRI")
        last = weekly[weekly["session"] == "20260814"].iloc[0]
        self.assertEqual(last["HIGH"], 130)
        self.assertEqual(last["LOW"], 100)
        self.assertEqual(last["CLOSE"], 128)
        self.assertIn("Industry", weekly.columns)
        frame, label = build_htf_frame(hist, "20260814", "W-FRI", min_history=2)
        self.assertFalse(frame.empty)
        self.assertIn("17 Aug", label)
        self.assertIn("Industry", frame.columns)
        self.assertIn(frame.iloc[0]["Overlay"], {"Higher", "Lower", "Inside", "Outside", "Overlapping"})


class TestDailyOwnWindow(unittest.TestCase):
    def test_own_window_limits_ranking_to_recent_sessions(self):
        # 10 tight old sessions, 8 loose, 1 mid, then a 0.6-wide final close above band.
        # With own_window=10 the final is near-tightest (pct≈0.1). With the full
        # history the 10 tight old sessions push its rank above the quartile.
        hist_rows = []
        base = pd.Timestamp("2026-01-05")
        for i, (span, n) in enumerate([(0.4, 10), (2.0, 8), (1.0, 1)]):
            for j in range(n):
                d = (base + pd.Timedelta(days=len(hist_rows) + 1)).strftime("%Y%m%d")
                hist_rows.append(_bar("WWW", d, 100 + span / 2, 100 - span / 2, 100 + span / 2))
        final_d = (base + pd.Timedelta(days=len(hist_rows) + 1)).strftime("%Y%m%d")
        hist_rows.append(_bar("WWW", final_d, 100.3, 99.7, 100.3))
        hist = compute_cpr(pd.DataFrame(hist_rows))
        scan = apply_bullish_cpr_filters(hist[hist["session"] == final_d].copy())
        out = attach_history_features(scan, hist, own_window=10)
        self.assertTrue(bool(out.iloc[0]["Own_Narrow"]))
        self.assertLessEqual(int(out.iloc[0]["History_Days"]), 10)
        self.assertLessEqual(float(out.iloc[0]["Width_Rank_Pct"]), 0.25)
        out_all = attach_history_features(scan, hist)
        self.assertGreater(float(out_all.iloc[0]["Width_Rank_Pct"]), 0.25)
        self.assertFalse(bool(out_all.iloc[0]["Own_Narrow"]))


if __name__ == "__main__":
    unittest.main()
