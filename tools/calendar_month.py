#!/usr/bin/env python3
"""Run the calendar month tool."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mac_tinker.tools.calendar_month import main
if __name__ == "__main__":
    main()
