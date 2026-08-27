"""Generate a Quick Look thumbnail into an explicit output folder."""
import argparse, subprocess
from pathlib import Path
from mac_tinker.common import add_output_args, emit

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); add_output_args(p); p.add_argument("path"); p.add_argument("--output",default="quicklook_output"); a=p.parse_args(argv); out=Path(a.output).expanduser(); out.mkdir(parents=True,exist_ok=True); c=subprocess.run(["qlmanage","-t","-s","512","-o",str(out),a.path],capture_output=True,text=True); emit({"output":str(out.resolve()),"returncode":c.returncode,"stdout":c.stdout,"stderr":c.stderr},a.json)
if __name__=="__main__": main()
