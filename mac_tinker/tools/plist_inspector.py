"""Inspect Apple property-list files safely using Python's plistlib."""
import argparse, plistlib
from pathlib import Path
from mac_tinker.common import add_output_args, emit

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); add_output_args(p); p.add_argument("path"); a=p.parse_args(argv); path=Path(a.path)
    try:
        with path.open("rb") as f: value=plistlib.load(f)
        emit({"path":str(path),"type":type(value).__name__,"content":value},a.json)
    except Exception as e: emit({"path":str(path),"error":str(e)},a.json)
if __name__=="__main__": main()
