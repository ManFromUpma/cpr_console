#!/usr/bin/env python3
"""Run the base64 lab tool."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mac_tinker.tools.base64_lab import main
if __name__ == "__main__":
    main()
