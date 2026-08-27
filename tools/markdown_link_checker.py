#!/usr/bin/env python3
"""Run the markdown link checker tool."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mac_tinker.tools.markdown_link_checker import main
if __name__ == "__main__":
    main()
