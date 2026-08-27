"""Report common build/cache folders; it intentionally does not delete them."""
import argparse
from pathlib import Path
from mac_tinker.common import add_output_args, emit, human_bytes
NAMES={"__pycache__",".pytest_cache","node_modules",".mypy_cache",".ruff_cache","dist","build","target",".gradle"}
def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); add_output_args(p); p.add_argument("path",nargs="?",default="."); a=p.parse_args(argv); rows=[]
    for base,dirs,files in __import__('os').walk(a.path):
        dirs[:]=[d for d in dirs if not d.startswith(".") or d in NAMES]
        for d in list(dirs):
            if d in NAMES:
                q=Path(base)/d; total=0
                for x in q.rglob("*"):
                    try:
                        if x.is_file(): total+=x.stat().st_size
                    except OSError: pass
                rows.append({"path":str(q),"category":d,"size":total,"size_human":human_bytes(total)})
    emit(rows,a.json)
if __name__=="__main__": main()
