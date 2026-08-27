#!/usr/bin/env python3
"""Run the python env report tool."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mac_tinker.tools.python_env_report import main
if __name__ == "__main__":
    main()
