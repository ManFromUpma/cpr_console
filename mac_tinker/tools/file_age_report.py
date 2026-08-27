"""Group files by when they were last modified."""
import argparse, time
from pathlib import Path
from collections import Counter
from mac_tinker.common import add_output_args, emit, iter_files

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); add_output_args(p); p.add_argument("path",nargs="?",default="."); p.add_argument("--days",type=int,default=30); p.add_argument("--include-hidden",action="store_true"); a=p.parse_args(argv); now=time.time(); counts=Counter(); examples={}
    for f in iter_files(Path(a.path),a.include_hidden):
        try: age=max(0,int((now-f.stat().st_mtime)/86400)); bucket=f"{min(age,a.days)}+ days" if age>=a.days else f"{age} days"; counts[bucket]+=1; examples.setdefault(bucket,str(f))
        except OSError: pass
    emit({"buckets":dict(sorted(counts.items())),"examples":examples},a.json)
if __name__=="__main__": main()
