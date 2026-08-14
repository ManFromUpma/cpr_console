#!/usr/bin/env python3
"""
NSE EOD CPR Scanner

Separate from the Shah CPR console (`cpr_engine.py` / `app.py`) and the
intraday breakout screener (`cpr_breakout_engine.py` / `breakout_app.py`).

- Downloads NSE bhavcopy CSVs (cash + F&O)
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
    for col in ["OPEN", "HIGH", "LOW", "CLOSE"]:
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


def keep_listed_equity(df: pd.DataFrame) -> pd.DataFrame:
    """EQ operating companies only — drop ETFs, AMCs, mutual funds, gilt/liquid products."""
    if df.empty:
        return df
    dropped = non_equity_mask(df)
    kept = df.loc[~dropped].copy()
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
    "CPR_Class",
    "Bias",
    "Price_Position",
    "Segment",
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
    "Pivot",
    "BC",
    "TC",
    "CPR_Bottom",
    "CPR_Top",
    "CPR_Width",
    "CPR_Width_Pct",
    "CPR_Class",
    "Bias",
    "Price_Position",
    "Segment",
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
    for col in ("Bullish_CPR", "Bearish_CPR"):
        if col in full.columns:
            full[col] = full[col].astype(str).str.lower().isin(["true", "1", "yes"])
    if "Bullish_CPR" not in full.columns:
        full = apply_bullish_cpr_filters(full)
    full = keep_listed_equity(full)
    full = attach_industry(full)
    _, narrow, bullish, bearish, top20 = split_shortlists(full)
    fo_available = "Segment" in full.columns and bool((full["Segment"] == "F&O + Cash").any())
    return ScanResult(
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


def split_shortlists(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    full_table = df.sort_values("CPR_Width_Pct").reset_index(drop=True)
    narrow = df[df["CPR_Class"] == "Narrow"].sort_values("CPR_Width_Pct").reset_index(drop=True)
    bullish = df[df["Bullish_CPR"]].sort_values("CPR_Width_Pct").reset_index(drop=True)
    bearish = df[df["Bearish_CPR"]].sort_values("CPR_Width_Pct", ascending=False).reset_index(drop=True)
    top_cols = [c for c in ["SYMBOL", "Industry", "CLOSE", "CPR_Width_Pct", "Bias", "Price_Position", "Segment"] if c in narrow.columns]
    ranked = narrow[narrow["CPR_Width_Pct"] > 0] if "CPR_Width_Pct" in narrow.columns else narrow
    top20 = ranked.head(20)[top_cols].reset_index(drop=True) if not ranked.empty else pd.DataFrame(columns=top_cols)
    return full_table, narrow, bullish, bearish, top20


def export_results(df: pd.DataFrame, date: str, output_dir: Optional[Path] = None) -> ScanResult:
    """Export ranked tables and shortlists."""
    output_dir = Path(output_dir) if output_dir is not None else OUTPUT_DIR
    output_dir.mkdir(exist_ok=True)
    full_table, narrow, bullish, bearish, top20 = split_shortlists(df)

    full_table.to_csv(output_dir / f"cpr_full_{date}.csv", index=False)
    print(f"✓ Full table: {output_dir / f'cpr_full_{date}.csv'}")

    narrow.to_csv(output_dir / f"cpr_narrow_{date}.csv", index=False)
    print(f"✓ Narrow CPR: {len(narrow)} symbols → {output_dir / f'cpr_narrow_{date}.csv'}")

    bullish.to_csv(output_dir / f"cpr_bullish_{date}.csv", index=False)
    print(f"✓ Bullish CPR: {len(bullish)} symbols → {output_dir / f'cpr_bullish_{date}.csv'}")

    bearish.to_csv(output_dir / f"cpr_bearish_{date}.csv", index=False)
    print(f"✓ Bearish CPR: {len(bearish)} symbols → {output_dir / f'cpr_bearish_{date}.csv'}")

    top20.to_csv(output_dir / f"cpr_top20_narrow_{date}.csv", index=False)
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


def scan_eod_cpr(date: str, output_dir: Optional[Path] = None, write_csv: bool = True) -> ScanResult:
    """Download bhavcopies, compute CPR, optionally write CSVs."""
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

        if write_csv:
            return export_results(cash_df, date, output_dir=output_dir)

        full_table, narrow, bullish, bearish, top20 = split_shortlists(cash_df)
        return ScanResult(
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
    finally:
        session.close()


def main(date: str) -> None:
    print(f"=== NSE EOD CPR Scanner for {date} ===\n")
    try:
        datetime.strptime(date, "%Y%m%d")
    except ValueError:
        print("Date must be YYYYMMDD, e.g. 20260813")
        sys.exit(1)

    try:
        result = scan_eod_cpr(date)
    except Exception as exc:
        print(f"Scan failed: {exc}")
        sys.exit(1)

    print("\n=== Scan Complete ===")
    print(f"EQ symbols: {result.cash_rows}")
    print(f"Narrow: {len(result.narrow)} | Bullish: {len(result.bullish)} | Bearish: {len(result.bearish)}")
    print(f"Output directory: {result.output_dir.resolve()}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python nse_cpr_scanner.py YYYYMMDD")
        print("Example: python nse_cpr_scanner.py 20260813")
        sys.exit(1)
    main(sys.argv[1])
