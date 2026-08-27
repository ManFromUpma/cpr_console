"""Flatten nested JSON into dotted paths, a practical data-shaping exercise."""
import argparse, json, sys
from pathlib import Path
from mac_tinker.common import add_output_args, emit

def flatten(x,prefix="",out=None):
    out={} if out is None else out
    if isinstance(x,dict):
        for k,v in x.items(): flatten(v,f"{prefix}.{k}" if prefix else str(k),out)
    elif isinstance(x,list):
        for i,v in enumerate(x): flatten(v,f"{prefix}[{i}]",out)
    else: out[prefix]=x
    return out

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); add_output_args(p); p.add_argument("file",nargs="?",help="JSON file, or stdin if omitted"); a=p.parse_args(argv); raw=Path(a.file).read_text() if a.file else sys.stdin.read(); emit(flatten(json.loads(raw)),a.json)
if __name__=="__main__": main()
