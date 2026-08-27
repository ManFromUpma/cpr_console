"""Create a SHA-256 manifest for a folder without copying or deleting files."""
import argparse, hashlib, json
from pathlib import Path
from mac_tinker.common import add_output_args, emit, iter_files

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); add_output_args(p); p.add_argument("path",nargs="?",default="."); p.add_argument("--output",help="Optional JSON manifest path"); p.add_argument("--include-hidden",action="store_true"); a=p.parse_args(argv); root=Path(a.path).resolve(); rows=[]
    for f in iter_files(root,a.include_hidden):
        h=hashlib.sha256()
        try:
            with f.open("rb") as stream:
                while b:=stream.read(1024*1024): h.update(b)
            rows.append({"path":str(f.relative_to(root)),"size":f.stat().st_size,"sha256":h.hexdigest()})
        except OSError as e: rows.append({"path":str(f),"error":str(e)})
    result={"root":str(root),"files":rows};
    if a.output: Path(a.output).write_text(json.dumps(result,indent=2)+"\n"); result["manifest_written"]=a.output
    emit(result,a.json)
if __name__=="__main__": main()
