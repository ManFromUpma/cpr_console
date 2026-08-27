"""Watch a folder with polling and report created, removed, or changed files."""
import argparse, time
from pathlib import Path
from mac_tinker.common import add_output_args, emit

def snapshot(root):
    out={}
    for p in root.rglob("*"):
        if p.is_file():
            try: out[str(p)]=(p.stat().st_size,p.stat().st_mtime_ns)
            except OSError: pass
    return out

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); add_output_args(p); p.add_argument("path",nargs="?",default="."); p.add_argument("--seconds",type=int,default=10); p.add_argument("--interval",type=float,default=1); a=p.parse_args(argv); root=Path(a.path); before=snapshot(root); events=[]; end=time.time()+a.seconds
    while time.time()<end:
        time.sleep(max(.1,a.interval)); after=snapshot(root)
        for x in sorted(set(after)-set(before)): events.append({"event":"created","path":x})
        for x in sorted(set(before)-set(after)): events.append({"event":"removed","path":x})
        for x in sorted(set(after)&set(before)):
            if after[x]!=before[x]: events.append({"event":"changed","path":x})
        before=after
    emit({"path":str(root.resolve()),"events":events},a.json)
if __name__=="__main__": main()
