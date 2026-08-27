"""Find duplicate files by size and SHA-256 hash."""
import argparse, hashlib
from pathlib import Path
from collections import defaultdict
from mac_tinker.common import add_output_args, emit, iter_files

def digest(path, chunk=1024*1024):
    h=hashlib.sha256()
    try:
        with path.open("rb") as f:
            while b:=f.read(chunk): h.update(b)
        return h.hexdigest()
    except OSError: return None

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); add_output_args(p); p.add_argument("path",nargs="?",default="."); p.add_argument("--min-size",default="1K"); p.add_argument("--include-hidden",action="store_true"); a=p.parse_args(argv)
    from mac_tinker.common import parse_bytes
    by_size=defaultdict(list)
    for f in iter_files(Path(a.path),a.include_hidden):
        try:
            if f.stat().st_size>=parse_bytes(a.min_size): by_size[f.stat().st_size].append(f)
        except OSError: pass
    groups=[]
    for size,paths in by_size.items():
        if len(paths)>1:
            by_hash=defaultdict(list)
            for f in paths:
                if (d:=digest(f)): by_hash[d].append(str(f))
            for h,items in by_hash.items():
                if len(items)>1: groups.append({"size":size,"hash":h,"files":items})
    emit(groups,a.json)
if __name__=="__main__": main()
