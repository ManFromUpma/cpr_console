"""
CPR Breakout screener and backtest engine.

Separate from the Shah CPR live console (`cpr_engine.py` / `app.py`).
This module does not change CPR formulas used by the main screener.

Strategy (intraday, typically 15m):
- CPR for session D comes from the previous completed daily bar (H/L/C).
- Narrow = that CPR width % is in the bottom quantile of the symbol's history.
- Long: consecutive closes above TC. Short: consecutive closes below BC.
- First signal of the day only. Stop at BC (long) / TC (short). Target = RR × risk.
- Flat by 15:15 session time.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import pytz

from cpr_contract import calculate_cpr, calculate_cpr_frame
from data_provider import _extract_symbol_ohlcv, _yahoo_download_chunked
from signal_contract import BreakoutSignal, breakout_signal_rank
from universe import classify_symbol


SESSION_TZ = "Asia/Kolkata"
EOD_FLAT = time(15, 15)
INTRADAY_MAX_DAYS = {
    "1m": 7,
    "2m": 59,
    "5m": 59,
    "15m": 59,
    "30m": 59,
    "60m": 729,
    "1h": 729,
}


def compute_cpr(high: float, low: float, close: float) -> Tuple[float, float, float, float, float]:
    """Pivot, TC, BC, absolute width, and width % of close."""
    levels = calculate_cpr(high, low, close)
    return levels.pivot, levels.tc, levels.bc, levels.width, levels.width_pct


def add_cpr_columns(daily: pd.DataFrame) -> pd.DataFrame:
    """Vectorized CPR columns from daily OHLC (lowercase column names)."""
    d = daily.copy()
    canonical = calculate_cpr_frame(
        d,
        high_col="high",
        low_col="low",
        close_col="close",
    )
    d["P"] = canonical["pivot"]
    d["TC"] = canonical["tc"]
    d["BC"] = canonical["bc"]
    d["width"] = canonical["width"]
    d["width_pct"] = canonical["width_pct"]
    return d.dropna(subset=["P", "TC", "BC", "width_pct"])


def tag_narrow(
    daily_cpr: pd.DataFrame,
    narrow_quantile: float = 0.25,
    min_width_pct: Optional[float] = None,
) -> pd.DataFrame:
    d = daily_cpr.copy()
    q = d["width_pct"].quantile(narrow_quantile)
    # Rank so equal-wide days are not all flagged when the quantile lands on a tie.
    d["narrow"] = d["width_pct"].rank(method="average", pct=True) <= narrow_quantile
    if min_width_pct is not None:
        d["narrow"] = d["narrow"] & (d["width_pct"] <= min_width_pct)
    d["narrow_threshold"] = q
    return d


def _session_zone(name: str = SESSION_TZ):
    return pytz.timezone(name)


def to_session_index(df: pd.DataFrame, session_timezone: str = SESSION_TZ) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    out = df.copy()
    idx = pd.to_datetime(out.index)
    zone = _session_zone(session_timezone)
    if getattr(idx, "tz", None) is None:
        idx = idx.tz_localize("UTC")
    out.index = idx.tz_convert(zone)
    out = out[~out.index.duplicated(keep="last")].sort_index()
    return out


def session_dates(index: pd.DatetimeIndex, session_timezone: str = SESSION_TZ) -> pd.Series:
    zone = _session_zone(session_timezone)
    stamps = pd.DatetimeIndex(pd.to_datetime(index))
    if stamps.tz is None:
        stamps = stamps.tz_localize(zone)
    else:
        stamps = stamps.tz_convert(zone)
    return pd.Series(stamps.date, index=index)


def merge_cpr_onto_intraday(
    intraday: pd.DataFrame,
    daily_cpr: pd.DataFrame,
    session_timezone: str = SESSION_TZ,
) -> pd.DataFrame:
    """
    Attach previous-session CPR to each intraday bar.

    Session D uses the last daily bar strictly before D, so today's incomplete
    daily candle is never used as today's CPR input.
    """
    if intraday is None or intraday.empty or daily_cpr is None or daily_cpr.empty:
        return pd.DataFrame()

    intra = to_session_index(intraday, session_timezone)
    daily = to_session_index(daily_cpr, session_timezone)
    intra = intra.copy()
    intra["date_key"] = pd.to_datetime(session_dates(intra.index, session_timezone).values)

    keep = ["P", "TC", "BC", "width", "width_pct", "narrow", "narrow_threshold"]
    cols = [c for c in keep if c in daily.columns]
    daily_reset = daily[cols].copy()
    daily_reset["date_key"] = pd.to_datetime(session_dates(daily.index, session_timezone).values)
    daily_reset = daily_reset.dropna(subset=["TC", "BC"]).sort_values("date_key")

    intra_reset = intra.reset_index().rename(columns={intra.index.name or "index": "Datetime"})
    if "Datetime" not in intra_reset.columns:
        intra_reset = intra_reset.rename(columns={intra_reset.columns[0]: "Datetime"})
    intra_reset = intra_reset.sort_values("date_key")

    merged = pd.merge_asof(
        intra_reset,
        daily_reset,
        on="date_key",
        direction="backward",
        allow_exact_matches=False,
    )
    merged = merged.dropna(subset=["TC", "BC"]).set_index("Datetime").sort_index()
    return merged


def add_breakout_signals(merged: pd.DataFrame, confirm_bars: int = 1) -> pd.DataFrame:
    """First confirmed TC/BC break of the day on a narrow CPR session."""
    m = merged.copy()
    confirm_bars = max(int(confirm_bars), 1)
    if "date_key" in m.columns:
        m["day"] = pd.to_datetime(m["date_key"]).dt.date
    else:
        m["day"] = session_dates(m.index).values

    m["above_TC"] = m["close"] > m["TC"]
    m["below_BC"] = m["close"] < m["BC"]
    narrow = m["narrow"].fillna(False).astype(bool)

    def _confirmed(series: pd.Series) -> pd.Series:
        rolled = series.astype(int).rolling(confirm_bars, min_periods=confirm_bars).sum()
        return rolled == confirm_bars

    m["long_signal"] = m.groupby("day", sort=False)["above_TC"].transform(_confirmed) & narrow
    m["short_signal"] = m.groupby("day", sort=False)["below_BC"].transform(_confirmed) & narrow
    m["long_signal"] = m["long_signal"].fillna(False).astype(bool)
    m["short_signal"] = m["short_signal"].fillna(False).astype(bool)

    m["long_entry"] = m["long_signal"] & (m.groupby("day")["long_signal"].cumsum() == 1)
    m["short_entry"] = m["short_signal"] & (m.groupby("day")["short_signal"].cumsum() == 1)
    return m


def _bar_time(ts) -> time:
    stamp = pd.Timestamp(ts)
    if stamp.tzinfo is not None:
        stamp = stamp.tz_convert(_session_zone())
    return stamp.time()


def simulate_trades(
    merged: pd.DataFrame,
    rr_target: float = 2.0,
    risk_pct: float = 0.01,
    capital: float = 100000.0,
    cost_bps: float = 5.0,
    slippage_bps: float = 0.0,
    eod_flat: time = EOD_FLAT,
    ambiguous_policy: str = "stop_first",
) -> Tuple[pd.DataFrame, pd.DataFrame, float]:
    """Backtest first daily signal with explicit conservative execution assumptions.

    ``cost_bps`` is the existing round-trip cost allowance. ``slippage_bps`` is
    applied on both entry and exit: adverse for the trade direction. If a bar
    touches both stop and target, ``ambiguous_policy`` chooses ``stop_first``
    (the conservative default) or ``target_first``. If a bar opens beyond a
    stop/target, the open is used as the gap fill rather than the requested level.
    """
    if rr_target <= 0 or risk_pct <= 0 or capital <= 0:
        raise ValueError("rr_target, risk_pct, and capital must be positive")
    if cost_bps < 0 or slippage_bps < 0:
        raise ValueError("cost_bps and slippage_bps cannot be negative")
    if ambiguous_policy not in {"stop_first", "target_first"}:
        raise ValueError("ambiguous_policy must be 'stop_first' or 'target_first'")

    slip = slippage_bps / 10000.0
    trades: List[Dict] = []
    equity_curve: List[Dict] = []
    position = 0
    entry_price = entry_raw = entry_time = sl = tp = None
    equity = float(capital)

    def adverse_entry(raw: float, side: int) -> float:
        return raw * (1.0 + slip) if side == 1 else raw * (1.0 - slip)

    def adverse_exit(raw: float, side: int) -> float:
        return raw * (1.0 - slip) if side == 1 else raw * (1.0 + slip)

    for ts, row in merged.iterrows():
        equity_curve.append({"time": ts, "equity": equity})
        bar_t = _bar_time(ts)

        if position in (1, -1):
            is_long = position == 1
            hit_sl = bool(row["low"] <= sl) if is_long else bool(row["high"] >= sl)
            hit_tp = bool(row["high"] >= tp) if is_long else bool(row["low"] <= tp)
            raw_open = float(row["open"]) if pd.notna(row.get("open")) else None
            gap_sl = (raw_open is not None and raw_open <= sl) if is_long else (raw_open is not None and raw_open >= sl)
            gap_tp = (raw_open is not None and raw_open >= tp) if is_long else (raw_open is not None and raw_open <= tp)
            hit_eod = bar_t >= eod_flat
            ambiguous = hit_sl and hit_tp

            reason = None
            if gap_sl:
                exit_raw, reason = raw_open, "stop_gap"
            elif gap_tp:
                exit_raw, reason = raw_open, "target_gap"
            elif ambiguous:
                if ambiguous_policy == "stop_first":
                    exit_raw, reason = sl, "stop_first_ambiguous"
                else:
                    exit_raw, reason = tp, "target_first_ambiguous"
            elif hit_sl:
                exit_raw, reason = sl, "stop"
            elif hit_tp:
                exit_raw, reason = tp, "target"
            elif hit_eod:
                exit_raw, reason = float(row["close"]), "eod_flat"

            if reason is not None:
                exit_p = adverse_exit(float(exit_raw), position)
                risk_frac = ((entry_price - sl) / entry_price) if is_long and entry_price else ((sl - entry_price) / entry_price if entry_price else 0.0)
                gross_pnl = ((exit_p - entry_price) / entry_price) if is_long else ((entry_price - exit_p) / entry_price)
                pnl = gross_pnl - cost_bps / 10000.0
                if risk_frac > 0:
                    equity *= 1 + pnl * (risk_pct / risk_frac)
                trades.append(
                    {
                        "entry_time": entry_time,
                        "exit_time": ts,
                        "side": "long" if is_long else "short",
                        "entry": entry_price,
                        "entry_raw": entry_raw,
                        "exit": exit_p,
                        "exit_raw": float(exit_raw),
                        "sl": sl,
                        "tp": tp,
                        "pnl_pct": pnl * 100,
                        "width_pct": float(row["width_pct"]) if pd.notna(row["width_pct"]) else np.nan,
                        "exit_reason": reason,
                        "ambiguous_bar": bool(ambiguous),
                        "gap_exit": reason.endswith("_gap"),
                        "slippage_bps": float(slippage_bps),
                        "cost_bps": float(cost_bps),
                    }
                )
                position = 0

        if position == 0:
            if bool(row.get("long_entry")):
                entry_raw = float(row["close"])
                entry_price = adverse_entry(entry_raw, 1)
                risk = entry_price - float(row["BC"])
                if risk > 0:
                    position = 1
                    entry_time = ts
                    sl = float(row["BC"])
                    tp = entry_price + rr_target * risk
            elif bool(row.get("short_entry")):
                entry_raw = float(row["close"])
                entry_price = adverse_entry(entry_raw, -1)
                risk = float(row["TC"]) - entry_price
                if risk > 0:
                    position = -1
                    entry_time = ts
                    sl = float(row["TC"])
                    tp = entry_price - rr_target * risk

    return pd.DataFrame(trades), pd.DataFrame(equity_curve), equity


def _summarize_trades(tdf: pd.DataFrame, equity: float, capital: float, symbol: str) -> Dict:
    if tdf is None or tdf.empty:
        return {"symbol": symbol, "trades": 0, "message": "No trades generated"}

    wins = tdf[tdf["pnl_pct"] > 0]
    losses = tdf[tdf["pnl_pct"] <= 0]
    win_rate = len(wins) / len(tdf) * 100
    avg_win = wins["pnl_pct"].mean() if len(wins) else 0.0
    avg_loss = losses["pnl_pct"].mean() if len(losses) else 0.0
    loss_sum = losses["pnl_pct"].sum() if len(losses) else 0.0
    if len(losses) and loss_sum != 0:
        profit_factor = abs(wins["pnl_pct"].sum() / loss_sum)
    else:
        profit_factor = np.inf
    total_return = (equity / capital - 1) * 100
    avg_width = tdf["width_pct"].mean()

    return {
        "symbol": symbol,
        "total_trades": len(tdf),
        "win_rate_pct": round(float(win_rate), 2),
        "profit_factor": round(float(profit_factor), 2) if np.isfinite(profit_factor) else "inf",
        "avg_win_pct": round(float(avg_win), 2),
        "avg_loss_pct": round(float(avg_loss), 2),
        "total_return_pct": round(float(total_return), 2),
        "final_equity": round(float(equity), 2),
        "avg_cpr_width_pct": round(float(avg_width), 3) if pd.notna(avg_width) else None,
        "trades_df": tdf,
    }


def build_signal_frame(
    daily: pd.DataFrame,
    intraday: pd.DataFrame,
    narrow_quantile: float = 0.25,
    min_width_pct: Optional[float] = None,
    confirm_bars: int = 1,
    session_timezone: str = SESSION_TZ,
) -> pd.DataFrame:
    if daily is None or daily.empty or intraday is None or intraday.empty:
        return pd.DataFrame()
    daily_cpr = tag_narrow(add_cpr_columns(daily), narrow_quantile, min_width_pct)
    merged = merge_cpr_onto_intraday(intraday, daily_cpr, session_timezone)
    if merged.empty:
        return merged
    return add_breakout_signals(merged, confirm_bars)


def _cap_lookback(interval: str, lookback_days: int) -> int:
    cap = INTRADAY_MAX_DAYS.get(interval, 59)
    return max(1, min(int(lookback_days), cap))


def download_ohlcv(
    symbols: List[str],
    interval: str,
    lookback_days: int,
    session_timezone: str = SESSION_TZ,
    chunk_size: int = 40,
) -> pd.DataFrame:
    import yfinance as yf

    symbols = [s.strip() for s in symbols if s and s.strip()]
    if not symbols:
        return pd.DataFrame()
    zone = _session_zone(session_timezone)
    end_day = datetime.now(zone).date() + timedelta(days=1)
    start_day = datetime.now(zone).date() - timedelta(days=lookback_days)
    return _yahoo_download_chunked(
        yf,
        symbols,
        start=start_day.isoformat(),
        end=end_day.isoformat(),
        interval=interval,
        chunk_size=chunk_size,
    )


def extract_symbol_frame(raw: pd.DataFrame, symbol: str, session_timezone: str = SESSION_TZ) -> pd.DataFrame:
    frame = _extract_symbol_ohlcv(raw, symbol)
    return to_session_index(frame, session_timezone)


@dataclass
class ScreenRow:
    symbol: str
    segment: str
    signal: str
    narrow: bool
    width_pct: Optional[float]
    last: Optional[float]
    pivot: Optional[float]
    tc: Optional[float]
    bc: Optional[float]
    entry: Optional[float] = None
    sl: Optional[float] = None
    tp: Optional[float] = None
    signal_time: Optional[str] = None
    bars_beyond: int = 0
    dist_pct: Optional[float] = None
    data_status: str = "OK"

    def to_dict(self) -> Dict:
        return {
            "Symbol": self.symbol,
            "Segment": self.segment,
            "Signal": self.signal,
            "Narrow": "Yes" if self.narrow else "No",
            "Width %": self.width_pct,
            "Last": self.last,
            "Pivot": self.pivot,
            "TC": self.tc,
            "BC": self.bc,
            "Entry": self.entry,
            "SL": self.sl,
            "TP": self.tp,
            "Signal Time": self.signal_time,
            "Bars beyond": self.bars_beyond,
            "Dist %": self.dist_pct,
            "Data Status": self.data_status,
        }


def _latest_screen_row(
    symbol: str,
    merged: pd.DataFrame,
    rr_target: float,
    include_watch: bool,
) -> Optional[ScreenRow]:
    if merged is None or merged.empty:
        return None
    today = session_dates(merged.index).iloc[-1]
    day = merged[session_dates(merged.index) == today]
    if day.empty:
        day = merged
    last = day.iloc[-1]
    narrow = bool(last.get("narrow")) if pd.notna(last.get("narrow")) else False
    last_px = float(last["close"])
    tc = float(last["TC"])
    bc = float(last["BC"])
    pivot = float(last["P"])
    width_pct = float(last["width_pct"]) if pd.notna(last.get("width_pct")) else None

    long_hits = day[day["long_entry"] == True]  # noqa: E712
    short_hits = day[day["short_entry"] == True]  # noqa: E712
    signal = BreakoutSignal.WATCH.value if narrow else BreakoutSignal.NONE.value
    entry = sl = tp = None
    signal_time = None
    bars_beyond = 0
    dist_pct = None

    chosen = None
    side = None
    if not long_hits.empty and not short_hits.empty:
        chosen = long_hits.iloc[0] if long_hits.index[0] <= short_hits.index[0] else short_hits.iloc[0]
        side = BreakoutSignal.LONG.value if long_hits.index[0] <= short_hits.index[0] else BreakoutSignal.SHORT.value
    elif not long_hits.empty:
        chosen = long_hits.iloc[0]
        side = BreakoutSignal.LONG.value
    elif not short_hits.empty:
        chosen = short_hits.iloc[0]
        side = BreakoutSignal.SHORT.value

    if chosen is not None and side is not None:
        signal = side
        entry = float(chosen["close"])
        signal_time = pd.Timestamp(chosen.name).tz_convert(_session_zone()).strftime("%Y-%m-%d %H:%M")
        if side == "Long":
            risk = entry - float(chosen["BC"])
            sl = float(chosen["BC"])
            tp = entry + rr_target * risk if risk > 0 else None
            bars_beyond = int(day.loc[chosen.name :, "above_TC"].sum())
            dist_pct = ((last_px - tc) / tc) * 100 if tc else None
        else:
            risk = float(chosen["TC"]) - entry
            sl = float(chosen["TC"])
            tp = entry - rr_target * risk if risk > 0 else None
            bars_beyond = int(day.loc[chosen.name :, "below_BC"].sum())
            dist_pct = ((bc - last_px) / bc) * 100 if bc else None
    elif narrow:
        if last_px > tc:
            dist_pct = ((last_px - tc) / tc) * 100
        elif last_px < bc:
            dist_pct = ((bc - last_px) / bc) * 100
        else:
            dist_pct = ((last_px - pivot) / pivot) * 100 if pivot else None
    elif not include_watch:
        return None

    if signal == BreakoutSignal.NONE.value:
        return None
    if signal == BreakoutSignal.WATCH.value and not include_watch:
        return None

    return ScreenRow(
        symbol=symbol,
        segment=classify_symbol(symbol),
        signal=signal,
        narrow=narrow,
        width_pct=round(width_pct, 3) if width_pct is not None else None,
        last=round(last_px, 2),
        pivot=round(pivot, 2),
        tc=round(tc, 2),
        bc=round(bc, 2),
        entry=round(entry, 2) if entry is not None else None,
        sl=round(sl, 2) if sl is not None else None,
        tp=round(tp, 2) if tp is not None else None,
        signal_time=signal_time,
        bars_beyond=bars_beyond,
        dist_pct=round(dist_pct, 3) if dist_pct is not None else None,
    )


def screen_cpr_breakout(
    symbols: List[str],
    narrow_quantile: float = 0.25,
    min_width_pct: Optional[float] = None,
    confirm_bars: int = 1,
    rr_target: float = 2.0,
    interval: str = "15m",
    daily_lookback: int = 90,
    intraday_lookback: int = 5,
    include_watch: bool = True,
    session_timezone: str = SESSION_TZ,
) -> pd.DataFrame:
    """Scan a universe for today's narrow-CPR TC/BC breakout (or watch setups)."""
    symbols = [s.strip() for s in symbols if s and s.strip()]
    if not symbols:
        return pd.DataFrame()

    intra_days = _cap_lookback(interval, intraday_lookback)
    daily_raw = download_ohlcv(symbols, "1d", max(daily_lookback, 20), session_timezone, chunk_size=80)
    intra_raw = download_ohlcv(symbols, interval, intra_days, session_timezone, chunk_size=40)

    rows: List[Dict] = []
    for symbol in symbols:
        daily = extract_symbol_frame(daily_raw, symbol, session_timezone)
        intra = extract_symbol_frame(intra_raw, symbol, session_timezone)
        if daily.empty or intra.empty:
            rows.append(
                ScreenRow(
                    symbol=symbol,
                    segment=classify_symbol(symbol),
                    signal="None",
                    narrow=False,
                    width_pct=None,
                    last=None,
                    pivot=None,
                    tc=None,
                    bc=None,
                    data_status="Data unavailable",
                ).to_dict()
            )
            continue
        merged = build_signal_frame(
            daily,
            intra,
            narrow_quantile=narrow_quantile,
            min_width_pct=min_width_pct,
            confirm_bars=confirm_bars,
            session_timezone=session_timezone,
        )
        if merged.empty:
            continue
        row = _latest_screen_row(symbol, merged, rr_target, include_watch=True)
        if row is None:
            continue
        if not include_watch and row.signal not in (
            BreakoutSignal.LONG.value,
            BreakoutSignal.SHORT.value,
        ):
            continue
        rows.append(row.to_dict())

    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["_rank"] = df["Signal"].map(breakout_signal_rank).fillna(9)
    df = df.sort_values(["_rank", "Width %"], ascending=[True, True]).drop(columns=["_rank"])
    return df.reset_index(drop=True)


def backtest_cpr_breakout(
    symbol: str = "RELIANCE.NS",
    start: Optional[str] = None,
    end: Optional[str] = None,
    narrow_quantile: float = 0.25,
    min_width_pct: Optional[float] = None,
    confirm_bars: int = 1,
    rr_target: float = 2.0,
    risk_pct: float = 0.01,
    capital: float = 100000.0,
    cost_bps: float = 5.0,
    slippage_bps: float = 0.0,
    ambiguous_policy: str = "stop_first",
    interval: str = "15m",
    session_timezone: str = SESSION_TZ,
) -> Dict:
    """
    Backtest one symbol. Yahoo caps 15m history at about 60 days; longer
    windows silently shrink to that limit.
    """
    zone = _session_zone(session_timezone)
    today = datetime.now(zone).date()
    max_days = INTRADAY_MAX_DAYS.get(interval, 59)
    if end:
        end_day = min(pd.Timestamp(end).date(), today + timedelta(days=1))
    else:
        end_day = today + timedelta(days=1)
    if start:
        start_day = pd.Timestamp(start).date()
    else:
        start_day = end_day - timedelta(days=max_days)
    if (end_day - start_day).days > max_days:
        start_day = end_day - timedelta(days=max_days)

    import yfinance as yf

    daily_raw = _yahoo_download_chunked(
        yf,
        [symbol],
        start=(start_day - timedelta(days=40)).isoformat(),
        end=end_day.isoformat(),
        interval="1d",
        chunk_size=1,
    )
    intra_raw = _yahoo_download_chunked(
        yf,
        [symbol],
        start=start_day.isoformat(),
        end=end_day.isoformat(),
        interval=interval,
        chunk_size=1,
    )
    daily = extract_symbol_frame(daily_raw, symbol, session_timezone)
    intra = extract_symbol_frame(intra_raw, symbol, session_timezone)
    if daily.empty:
        return {"symbol": symbol, "trades": 0, "message": f"No daily data for {symbol}"}
    if intra.empty:
        return {
            "symbol": symbol,
            "trades": 0,
            "message": f"No {interval} data for {symbol} (Yahoo often limits this interval to ~{max_days} days)",
        }

    merged = build_signal_frame(
        daily,
        intra,
        narrow_quantile=narrow_quantile,
        min_width_pct=min_width_pct,
        confirm_bars=confirm_bars,
        session_timezone=session_timezone,
    )
    if merged.empty:
        return {"symbol": symbol, "trades": 0, "message": "No trades generated"}

    tdf, _, equity = simulate_trades(
        merged,
        rr_target=rr_target,
        risk_pct=risk_pct,
        capital=capital,
        cost_bps=cost_bps,
        slippage_bps=slippage_bps,
        ambiguous_policy=ambiguous_policy,
    )
    result = _summarize_trades(tdf, equity, capital, symbol)
    result["cost_bps"] = float(cost_bps)
    result["slippage_bps"] = float(slippage_bps)
    result["ambiguous_policy"] = ambiguous_policy
    result["execution_policy"] = "Gap fills at open; same-bar collisions use the selected policy"
    result["interval"] = interval
    result["start"] = start_day.isoformat()
    result["end"] = end_day.isoformat()
    return result
