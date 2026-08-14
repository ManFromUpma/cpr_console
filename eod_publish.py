#!/usr/bin/env python3
"""
Daily publish pipeline for the NSE EOD CPR website.

1. Download the latest (or given) session bhavcopy
2. Write CSVs under cpr_output/
3. Rebuild the static site under site/

Usage:
    python eod_publish.py
    python eod_publish.py 20260813
    python eod_publish.py --site-only
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from eod_site import build_site
from nse_cpr_scanner import (
    OUTPUT_DIR,
    HISTORY_LOOKBACK_HTF,
    candidate_session_dates,
    discover_scan_dates,
    scan_eod_cpr,
)


def scan_latest(date: str | None, output_dir: Path, lookback: int = HISTORY_LOOKBACK_HTF) -> str:
    dates = [date] if date else candidate_session_dates()
    last_error = None
    for candidate in dates:
        print(f"Trying session {candidate}…")
        try:
            result = scan_eod_cpr(candidate, output_dir=output_dir, lookback=lookback)
            print(f"Scanned {result.date}: {result.cash_rows} EQ names")
            return result.date
        except Exception as exc:
            last_error = exc
            print(f"  skipped {candidate}: {exc}")
    raise RuntimeError(f"No bhavcopy available. Last error: {last_error}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Scan NSE EOD CPR and publish the static site")
    parser.add_argument("date", nargs="?", help="YYYYMMDD. Default: last completed weekday session")
    parser.add_argument("--site-only", action="store_true", help="Rebuild HTML from existing CSVs")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    parser.add_argument("--site-dir", default="site")
    parser.add_argument(
        "--lookback",
        type=int,
        default=HISTORY_LOOKBACK_HTF,
        help="Prior cash sessions to cache for overlay / own-narrow / HTF bars (default 252)",
    )
    args = parser.parse_args(argv)

    output_dir = Path(args.output_dir)
    if args.date and len(args.date) != 8:
        print("Date must be YYYYMMDD")
        sys.exit(1)

    if not args.site_only:
        scan_latest(args.date, output_dir, lookback=args.lookback)
    elif not discover_scan_dates(output_dir):
        print(f"No CSVs in {output_dir}. Run without --site-only first.")
        sys.exit(1)

    dates = build_site(output_dir, Path(args.site_dir))
    print(f"Published {len(dates)} session(s). Open site/index.html or: python eod_site.py --serve")


if __name__ == "__main__":
    main()
