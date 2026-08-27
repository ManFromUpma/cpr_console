"""Print a compact directory tree for learning filesystem structure."""
import argparse
from pathlib import Path
from mac_tinker.common import add_output_args, emit

def build(root, depth, include_hidden, prefix=""):
    if depth<0: return []
    try: children=sorted([p for p in root.iterdir() if include_hidden or not p.name.startswith(".")],key=lambda p:(p.is_file(),p.name.lower()))
    except OSError as e: return [{"error":str(e)}]
    out=[]
    for p in children:
        item={"name":p.name,"type":"file" if p.is_file() else "dir"}
        if p.is_dir(): item["children"]=build(p,depth-1,include_hidden)
        out.append(item)
    return out

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); add_output_args(p); p.add_argument("path",nargs="?",default="."); p.add_argument("--depth",type=int,default=2); p.add_argument("--include-hidden",action="store_true"); a=p.parse_args(argv); emit({"root":str(Path(a.path).resolve()),"tree":build(Path(a.path),a.depth,a.include_hidden)},a.json)
if __name__=="__main__": main()
