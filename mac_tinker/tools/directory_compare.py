"""Compare two directory trees by relative path and file metadata."""
import argparse, filecmp
from pathlib import Path
from mac_tinker.common import add_output_args, emit

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); add_output_args(p); p.add_argument("left"); p.add_argument("right"); a=p.parse_args(argv); d=filecmp.dircmp(a.left,a.right); emit({"left":a.left,"right":a.right,"only_left":d.left_only,"only_right":d.right_only,"common_funny":d.common_funny,"common_dirs":d.common_dirs,"common_files":d.common_files,"diff_files":d.diff_files},a.json)
if __name__=="__main__": main()
