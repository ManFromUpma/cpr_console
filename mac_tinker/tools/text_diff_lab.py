"""Compare two text files and explain their line-level differences."""
import argparse, difflib
from pathlib import Path
from mac_tinker.common import add_output_args, emit

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); add_output_args(p); p.add_argument("left"); p.add_argument("right"); a=p.parse_args(argv); l=Path(a.left).read_text().splitlines(True); r=Path(a.right).read_text().splitlines(True); diff=list(difflib.unified_diff(l,r,fromfile=a.left,tofile=a.right)); emit({"left":a.left,"right":a.right,"changed":bool(diff),"unified_diff":"".join(diff)},a.json)
if __name__=="__main__": main()
