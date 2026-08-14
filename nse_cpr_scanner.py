#!/usr/bin/env python3
"""
NSE EOD CPR Scanner

Separate from the Shah CPR console (`cpr_engine.py` / `app.py`) and the
intraday breakout screener (`cpr_breakout_engine.py` / `breakout_app.py`).

- Downloads NSE bhavcopy CSVs (cash + F&O)
- Caches ~252 prior cash sessions (configurable via --lookback): ~60 for daily
  own-history rank, the rest gives weekly / monthly CPR real depth
- Computes CPR, Width %, classification, and Bullish/Bearish flags
- Tags F&O vs Cash-only symbols
- Exports ranked tables and shortlists

This uses the completed session's H/L/C (EOD bhavcopy). Those levels are
the CPR that applies to the *next* session.

Usage:
    python nse_cpr_scanner.py 20260813
"""

from __future__ import annotations

import io
import sys
import time
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests

OUTPUT_DIR = Path("cpr_output")
IST = ZoneInfo("Asia/Kolkata")

CASH_URL = "https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_{date}_F_0000.csv.zip"
FO_URL = "https://nsearchives.nseindia.com/content/fo/BhavCopy_NSE_FO_0_0_0_{date}_F_0000.csv.zip"

NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/all-reports",
}

# UDI bhavcopy (Jul 2024+) → legacy names used by the rest of this scanner.
COLUMN_ALIASES = {
    "TckrSymb": "SYMBOL",
    "SctySrs": "SERIES",
    "OpnPric": "OPEN",
    "HghPric": "HIGH",
    "LwPric": "LOW",
    "ClsPric": "CLOSE",
    "LastPric": "LAST",
    "PrvsClsgPric": "PREVCLOSE",
    "TtlTradgVol": "VOLUME",
    "TtlTrfVal": "VALUE",
    "FinInstrmNm": "NAME",
    "ISIN": "ISIN",
}

CASH_SERIES = ("EQ",)
UNCLASSIFIED_INDUSTRY = "Unclassified"
INDUSTRY_URL = "https://nsearchives.nseindia.com/content/indices/ind_nifty500list.csv"
INDUSTRY_CACHE = Path(__file__).resolve().parent / "universes" / "nifty500_industry.csv"
HISTORY_LOOKBACK = 60
HISTORY_LOOKBACK_HTF = 252
OWN_NARROW_QUANTILE = 0.25
MIN_HISTORY_DAYS = 10
MIN_HISTORY_WEEKS = 8
MIN_HISTORY_MONTHS = 4
MIN_VALUE_TOP20 = 20_000_000
BHAVCOPY_SLIM_COLS = ["SYMBOL", "SERIES", "NAME", "OPEN", "HIGH", "LOW", "CLOSE", "VOLUME", "VALUE"]

# ETFs, AMC schemes, index funds, gilt/liquid products listed as EQ.
NON_EQUITY_NAME = (
    r"AMC|\bETF\b|BEES|IETF|MUTUAL\s*FUND|INDEX FUND|\bFOF\b|"
    r"LIQUID FUND|LIQUID ETF|GOLD ETF|SILVER ETF"
)
NON_EQUITY_SYMBOL = r"ETF|BEES|IETF|LIQUID|GILT|GSEC|INVIT"


@dataclass
class ScanResult:
    date: str
    cash_rows: int
    fo_available: bool
    full: pd.DataFrame
    narrow: pd.DataFrame
    bullish: pd.DataFrame
    bearish: pd.DataFrame
    top20: pd.DataFrame
    output_dir: Path = field(default_factory=lambda: OUTPUT_DIR)
    weekly: pd.DataFrame = field(default_factory=pd.DataFrame)
    monthly: pd.DataFrame = field(default_factory=pd.DataFrame)
    weekly_applies: str = ""
    monthly_applies: str = ""


def _nse_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(NSE_HEADERS)
    try:
        session.get("https://www.nseindia.com", timeout=20)
    except requests.RequestException:
        pass
    return session


def download_bhavcopy(url: str, date: str, session: Optional[requests.Session] = None) -> Optional[pd.DataFrame]:
    """Download and unzip an NSE bhavcopy CSV."""
    formatted_url = url.format(date=date)
    print(f"Downloading: {formatted_url}")
    own_session = session is None
    session = session or _nse_session()
    try:
        response = session.get(formatted_url, timeout=45)
        response.raise_for_status()
        if formatted_url.endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                csv_filename = next(
                    (name for name in z.namelist() if name.lower().endswith(".csv")),
                    z.namelist()[0],
                )
                with z.open(csv_filename) as f:
                    df = pd.read_csv(f)
        else:
            df = pd.read_csv(io.BytesIO(response.content))
        return df
    except Exception as exc:
        print(f"Error downloading {formatted_url}: {exc}")
        return None
    finally:
        if own_session:
            session.close()


def normalize_bhavcopy(df: pd.DataFrame, cash_only: bool = False) -> pd.DataFrame:
    """Map UDI or legacy columns onto SYMBOL / OPEN / HIGH / LOW / CLOSE."""
    out = df.copy()
    out.columns = [str(c).strip() for c in out.columns]
    rename = {src: dst for src, dst in COLUMN_ALIASES.items() if src in out.columns and dst not in out.columns}
    if rename:
        out = out.rename(columns=rename)

    required = ["SYMBOL", "OPEN", "HIGH", "LOW", "CLOSE"]
    missing = [col for col in required if col not in out.columns]
    if missing:
        raise ValueError(f"Bhavcopy missing columns {missing}. Got: {list(out.columns)}")

    out["SYMBOL"] = out["SYMBOL"].astype(str).str.strip().str.upper()
    for col in ["OPEN", "HIGH", "LOW", "CLOSE", "VOLUME", "VALUE"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")

    if "SERIES" in out.columns:
        out["SERIES"] = out["SERIES"].astype(str).str.strip().str.upper()
        if cash_only:
            out = out[out["SERIES"].isin(CASH_SERIES)]

    out = out.dropna(subset=["SYMBOL", "HIGH", "LOW", "CLOSE"])
    out = out[out["CLOSE"] > 0]
    out = out.drop_duplicates(subset=["SYMBOL"], keep="first")
    return out.reset_index(drop=True)


def non_equity_mask(df: pd.DataFrame) -> pd.Series:
    """True for ETFs, AMC products, liquid/gilt funds, not operating companies."""
    symbol = df["SYMBOL"].astype(str)
    mask = symbol.str.contains(NON_EQUITY_SYMBOL, case=False, regex=True, na=False)
    if "NAME" in df.columns:
        name = df["NAME"].astype(str)
        mask = mask | name.str.contains(NON_EQUITY_NAME, case=False, regex=True, na=False)
    return mask


def keep_listed_equity(df: pd.DataFrame, quiet: bool = False) -> pd.DataFrame:
    """EQ operating companies only — drop ETFs, AMCs, mutual funds, gilt/liquid products."""
    if df.empty:
        return df
    dropped = non_equity_mask(df)
    kept = df.loc[~dropped].copy()
    if not quiet:
        print(f"Equity filter: {int(dropped.sum())} ETF/AMC/fund rows dropped → {len(kept)} stocks")
    return kept.reset_index(drop=True)


def load_industry_map(session: Optional[requests.Session] = None, fetch: bool = True) -> dict:
    """Symbol → NSE Indices industry (Nifty 500 list). Cache under universes/."""
    if INDUSTRY_CACHE.exists():
        cached = pd.read_csv(INDUSTRY_CACHE)
        if "Symbol" in cached.columns and "Industry" in cached.columns:
            mapping = {
                str(sym).strip().upper(): str(ind).strip()
                for sym, ind in zip(cached["Symbol"], cached["Industry"])
                if pd.notna(sym) and pd.notna(ind)
            }
            if mapping:
                return mapping
    if not fetch:
        return {}
    own = session is None
    session = session or _nse_session()
    try:
        response = session.get(INDUSTRY_URL, timeout=30)
        response.raise_for_status()
        table = pd.read_csv(io.BytesIO(response.content))
        table.columns = [str(c).strip() for c in table.columns]
        if "Symbol" not in table.columns or "Industry" not in table.columns:
            print(f"Industry file missing columns: {list(table.columns)}")
            return {}
        INDUSTRY_CACHE.parent.mkdir(exist_ok=True)
        table.to_csv(INDUSTRY_CACHE, index=False)
        print(f"Industry map: {len(table)} Nifty 500 names → {INDUSTRY_CACHE}")
        return {
            str(sym).strip().upper(): str(ind).strip()
            for sym, ind in zip(table["Symbol"], table["Industry"])
            if pd.notna(sym) and pd.notna(ind)
        }
    except Exception as exc:
        print(f"Industry map unavailable: {exc}")
        return {}
    finally:
        if own:
            session.close()


def attach_industry(df: pd.DataFrame, mapping: Optional[dict] = None, fetch: bool = True) -> pd.DataFrame:
    """Join Nifty 500 industry. Names outside that list are Unclassified."""
    out = df.copy()
    mapping = mapping if mapping is not None else load_industry_map(fetch=fetch)
    out["Industry"] = out["SYMBOL"].map(mapping).fillna(UNCLASSIFIED_INDUSTRY)
    return out


def cpr_overlay(today_top, today_bot, prior_top, prior_bot) -> str:
    """Shah overlay: today's CPR vs the previous session's CPR."""
    if pd.isna(prior_top) or pd.isna(prior_bot) or pd.isna(today_top) or pd.isna(today_bot):
        return "Unknown"
    if today_bot > prior_top:
        return "Higher"
    if today_top < prior_bot:
        return "Lower"
    if today_top <= prior_top and today_bot >= prior_bot:
        return "Inside"
    if today_top >= prior_top and today_bot <= prior_bot:
        return "Outside"
    return "Overlapping"


def bhavcopy_cache_dir(output_dir: Optional[Path] = None) -> Path:
    root = Path(output_dir) if output_dir is not None else OUTPUT_DIR
    return root / "bhavcopy"


def session_date_window(end_date: str, sessions: int = HISTORY_LOOKBACK_HTF, calendar_pad: int = 130) -> List[str]:
    """Newest-first weekday dates, padded so holidays can be skipped.

    `calendar_pad` covers weekends + market holidays so the window yields at least
    `sessions` trading dates (~250 sessions ≈ 12 months)."""
    end = datetime.strptime(end_date, "%Y%m%d").date()
    dates: List[str] = []
    cur = end
    for _ in range(sessions + calendar_pad):
        if cur.weekday() < 5:
            dates.append(cur.strftime("%Y%m%d"))
        cur -= timedelta(days=1)
    return dates


def _slim_bhavcopy(df: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in BHAVCOPY_SLIM_COLS if c in df.columns]
    return df.loc[:, cols].copy()


def ensure_bhavcopy_history(
    end_date: str,
    lookback: int = HISTORY_LOOKBACK_HTF,
    output_dir: Optional[Path] = None,
    session: Optional[requests.Session] = None,
) -> List[str]:
    """Download and cache up to `lookback` cash EQ bhavcopies ending at end_date."""
    cache = bhavcopy_cache_dir(output_dir)
    cache.mkdir(parents=True, exist_ok=True)
    own = session is None
    session = session or _nse_session()
    got: List[str] = []
    try:
        for date in session_date_window(end_date, lookback):
            if len(got) >= lookback:
                break
            path = cache / f"cm_{date}.csv"
            if path.exists() and path.stat().st_size > 0:
                got.append(date)
                continue
            raw = download_bhavcopy(CASH_URL, date, session=session)
            if raw is None:
                print(f"  no cash bhavcopy for {date}")
                time.sleep(0.15)
                continue
            try:
                df = keep_listed_equity(normalize_bhavcopy(raw, cash_only=True), quiet=True)
            except Exception as exc:
                print(f"  skip {date}: {exc}")
                continue
            _slim_bhavcopy(df).to_csv(path, index=False)
            print(f"  cached {date}: {len(df)} stocks → {path.name}")
            got.append(date)
            time.sleep(0.15)
    finally:
        if own:
            session.close()
    print(f"Bhavcopy history: {len(got)} sessions ending {end_date}")
    return got


def seed_bhavcopy_cache(df: pd.DataFrame, date: str, output_dir: Optional[Path] = None) -> Path:
    """Write today's slim cash bhavcopy so history does not re-download it."""
    cache = bhavcopy_cache_dir(output_dir)
    cache.mkdir(parents=True, exist_ok=True)
    path = cache / f"cm_{date}.csv"
    _slim_bhavcopy(df).to_csv(path, index=False)
    return path


def cached_history_dates(end_date: str, output_dir: Optional[Path] = None, lookback: int = HISTORY_LOOKBACK_HTF) -> List[str]:
    cache = bhavcopy_cache_dir(output_dir)
    got: List[str] = []
    for date in session_date_window(end_date, lookback):
        path = cache / f"cm_{date}.csv"
        if path.exists() and path.stat().st_size > 0:
            got.append(date)
        if len(got) >= lookback:
            break
    return got


def load_history_panel(dates: List[str], output_dir: Optional[Path] = None) -> pd.DataFrame:
    cache = bhavcopy_cache_dir(output_dir)
    frames = []
    for date in dates:
        path = cache / f"cm_{date}.csv"
        if not path.exists():
            continue
        df = pd.read_csv(path)
        if df.empty:
            continue
        df["session"] = date
        frames.append(compute_cpr(df))
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def scan_from_cached_bhavcopy(
    date: str,
    output_dir: Optional[Path] = None,
    lookback: int = HISTORY_LOOKBACK_HTF,
    write_csv: bool = True,
) -> ScanResult:
    """Build a session scan from a cached cash bhavcopy (no NSE download)."""
    path = bhavcopy_cache_dir(output_dir) / f"cm_{date}.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing cached bhavcopy {path}")
    cash_df = pd.read_csv(path)
    cash_df = keep_listed_equity(cash_df, quiet=True)
    if cash_df.empty:
        raise RuntimeError(f"Cached bhavcopy {date} has no listed equity rows")
    cash_df = attach_industry(cash_df, fetch=False)
    if "Segment" not in cash_df.columns:
        cash_df["Segment"] = "Cash Only"
    cash_df = compute_cpr(cash_df)
    cash_df = apply_bullish_cpr_filters(cash_df)
    hist_dates = cached_history_dates(date, output_dir, lookback)
    if hist_dates:
        cash_df = attach_history_features(
            cash_df, load_history_panel(hist_dates, output_dir), own_window=HISTORY_LOOKBACK
        )
    if write_csv:
        return export_results(cash_df, date, output_dir=output_dir, verbose=False)
    full_table, narrow, bullish, bearish, top20 = split_shortlists(cash_df)
    return ScanResult(
        date=date,
        cash_rows=len(cash_df),
        fo_available=False,
        full=full_table,
        narrow=narrow,
        bullish=bullish,
        bearish=bearish,
        top20=top20,
        output_dir=Path(output_dir) if output_dir is not None else OUTPUT_DIR,
    )


def backfill_cached_scans(
    end_date: str,
    output_dir: Optional[Path] = None,
    lookback: int = HISTORY_LOOKBACK_HTF,
    skip_existing: bool = True,
) -> List[str]:
    """Write cpr_full_*.csv for each cached cash session so the site archive has those dates."""
    output_dir = Path(output_dir) if output_dir is not None else OUTPUT_DIR
    dates = cached_history_dates(end_date, output_dir, lookback)
    if not dates:
        print("Archive: no cached bhavcopies")
        return []
    print(f"Archive: loading {len(dates)} cached sessions…")
    panel = load_history_panel(dates, output_dir)
    industry = load_industry_map(fetch=False)
    written: List[str] = []
    for date in dates:
        full_path = output_dir / f"cpr_full_{date}.csv"
        if full_path.exists():
            header = set(pd.read_csv(full_path, nrows=0).columns)
            if skip_existing and "Setup" in header and "Overlay" in header:
                continue
            print(f"  enrich {date} with overlay / own-narrow")
            result = load_scan_result(date, output_dir)
            export_results(result.full, date, output_dir=output_dir, verbose=False)
            written.append(date)
            continue
        day = panel[panel["session"] == date].copy()
        if day.empty:
            continue
        print(f"  archive scan {date}")
        if "Segment" not in day.columns:
            day["Segment"] = "Cash Only"
        day = attach_industry(day, mapping=industry, fetch=False)
        day = apply_bullish_cpr_filters(day)
        hist = panel.loc[panel["session"] <= date]
        day = attach_history_features(day, hist, own_window=HISTORY_LOOKBACK)
        export_results(day, date, output_dir=output_dir, verbose=False)
        written.append(date)
    print(f"Archive: {len(dates)} cached sessions, {len(written)} scans written")
    return dates


def attach_history_features(
    scan_df: pd.DataFrame,
    history_df: pd.DataFrame,
    own_narrow_q: float = OWN_NARROW_QUANTILE,
    min_history: int = MIN_HISTORY_DAYS,
    own_window: Optional[int] = None,
) -> pd.DataFrame:
    """Width percentile vs own history, prior-session overlay, median turnover, Setup.

    `own_window` limits the width percentile / History_Days / turnover to the most
    recent N sessions per symbol. Daily scans pass HISTORY_LOOKBACK (60) even when
    the cache holds ~252 sessions; weekly / monthly HTF bars leave it None so the
    rank and history counts use every completed bar in the cache.
    """
    out = scan_df.copy()
    if history_df is None or history_df.empty or "SYMBOL" not in history_df.columns:
        out["Overlay"] = "Unknown"
        out["Width_Rank_Pct"] = np.nan
        out["Own_Narrow"] = False
        out["History_Days"] = 0
        out["Value_60d"] = np.nan
        out["Setup"] = "No setup"
        return out

    hist = history_df.copy()
    hist["SYMBOL"] = hist["SYMBOL"].astype(str).str.strip().str.upper()
    hist = hist.sort_values(["SYMBOL", "session"])
    if own_window:
        hist = hist.groupby("SYMBOL", sort=False).tail(own_window)
    hist["prior_top"] = hist.groupby("SYMBOL")["CPR_Top"].shift(1)
    hist["prior_bot"] = hist.groupby("SYMBOL")["CPR_Bottom"].shift(1)
    hist["Width_Rank_Pct"] = hist.groupby("SYMBOL")["CPR_Width_Pct"].rank(method="average", pct=True)
    hist["History_Days"] = hist.groupby("SYMBOL")["session"].transform("count")
    if "VALUE" in hist.columns:
        hist["VALUE"] = pd.to_numeric(hist["VALUE"], errors="coerce")
        hist["Value_60d"] = hist.groupby("SYMBOL")["VALUE"].transform("median")
    else:
        hist["Value_60d"] = np.nan

    latest = hist["session"].max()
    today = hist[hist["session"] == latest][
        ["SYMBOL", "prior_top", "prior_bot", "Width_Rank_Pct", "History_Days", "Value_60d"]
    ]
    out["SYMBOL"] = out["SYMBOL"].astype(str).str.strip().str.upper()
    out = out.drop(columns=["Overlay", "Width_Rank_Pct", "Own_Narrow", "History_Days", "Value_60d", "Setup"], errors="ignore")
    out = out.merge(today, on="SYMBOL", how="left")
    out["Overlay"] = [
        cpr_overlay(t, b, pt, pb)
        for t, b, pt, pb in zip(out["CPR_Top"], out["CPR_Bottom"], out["prior_top"], out["prior_bot"])
    ]
    out["Width_Rank_Pct"] = pd.to_numeric(out["Width_Rank_Pct"], errors="coerce")
    out["History_Days"] = pd.to_numeric(out["History_Days"], errors="coerce").fillna(0).astype(int)
    out["Own_Narrow"] = (
        (out["Width_Rank_Pct"] <= own_narrow_q)
        & (out["History_Days"] >= min_history)
        & (pd.to_numeric(out["CPR_Width_Pct"], errors="coerce") > 0)
    ).fillna(False).astype(bool)
    above = out["Price_Position"] == "Above CPR"
    below = out["Price_Position"] == "Below CPR"
    inside = out["Price_Position"] == "Inside CPR"
    out["Setup"] = np.where(
        out["Own_Narrow"] & above & (out["Overlay"] == "Higher"),
        "Long",
        np.where(
            out["Own_Narrow"] & below & (out["Overlay"] == "Lower"),
            "Short",
            np.where(out["Own_Narrow"] & inside, "Watch", "No setup"),
        ),
    )
    return out.drop(columns=["prior_top", "prior_bot"], errors="ignore")


def last_complete_period_end(scan_date: str, freq: str) -> str:
    """Last finished week (W-FRI) or month as of scan_date. Incomplete bars are excluded."""
    d = datetime.strptime(scan_date, "%Y%m%d").date()
    ts = pd.Timestamp(d)
    per = ts.to_period(freq)
    end = per.end_time.date()
    if freq.startswith("W"):
        if d >= end or d.weekday() == 4:
            return end.strftime("%Y%m%d")
        return (per - 1).end_time.date().strftime("%Y%m%d")
    last_weekday = end
    while last_weekday.weekday() >= 5:
        last_weekday -= timedelta(days=1)
    if d >= last_weekday:
        return end.strftime("%Y%m%d")
    return (per - 1).end_time.date().strftime("%Y%m%d")


def htf_applies_label(period_end: str, freq: str) -> str:
    """The calendar window the completed bar’s CPR is for (next week / next month)."""
    end = datetime.strptime(period_end, "%Y%m%d").date()
    if freq.startswith("W"):
        start = end + timedelta(days=3)
        while start.weekday() != 0:
            start += timedelta(days=1)
        finish = start + timedelta(days=4)
        return f"Week {start.strftime('%d %b')} – {finish.strftime('%d %b %Y')}"
    nxt = pd.Timestamp(end).to_period("M") + 1
    return nxt.strftime("%b %Y")


def aggregate_htf_bars(history_df: pd.DataFrame, freq: str) -> pd.DataFrame:
    """Roll daily OHLC into week or month bars. session = period end YYYYMMDD."""
    if history_df is None or history_df.empty:
        return pd.DataFrame()
    df = history_df.copy()
    df["SYMBOL"] = df["SYMBOL"].astype(str).str.strip().str.upper()
    df["dt"] = pd.to_datetime(df["session"].astype(str), format="%Y%m%d", errors="coerce")
    df = df.dropna(subset=["dt", "SYMBOL", "HIGH", "LOW", "CLOSE"])
    if df.empty:
        return pd.DataFrame()
    df["period_end"] = df["dt"].dt.to_period(freq).dt.end_time.dt.strftime("%Y%m%d")
    agg = {"OPEN": "first", "HIGH": "max", "LOW": "min", "CLOSE": "last"}
    if "VALUE" in df.columns:
        df["VALUE"] = pd.to_numeric(df["VALUE"], errors="coerce")
        agg["VALUE"] = "sum"
    for col in ("NAME", "Industry", "Segment"):
        if col in df.columns:
            agg[col] = "last"
    grouped = df.sort_values(["SYMBOL", "dt"]).groupby(["SYMBOL", "period_end"], sort=True)
    out = grouped.agg(agg).reset_index()
    out["session"] = out["period_end"]
    return compute_cpr(out)


def build_htf_frame(
    history_df: pd.DataFrame,
    scan_date: str,
    freq: str,
    min_history: int,
) -> tuple[pd.DataFrame, str]:
    """Completed HTF bars up to scan_date, with overlay / own-narrow / Setup."""
    bars = aggregate_htf_bars(history_df, freq)
    if bars.empty:
        return pd.DataFrame(), ""
    complete_end = last_complete_period_end(scan_date, freq)
    bars = bars[bars["session"] <= complete_end]
    if bars.empty:
        return pd.DataFrame(), ""
    bars = apply_bullish_cpr_filters(bars)
    bars = attach_history_features(bars, bars, min_history=min_history)
    latest = bars["session"].max()
    frame = bars[bars["session"] == latest].copy()
    label = htf_applies_label(str(latest), freq)
    frame["Applies"] = label
    frame["Timeframe"] = "Weekly" if freq.startswith("W") else "Monthly"
    return frame.reset_index(drop=True), label


def attach_htf_to_result(result: ScanResult, output_dir: Optional[Path] = None, write_csv: bool = True) -> ScanResult:
    """Add weekly / monthly CPR from cached daily bhavcopies."""
    output_dir = Path(output_dir) if output_dir is not None else result.output_dir
    hist_dates = cached_history_dates(result.date, output_dir)
    if len(hist_dates) < 5:
        return result
    panel = load_history_panel(hist_dates, output_dir)
    if panel.empty:
        return result
    weekly, w_label = build_htf_frame(panel, result.date, "W-FRI", MIN_HISTORY_WEEKS)
    monthly, m_label = build_htf_frame(panel, result.date, "M", MIN_HISTORY_MONTHS)
    result.weekly = weekly
    result.monthly = monthly
    result.weekly_applies = w_label
    result.monthly_applies = m_label
    if write_csv:
        output_dir.mkdir(exist_ok=True)
        if not weekly.empty:
            weekly.to_csv(output_dir / f"cpr_weekly_{result.date}.csv", index=False)
            print(f"✓ Weekly CPR ({w_label}): {len(weekly)} names")
        if not monthly.empty:
            monthly.to_csv(output_dir / f"cpr_monthly_{result.date}.csv", index=False)
            print(f"✓ Monthly CPR ({m_label}): {len(monthly)} names")
    w_setups = int(weekly["Setup"].isin(["Long", "Short", "Watch"]).sum()) if not weekly.empty and "Setup" in weekly.columns else 0
    m_setups = int(monthly["Setup"].isin(["Long", "Short", "Watch"]).sum()) if not monthly.empty and "Setup" in monthly.columns else 0
    print(f"HTF: weekly {w_label or 'n/a'} setups {w_setups} | monthly {m_label or 'n/a'} setups {m_setups}")
    return result


def compute_cpr(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute CPR columns for a bhavcopy DataFrame.
    Required columns: SYMBOL, OPEN, HIGH, LOW, CLOSE
    """
    out = df.copy()
    for col in ["OPEN", "HIGH", "LOW", "CLOSE"]:
        out[col] = pd.to_numeric(out[col], errors="coerce")

    out["Pivot"] = (out["HIGH"] + out["LOW"] + out["CLOSE"]) / 3
    out["BC"] = (out["HIGH"] + out["LOW"]) / 2
    out["TC"] = 2 * out["Pivot"] - out["BC"]

    out["CPR_Top"] = out[["BC", "TC"]].max(axis=1)
    out["CPR_Bottom"] = out[["BC", "TC"]].min(axis=1)

    out["CPR_Width"] = out["CPR_Top"] - out["CPR_Bottom"]
    out["CPR_Width_Pct"] = (out["CPR_Width"] / out["CLOSE"]) * 100

    out["CPR_Class"] = pd.cut(
        out["CPR_Width_Pct"],
        bins=[0, 0.25, 0.75, np.inf],
        labels=["Narrow", "Moderate", "Wide"],
        include_lowest=True,
    )

    out["Bias"] = np.where(
        out["Pivot"] > out["BC"],
        "Bullish",
        np.where(out["Pivot"] < out["BC"], "Bearish", "Neutral"),
    )

    out["Price_Position"] = np.where(
        out["CLOSE"] > out["CPR_Top"],
        "Above CPR",
        np.where(out["CLOSE"] < out["CPR_Bottom"], "Below CPR", "Inside CPR"),
    )
    return out


def tag_fo_symbols(cash_df: pd.DataFrame, fo_df: Optional[pd.DataFrame]) -> pd.DataFrame:
    """Tag symbols as F&O or Cash-only."""
    out = cash_df.copy()
    if fo_df is not None and not fo_df.empty and "SYMBOL" in fo_df.columns:
        fo_symbols = set(fo_df["SYMBOL"].astype(str).str.strip().str.upper().unique())
        out["Segment"] = np.where(out["SYMBOL"].isin(fo_symbols), "F&O + Cash", "Cash Only")
    else:
        out["Segment"] = "Cash Only"
    return out


def apply_bullish_cpr_filters(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply Bullish CPR conditions:
    - Close above CPR
    - Bullish bias (Pivot > BC)
    - Narrow CPR (for breakout potential)
    """
    out = df.copy()
    out["Bullish_CPR"] = (
        (out["CLOSE"] > out["CPR_Top"])
        & (out["Pivot"] > out["BC"])
        & (out["CPR_Width_Pct"] < 0.25)
    )
    out["Bearish_CPR"] = (out["CLOSE"] < out["CPR_Bottom"]) & (out["Pivot"] < out["BC"])
    return out


DISPLAY_COLS = [
    "SYMBOL",
    "NAME",
    "Industry",
    "SERIES",
    "CLOSE",
    "Pivot",
    "BC",
    "TC",
    "CPR_Bottom",
    "CPR_Top",
    "CPR_Width",
    "CPR_Width_Pct",
    "Width_Rank_Pct",
    "CPR_Class",
    "Own_Narrow",
    "Overlay",
    "Setup",
    "Bias",
    "Price_Position",
    "Segment",
    "History_Days",
    "Applies",
    "Bullish_CPR",
    "Bearish_CPR",
]

WEB_EXPORT_COLS = [
    "SYMBOL",
    "SERIES",
    "NAME",
    "Industry",
    "OPEN",
    "HIGH",
    "LOW",
    "CLOSE",
    "VOLUME",
    "VALUE",
    "Pivot",
    "BC",
    "TC",
    "CPR_Bottom",
    "CPR_Top",
    "CPR_Width",
    "CPR_Width_Pct",
    "Width_Rank_Pct",
    "CPR_Class",
    "Own_Narrow",
    "Overlay",
    "Setup",
    "Bias",
    "Price_Position",
    "Segment",
    "History_Days",
    "Value_60d",
    "Applies",
    "Timeframe",
    "Bullish_CPR",
    "Bearish_CPR",
]


def _present_cols(df: pd.DataFrame, cols: Optional[List[str]] = None) -> list:
    wanted = cols or DISPLAY_COLS
    return [c for c in wanted if c in df.columns]


def web_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Slim CPR columns for public download (not the raw bhavcopy dump)."""
    cols = _present_cols(df, WEB_EXPORT_COLS)
    return df.loc[:, cols].copy() if cols else df.copy()


def last_completed_session(now: Optional[datetime] = None) -> str:
    """Most recent weekday session. Before 16:15 IST, yesterday is still 'today'."""
    now = now or datetime.now(IST)
    if now.tzinfo is None:
        now = now.replace(tzinfo=IST)
    else:
        now = now.astimezone(IST)
    d = now.date()
    if now.hour < 16 or (now.hour == 16 and now.minute < 15):
        d -= timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.strftime("%Y%m%d")


def candidate_session_dates(now: Optional[datetime] = None, max_back: int = 7) -> List[str]:
    """Weekday dates to try when the latest session is a holiday."""
    dates: List[str] = []
    first = datetime.strptime(last_completed_session(now), "%Y%m%d").date()
    cur = first
    while len(dates) < max_back:
        if cur.weekday() < 5:
            dates.append(cur.strftime("%Y%m%d"))
        cur -= timedelta(days=1)
    return dates


def discover_scan_dates(output_dir: Optional[Path] = None) -> List[str]:
    output_dir = Path(output_dir) if output_dir is not None else OUTPUT_DIR
    dates = sorted(
        {p.stem.split("_")[-1] for p in output_dir.glob("cpr_full_*.csv") if p.stem.split("_")[-1].isdigit()},
        reverse=True,
    )
    return dates


def load_scan_result(date: str, output_dir: Optional[Path] = None) -> ScanResult:
    """Rebuild a ScanResult from previously exported CSVs."""
    output_dir = Path(output_dir) if output_dir is not None else OUTPUT_DIR
    full_path = output_dir / f"cpr_full_{date}.csv"
    if not full_path.exists():
        raise FileNotFoundError(f"Missing {full_path}")
    full = pd.read_csv(full_path)
    for col in ("Bullish_CPR", "Bearish_CPR", "Own_Narrow"):
        if col in full.columns:
            full[col] = full[col].astype(str).str.lower().isin(["true", "1", "yes"])
    if "Bullish_CPR" not in full.columns:
        full = apply_bullish_cpr_filters(full)
    full = keep_listed_equity(full, quiet=True)
    full = attach_industry(full)
    if "Setup" in full.columns:
        full["Setup"] = full["Setup"].fillna("No setup").replace({"None": "No setup", "nan": "No setup"})
    else:
        hist_dates = cached_history_dates(date, output_dir)
        if date in hist_dates:
            full = attach_history_features(
                full, load_history_panel(hist_dates, output_dir), own_window=HISTORY_LOOKBACK
            )
    _, narrow, bullish, bearish, top20 = split_shortlists(full)
    fo_available = "Segment" in full.columns and bool((full["Segment"] == "F&O + Cash").any())
    result = ScanResult(
        date=date,
        cash_rows=len(full),
        fo_available=fo_available,
        full=full,
        narrow=narrow,
        bullish=bullish,
        bearish=bearish,
        top20=top20,
        output_dir=output_dir,
    )
    weekly_path = output_dir / f"cpr_weekly_{date}.csv"
    monthly_path = output_dir / f"cpr_monthly_{date}.csv"
    if weekly_path.exists():
        result.weekly = pd.read_csv(weekly_path)
        if "Applies" in result.weekly.columns and not result.weekly.empty:
            result.weekly_applies = str(result.weekly["Applies"].iloc[0])
    if monthly_path.exists():
        result.monthly = pd.read_csv(monthly_path)
        if "Applies" in result.monthly.columns and not result.monthly.empty:
            result.monthly_applies = str(result.monthly["Applies"].iloc[0])
    return result


def _liquid_enough(df: pd.DataFrame) -> pd.Series:
    if "VALUE" in df.columns:
        value = pd.to_numeric(df["VALUE"], errors="coerce")
        if value.notna().any():
            return value >= MIN_VALUE_TOP20
    if "Value_60d" in df.columns:
        return pd.to_numeric(df["Value_60d"], errors="coerce") >= MIN_VALUE_TOP20
    return pd.Series(True, index=df.index)


def split_shortlists(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    full_table = df.sort_values("CPR_Width_Pct").reset_index(drop=True)
    narrow = df[df["CPR_Class"] == "Narrow"].sort_values("CPR_Width_Pct").reset_index(drop=True)
    bullish = df[df["Bullish_CPR"]].sort_values("CPR_Width_Pct").reset_index(drop=True)
    bearish = df[df["Bearish_CPR"]].sort_values("CPR_Width_Pct", ascending=False).reset_index(drop=True)
    top_cols = [
        c
        for c in [
            "SYMBOL",
            "Industry",
            "CLOSE",
            "Pivot",
            "BC",
            "TC",
            "CPR_Width_Pct",
            "Width_Rank_Pct",
            "Overlay",
            "Setup",
            "Own_Narrow",
            "Bias",
            "Price_Position",
            "Segment",
        ]
        if c in df.columns
    ]
    ranked = pd.DataFrame(columns=df.columns)
    if "Setup" in df.columns:
        ranked = df[df["Setup"].isin(["Long", "Short", "Watch"])]
        if not ranked.empty:
            liquid_mask = _liquid_enough(ranked).reindex(ranked.index).fillna(False)
            liquid = ranked.loc[liquid_mask]
            if not liquid.empty:
                ranked = liquid
    if ranked.empty and "Own_Narrow" in df.columns:
        ranked = df[df["Own_Narrow"].astype(bool)]
    if ranked.empty:
        ranked = narrow[narrow["CPR_Width_Pct"] > 0] if "CPR_Width_Pct" in narrow.columns else narrow
    sort_col = "Width_Rank_Pct" if "Width_Rank_Pct" in ranked.columns else "CPR_Width_Pct"
    if not ranked.empty and sort_col in ranked.columns:
        ranked = ranked.sort_values(sort_col, na_position="last")
    top20 = ranked.head(20)[top_cols].reset_index(drop=True) if not ranked.empty else pd.DataFrame(columns=top_cols)
    return full_table, narrow, bullish, bearish, top20


def export_results(
    df: pd.DataFrame,
    date: str,
    output_dir: Optional[Path] = None,
    verbose: bool = True,
) -> ScanResult:
    """Export ranked tables and shortlists."""
    output_dir = Path(output_dir) if output_dir is not None else OUTPUT_DIR
    output_dir.mkdir(exist_ok=True)
    full_table, narrow, bullish, bearish, top20 = split_shortlists(df)

    full_table.to_csv(output_dir / f"cpr_full_{date}.csv", index=False)
    narrow.to_csv(output_dir / f"cpr_narrow_{date}.csv", index=False)
    bullish.to_csv(output_dir / f"cpr_bullish_{date}.csv", index=False)
    bearish.to_csv(output_dir / f"cpr_bearish_{date}.csv", index=False)
    top20.to_csv(output_dir / f"cpr_top20_narrow_{date}.csv", index=False)
    if verbose:
        print(f"✓ Full table: {output_dir / f'cpr_full_{date}.csv'}")
        print(f"✓ Narrow CPR: {len(narrow)} symbols → {output_dir / f'cpr_narrow_{date}.csv'}")
        print(f"✓ Bullish CPR: {len(bullish)} symbols → {output_dir / f'cpr_bullish_{date}.csv'}")
        print(f"✓ Bearish CPR: {len(bearish)} symbols → {output_dir / f'cpr_bearish_{date}.csv'}")
        print(f"✓ Top 20 Narrow: {output_dir / f'cpr_top20_narrow_{date}.csv'}")

    return ScanResult(
        date=date,
        cash_rows=len(df),
        fo_available="Segment" in df.columns and (df["Segment"] == "F&O + Cash").any(),
        full=full_table,
        narrow=narrow,
        bullish=bullish,
        bearish=bearish,
        top20=top20,
        output_dir=output_dir,
    )


def scan_eod_cpr(
    date: str,
    output_dir: Optional[Path] = None,
    write_csv: bool = True,
    lookback: int = HISTORY_LOOKBACK_HTF,
) -> ScanResult:
    """Download bhavcopies, compute CPR, attach history features, optionally write CSVs."""
    session = _nse_session()
    try:
        cash_raw = download_bhavcopy(CASH_URL, date, session=session)
        if cash_raw is None:
            raise RuntimeError("Failed to download cash bhavcopy.")
        cash_df = normalize_bhavcopy(cash_raw, cash_only=True)
        print(f"Cash bhavcopy: {len(cash_raw)} rows → {len(cash_df)} EQ symbols")
        cash_df = keep_listed_equity(cash_df)

        fo_raw = download_bhavcopy(FO_URL, date, session=session)
        fo_df = None
        if fo_raw is not None:
            fo_df = normalize_bhavcopy(fo_raw, cash_only=False)
            print(f"F&O bhavcopy: {len(fo_raw)} rows → {fo_df['SYMBOL'].nunique()} unique symbols")
        else:
            print("F&O bhavcopy not available (weekend/holiday?)")

        cash_df = tag_fo_symbols(cash_df, fo_df)
        cash_df = attach_industry(cash_df, fetch=True)
        cash_df = compute_cpr(cash_df)
        cash_df = apply_bullish_cpr_filters(cash_df)

        seed_bhavcopy_cache(cash_df, date, output_dir=output_dir)
        if lookback and lookback > 0:
            hist_dates = ensure_bhavcopy_history(
                date, lookback=lookback, output_dir=output_dir, session=session
            )
            cash_df = attach_history_features(
                cash_df, load_history_panel(hist_dates, output_dir), own_window=HISTORY_LOOKBACK
            )
            setups = int((cash_df["Setup"].isin(["Long", "Short", "Watch"])).sum()) if "Setup" in cash_df.columns else 0
            own_n = int(cash_df["Own_Narrow"].sum()) if "Own_Narrow" in cash_df.columns else 0
            print(f"History features: Own_Narrow {own_n} | Setups {setups}")

        if write_csv:
            result = export_results(cash_df, date, output_dir=output_dir)
            result = attach_htf_to_result(result, output_dir=output_dir, write_csv=True)
            if lookback and lookback > 0:
                backfill_cached_scans(date, output_dir=output_dir, lookback=lookback, skip_existing=True)
            return result

        full_table, narrow, bullish, bearish, top20 = split_shortlists(cash_df)
        result = ScanResult(
            date=date,
            cash_rows=len(cash_df),
            fo_available=fo_df is not None,
            full=full_table,
            narrow=narrow,
            bullish=bullish,
            bearish=bearish,
            top20=top20,
            output_dir=Path(output_dir) if output_dir is not None else OUTPUT_DIR,
        )
        return attach_htf_to_result(result, output_dir=output_dir, write_csv=False)
    finally:
        session.close()


def main(argv: Optional[List[str]] = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print("Usage: python nse_cpr_scanner.py YYYYMMDD [--lookback 252]")
        print("       python nse_cpr_scanner.py --backfill YYYYMMDD")
        print("Example: python nse_cpr_scanner.py 20260813")
        sys.exit(0 if argv and argv[0] in ("-h", "--help") else 1)

    lookback = HISTORY_LOOKBACK_HTF
    if "--lookback" in argv:
        idx = argv.index("--lookback")
        try:
            lookback = int(argv[idx + 1])
        except (IndexError, ValueError):
            print("--lookback needs an integer, e.g. --lookback 252")
            sys.exit(1)

    if argv[0] == "--backfill":
        date = argv[1] if len(argv) > 1 and argv[1] != "--lookback" else last_completed_session()
        try:
            datetime.strptime(date, "%Y%m%d")
        except ValueError:
            print("Date must be YYYYMMDD, e.g. 20260813")
            sys.exit(1)
        print(f"=== Backfill archive scans through {date} ===\n")
        dates = backfill_cached_scans(date, lookback=lookback, skip_existing=True)
        print(f"Sessions available: {len(dates)}")
        return

    date = argv[0]
    print(f"=== NSE EOD CPR Scanner for {date} ===\n")
    try:
        datetime.strptime(date, "%Y%m%d")
    except ValueError:
        print("Date must be YYYYMMDD, e.g. 20260813")
        sys.exit(1)

    try:
        result = scan_eod_cpr(date, lookback=lookback)
    except Exception as exc:
        print(f"Scan failed: {exc}")
        sys.exit(1)

    print("\n=== Scan Complete ===")
    print(f"EQ symbols: {result.cash_rows}")
    print(f"Narrow: {len(result.narrow)} | Bullish: {len(result.bullish)} | Bearish: {len(result.bearish)}")
    print(f"Output directory: {result.output_dir.resolve()}")


if __name__ == "__main__":
    main()
