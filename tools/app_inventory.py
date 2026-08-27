#!/usr/bin/env python3
"""Run the app inventory tool."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mac_tinker.tools.app_inventory import main
if __name__ == "__main__":
    main()
