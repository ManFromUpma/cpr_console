#!/usr/bin/env python3
"""Run the disk space watch tool."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mac_tinker.tools.disk_space_watch import main
if __name__ == "__main__":
    main()
