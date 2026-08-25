#!/usr/bin/env python3
"""Run the offline professional CPR repository review."""
from __future__ import annotations

import argparse
from pathlib import Path

from expert_review_agent import run_review


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a review-only CPR Console expert report")
    parser.add_argument("root", nargs="?", default=".", help="Repository root to review")
    parser.add_argument("--report", help="Markdown report output path")
    parser.add_argument("--evidence", help="JSON evidence output path")
    args = parser.parse_args()
    report, evidence = run_review(
        Path(args.root),
        report_path=Path(args.report) if args.report else None,
        evidence_path=Path(args.evidence) if args.evidence else None,
    )
    print(f"Report: {report}")
    print(f"Evidence: {evidence}")


if __name__ == "__main__":
    main()
