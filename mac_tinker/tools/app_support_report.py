"""Find large per-user Application Support folders for inspection."""
import argparse
from pathlib import Path
from mac_tinker.common import add_output_args, emit, human_bytes

def size(path):
    total=0
    try:
        for f in path.rglob("*"):
            if f.is_file(): total+=f.stat().st_size
    except OSError: pass
    return total

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); add_output_args(p); p.add_argument("--count",type=int,default=25); a=p.parse_args(argv); root=Path.home()/"Library/Application Support"; rows=[]
    try:
        for d in root.iterdir():
            if d.is_dir(): s=size(d); rows.append({"name":d.name,"path":str(d),"size":s,"size_human":human_bytes(s)})
    except OSError as e: rows=[{"error":str(e)}]
    emit(sorted(rows,key=lambda x:x.get("size",0),reverse=True)[:a.count],a.json)
if __name__=="__main__": main()
