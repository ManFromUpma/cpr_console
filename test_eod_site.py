"""Unit tests for the EOD CPR static site (no network)."""

import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from zoneinfo import ZoneInfo

import pandas as pd

from eod_site import build_site
from nse_cpr_scanner import (
    apply_bullish_cpr_filters,
    compute_cpr,
    export_results,
    last_completed_session,
    load_scan_result,
    normalize_bhavcopy,
    tag_fo_symbols,
)

IST = ZoneInfo("Asia/Kolkata")


def _sample_cash():
    return pd.DataFrame(
        {
            "TckrSymb": ["AAA", "BBB"],
            "SctySrs": ["EQ", "EQ"],
            "OpnPric": [100.0, 50.0],
            "HghPric": [100.2, 55.0],
            "LwPric": [100.0, 45.0],
            "ClsPric": [100.15, 46.0],
        }
    )


class TestSessionDate(unittest.TestCase):
    def test_before_close_uses_previous_weekday(self):
        now = datetime(2026, 8, 14, 0, 53, tzinfo=IST)
        self.assertEqual(last_completed_session(now), "20260813")

    def test_weekend_rolls_to_friday(self):
        now = datetime(2026, 8, 16, 10, 0, tzinfo=IST)
        self.assertEqual(last_completed_session(now), "20260814")


class TestSiteBuild(unittest.TestCase):
    def test_builds_html_and_downloads(self):
        cash = normalize_bhavcopy(_sample_cash(), cash_only=True)
        cash = tag_fo_symbols(cash, pd.DataFrame({"SYMBOL": ["AAA"]}))
        cash = apply_bullish_cpr_filters(compute_cpr(cash))
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            site = Path(tmp) / "site"
            export_results(cash, "20260813", output_dir=out)
            loaded = load_scan_result("20260813", output_dir=out)
            self.assertEqual(loaded.cash_rows, 2)
            dates = build_site(out, site)
            self.assertEqual(dates, ["20260813"])
            self.assertTrue((site / "index.html").exists())
            self.assertTrue((site / "downloads" / "cpr_full.csv").exists())
            self.assertTrue((site / "downloads" / "cpr_20260813.zip").exists())
            self.assertTrue((site / "archive" / "20260813" / "index.html").exists())
            html = (site / "index.html").read_text(encoding="utf-8")
            self.assertIn("AAA", html)
            self.assertIn("window.CPR_DATA", html)
            self.assertIn("cpr_20260813.zip", html)
            self.assertIn("id=\"industry\"", html)
            self.assertIn("Unclassified", html)


if __name__ == "__main__":
    unittest.main()
