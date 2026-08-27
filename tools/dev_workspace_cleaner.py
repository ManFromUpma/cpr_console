#!/usr/bin/env python3
"""Run the dev workspace cleaner tool."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mac_tinker.tools.dev_workspace_cleaner import main
if __name__ == "__main__":
    main()
