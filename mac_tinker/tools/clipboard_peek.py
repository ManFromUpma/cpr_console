"""Read the current clipboard through pbpaste; no clipboard history is stored."""
import argparse
from mac_tinker.common import add_output_args, emit, mac_command

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); add_output_args(p); p.add_argument("--chars",type=int,default=2000); a=p.parse_args(argv); r=mac_command("pbpaste",[]); r["stdout"]=r.get("stdout","")[:a.chars]; emit(r,a.json)
if __name__=="__main__": main()
