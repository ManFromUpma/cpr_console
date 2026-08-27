#!/usr/bin/env python3
"""Run the system snapshot tool."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mac_tinker.tools.system_snapshot import main
if __name__ == "__main__":
    main()
