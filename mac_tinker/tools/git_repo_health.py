"""Summarize Git working-tree hygiene without changing the repository."""
import argparse
from pathlib import Path
from mac_tinker.common import add_output_args, emit, run_command

def cmd(cwd,args):
    c,o,e=run_command(["git"]+args,10); return {"returncode":c,"stdout":o,"stderr":e}
def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); add_output_args(p); p.add_argument("path",nargs="?",default="."); a=p.parse_args(argv); cwd=str(Path(a.path).resolve()); emit({"root":cwd,"status":cmd(cwd,["-C",cwd,"status","--short"]),"branch":cmd(cwd,["-C",cwd,"branch","--show-current"]),"recent":cmd(cwd,["-C",cwd,"log","-5","--oneline"])},a.json)
if __name__=="__main__": main()
