#!/usr/bin/env python3
"""Run the file watch tool."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mac_tinker.tools.file_watch import main
if __name__ == "__main__":
    main()
