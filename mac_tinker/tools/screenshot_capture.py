"""Capture a screenshot to a chosen path; the action is explicit and visible."""
import argparse, subprocess
from pathlib import Path
from mac_tinker.common import add_output_args, emit

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); add_output_args(p); p.add_argument("output",nargs="?",default="~/Desktop/mac_tinker_screenshot.png"); p.add_argument("--window",action="store_true"); p.add_argument("--interactive",action="store_true"); a=p.parse_args(argv); out=str(Path(a.output).expanduser()); args=["screencapture"]; args+=(["-w"] if a.window else []); args+=(["-i"] if a.interactive else []); args.append(out); c=subprocess.run(args,capture_output=True,text=True); emit({"output":out,"returncode":c.returncode,"stdout":c.stdout,"stderr":c.stderr},a.json)
if __name__=="__main__": main()
