"""Inspect download-quarantine extended attributes without changing them."""
import argparse, subprocess
from pathlib import Path
from mac_tinker.common import add_output_args, emit, iter_files

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); add_output_args(p); p.add_argument("path",nargs="?",default="."); p.add_argument("--recursive",action="store_true"); a=p.parse_args(argv); paths=iter_files(Path(a.path)) if a.recursive or Path(a.path).is_dir() else [Path(a.path)]; rows=[]
    for f in paths:
        c=subprocess.run(["xattr","-p","com.apple.quarantine",str(f)],capture_output=True,text=True)
        if c.returncode==0: rows.append({"path":str(f),"quarantine":c.stdout.strip()})
    emit(rows,a.json)
if __name__=="__main__": main()
