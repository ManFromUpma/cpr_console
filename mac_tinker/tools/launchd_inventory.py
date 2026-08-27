"""List launchd plist files by scope; read-only by design."""
import argparse
from pathlib import Path
from mac_tinker.common import add_output_args, emit

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); add_output_args(p); p.add_argument("--all",action="store_true"); a=p.parse_args(argv); home=Path.home(); roots=[home/"Library/LaunchAgents",Path("/Library/LaunchAgents"),Path("/Library/LaunchDaemons")]
    if a.all: roots += [Path("/System/Library/LaunchAgents"),Path("/System/Library/LaunchDaemons")]
    rows=[]
    for root in roots:
        try:
            for f in sorted(root.glob("*.plist")): rows.append({"scope":str(root),"path":str(f),"size":f.stat().st_size})
        except OSError: pass
    emit(rows,a.json)
if __name__=="__main__": main()
