"""Hash files and text to learn integrity checks and content fingerprints."""
import argparse, hashlib
from pathlib import Path
from mac_tinker.common import add_output_args, emit

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); add_output_args(p); g=p.add_mutually_exclusive_group(required=True); g.add_argument("--file"); g.add_argument("--text"); p.add_argument("--algorithm",choices=sorted(hashlib.algorithms_guaranteed),default="sha256"); a=p.parse_args(argv); h=hashlib.new(a.algorithm)
    if a.file:
        with Path(a.file).open("rb") as f:
            while b:=f.read(1024*1024): h.update(b)
        data={"kind":"file","path":a.file}
    else: h.update(a.text.encode()); data={"kind":"text"}
    data.update({"algorithm":a.algorithm,"digest":h.hexdigest()}); emit(data,a.json)
if __name__=="__main__": main()
