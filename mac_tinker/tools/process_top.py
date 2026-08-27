"""List the most CPU- or memory-hungry processes."""
import argparse
from mac_tinker.common import add_output_args, emit, run_command

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); add_output_args(p); p.add_argument("--sort",choices=["cpu","memory"],default="cpu"); p.add_argument("--count",type=int,default=15); a=p.parse_args(argv)
    sort="-o %cpu" if a.sort=="cpu" else "-o %mem"; code,out,err=run_command(["ps","-Ao","pid,ppid,%cpu,%mem,etime,comm", "-r"],10); lines=out.splitlines()[:a.count+1]; emit({"sort":a.sort,"lines":lines,"returncode":code,"stderr":err},a.json)
if __name__=="__main__": main()
