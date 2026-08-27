"""List extended attributes on a file or folder."""
import argparse, subprocess
from pathlib import Path
from mac_tinker.common import add_output_args, emit, iter_files

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); add_output_args(p); p.add_argument("path",nargs="?",default="."); p.add_argument("--recursive",action="store_true"); a=p.parse_args(argv); target=Path(a.path); paths=list(iter_files(target)) if a.recursive and target.is_dir() else [target]; rows=[]
    for f in paths:
        c=subprocess.run(["xattr","-l",str(f)],capture_output=True,text=True); rows.append({"path":str(f),"returncode":c.returncode,"attributes":c.stdout,"stderr":c.stderr})
    emit(rows,a.json)
if __name__=="__main__": main()
