"""Estimate the installed size of Python packages in the active environment."""
import argparse, importlib.metadata
from pathlib import Path
from mac_tinker.common import add_output_args, emit, human_bytes

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); add_output_args(p); p.add_argument("--count",type=int,default=30); a=p.parse_args(argv); rows=[]
    for d in importlib.metadata.distributions():
        total=0
        try:
            for f in d.files or []:
                q=Path(d.locate_file(f));
                if q.is_file(): total+=q.stat().st_size
        except OSError: pass
        rows.append({"name":d.metadata.get("Name"),"version":d.version,"size":total,"size_human":human_bytes(total)})
    emit(sorted(rows,key=lambda x:x["size"],reverse=True)[:a.count],a.json)
if __name__=="__main__": main()
