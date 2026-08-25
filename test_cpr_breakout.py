"""Unit tests for the CPR breakout engine (no network)."""

import unittest
from datetime import datetime, timedelta

import pandas as pd
import pytz

from cpr_breakout_engine import (
    add_breakout_signals,
    add_cpr_columns,
    build_signal_frame,
    compute_cpr,
    merge_cpr_onto_intraday,
    simulate_trades,
    tag_narrow,
)


IST = pytz.timezone("Asia/Kolkata")


def _ist(y, m, d, hh=0, mm=0):
    return IST.localize(datetime(y, m, d, hh, mm))


class TestComputeCpr(unittest.TestCase):
    def test_matches_standard_hlc(self):
        p, tc, bc, width, width_pct = compute_cpr(110, 100, 106)
        self.assertAlmostEqual(p, 105.3333333333, places=6)
        self.assertAlmostEqual(bc, 105.0, places=6)
        self.assertAlmostEqual(tc, 105.6666666667, places=6)
        self.assertAlmostEqual(width, abs(tc - bc), places=6)
        self.assertAlmostEqual(width_pct, (width / 106) * 100, places=6)


class TestNarrowAndMerge(unittest.TestCase):
    def test_asof_uses_previous_session_not_today(self):
        daily_idx = pd.to_datetime(["2024-06-03", "2024-06-04", "2024-06-05"]).tz_localize("Asia/Kolkata")
        daily = pd.DataFrame(
            {
                "open": [100, 100, 100],
                "high": [110, 102, 140],
                "low": [100, 101, 90],
                "close": [106, 101.5, 120],
                "volume": [1, 1, 1],
            },
            index=daily_idx,
        )
        daily = tag_narrow(add_cpr_columns(daily), narrow_quantile=1.0)

        intra_idx = [
            _ist(2024, 6, 5, 9, 15),
            _ist(2024, 6, 5, 9, 30),
        ]
        intra = pd.DataFrame(
            {
                "open": [101.6, 101.7],
                "high": [101.8, 102.0],
                "low": [101.5, 101.6],
                "close": [101.7, 101.9],
                "volume": [1, 1],
            },
            index=pd.DatetimeIndex(intra_idx),
        )

        merged = merge_cpr_onto_intraday(intra, daily)
        self.assertFalse(merged.empty)
        # 4 Jun H/L/C = 102/101/101.5 → CPR used on 5 Jun
        expected_p, expected_tc, expected_bc, _, _ = compute_cpr(102, 101, 101.5)
        self.assertAlmostEqual(float(merged.iloc[0]["P"]), expected_p, places=5)
        self.assertAlmostEqual(float(merged.iloc[0]["TC"]), expected_tc, places=5)
        self.assertAlmostEqual(float(merged.iloc[0]["BC"]), expected_bc, places=5)
        # Must not use 5 Jun's wide 140/90/120 bar
        wide_p, _, _, _, _ = compute_cpr(140, 90, 120)
        self.assertNotAlmostEqual(float(merged.iloc[0]["P"]), wide_p, places=2)

    def test_narrow_quantile_flags_tight_band(self):
        idx = pd.to_datetime([f"2024-06-{d:02d}" for d in range(3, 13)]).tz_localize("Asia/Kolkata")
        # Wide days: close far from mid-range. Tight day: close at mid-range.
        highs = [120] * 9 + [101]
        lows = [80] * 9 + [99]
        closes = [118] * 9 + [100]
        daily = pd.DataFrame(
            {"open": closes, "high": highs, "low": lows, "close": closes, "volume": [1] * 10},
            index=idx,
        )
        tagged = tag_narrow(add_cpr_columns(daily), narrow_quantile=0.20)
        self.assertTrue(bool(tagged.iloc[-1]["narrow"]))
        self.assertFalse(bool(tagged.iloc[0]["narrow"]))


class TestSignalsAndTrades(unittest.TestCase):
    def _frame(self, closes, tc=105.67, bc=105.0, narrow=True):
        start = _ist(2024, 6, 5, 9, 15)
        idx = [start + timedelta(minutes=15 * i) for i in range(len(closes))]
        df = pd.DataFrame(
            {
                "open": closes,
                "high": [c + 0.2 for c in closes],
                "low": [c - 0.2 for c in closes],
                "close": closes,
                "volume": [1] * len(closes),
                "P": [(tc + bc) / 2] * len(closes),
                "TC": [tc] * len(closes),
                "BC": [bc] * len(closes),
                "width": [abs(tc - bc)] * len(closes),
                "width_pct": [0.2] * len(closes),
                "narrow": [narrow] * len(closes),
                "date_key": [pd.Timestamp(start.date())] * len(closes),
            },
            index=pd.DatetimeIndex(idx),
        )
        return add_breakout_signals(df, confirm_bars=1)

    def test_first_long_of_day_only(self):
        closes = [105.0, 105.8, 106.0, 106.2]
        m = self._frame(closes)
        self.assertEqual(int(m["long_entry"].sum()), 1)
        self.assertTrue(bool(m.iloc[1]["long_entry"]))
        self.assertFalse(bool(m.iloc[2]["long_entry"]))

    def test_no_signal_when_not_narrow(self):
        m = self._frame([105.0, 106.0, 106.2], narrow=False)
        self.assertEqual(int(m["long_entry"].sum()), 0)

    def test_short_below_bc(self):
        m = self._frame([105.2, 104.8, 104.5])
        self.assertEqual(int(m["short_entry"].sum()), 1)
        self.assertTrue(bool(m.iloc[1]["short_entry"]))

    def test_long_trade_hits_target(self):
        m = self._frame([105.0, 105.8, 108.0])
        m.loc[m.index[2], "high"] = 108.5
        tdf, _, equity = simulate_trades(m, rr_target=2.0, cost_bps=0.0, capital=100000)
        self.assertEqual(len(tdf), 1)
        self.assertEqual(tdf.iloc[0]["side"], "long")
        self.assertGreater(tdf.iloc[0]["pnl_pct"], 0)
        self.assertGreater(equity, 100000)

    def test_build_signal_frame_end_to_end(self):
        daily_idx = pd.to_datetime(["2024-06-03", "2024-06-04"]).tz_localize("Asia/Kolkata")
        daily = pd.DataFrame(
            {
                "open": [100, 100],
                "high": [110, 102],
                "low": [100, 101],
                "close": [106, 101.5],
                "volume": [1, 1],
            },
            index=daily_idx,
        )
        _, tc, bc, _, _ = compute_cpr(102, 101, 101.5)
        intra_idx = [_ist(2024, 6, 5, 9, 15), _ist(2024, 6, 5, 9, 30)]
        intra = pd.DataFrame(
            {
                "open": [bc, tc + 0.2],
                "high": [bc + 0.1, tc + 0.4],
                "low": [bc - 0.1, tc],
                "close": [bc, tc + 0.3],
                "volume": [1, 1],
            },
            index=pd.DatetimeIndex(intra_idx),
        )
        merged = build_signal_frame(daily, intra, narrow_quantile=1.0, confirm_bars=1)
        self.assertTrue(bool(merged.iloc[1]["long_entry"]))


if __name__ == "__main__":
    unittest.main()


class TestExecutionModel(unittest.TestCase):
    def test_slippage_is_recorded_and_reduces_long_entry(self):
        test = TestSignalsAndTrades()
        m = test._frame([105.0, 105.8, 108.0])
        m.loc[m.index[2], "high"] = 108.5
        trades, _, _ = simulate_trades(m, rr_target=2.0, cost_bps=0.0, slippage_bps=10.0, capital=100000)
        self.assertEqual(len(trades), 1)
        self.assertEqual(float(trades.iloc[0]["slippage_bps"]), 10.0)
        self.assertGreater(float(trades.iloc[0]["entry"]), float(trades.iloc[0]["entry_raw"]))

    def test_stop_first_ambiguous_bar_is_reported(self):
        test = TestSignalsAndTrades()
        m = test._frame([105.0, 105.8, 106.0])
        # The post-entry bar touches both BC and TP; conservative policy chooses stop.
        m.loc[m.index[2], "low"] = 104.0
        m.loc[m.index[2], "high"] = 108.0
        trades, _, _ = simulate_trades(m, rr_target=2.0, cost_bps=0.0, ambiguous_policy="stop_first")
        self.assertEqual(len(trades), 1)
        self.assertTrue(bool(trades.iloc[0]["ambiguous_bar"]))
        self.assertEqual(trades.iloc[0]["exit_reason"], "stop_first_ambiguous")

    def test_stop_gap_uses_open_and_is_reported(self):
        test = TestSignalsAndTrades()
        m = test._frame([105.0, 105.8, 104.0])
        m.loc[m.index[2], "open"] = 103.0
        m.loc[m.index[2], "low"] = 102.5
        trades, _, _ = simulate_trades(m, rr_target=2.0, cost_bps=0.0)
        self.assertEqual(len(trades), 1)
        self.assertTrue(bool(trades.iloc[0]["gap_exit"]))
        self.assertEqual(trades.iloc[0]["exit_reason"], "stop_gap")
        self.assertEqual(float(trades.iloc[0]["exit_raw"]), 103.0)
