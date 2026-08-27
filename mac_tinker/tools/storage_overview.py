"""Show mounted volumes and free space without changing anything."""
import argparse, shutil
from pathlib import Path
from mac_tinker.common import add_output_args, emit, human_bytes, run_command

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); add_output_args(p); p.add_argument("path",nargs="?",default="/"); a=p.parse_args(argv)
    total,used,free=shutil.disk_usage(a.path); data={"path":a.path,"total":total,"used":used,"free":free,"total_human":human_bytes(total),"used_human":human_bytes(used),"free_human":human_bytes(free)}
    code,out,err=run_command(["df","-h"],10); data["mounts"]={"returncode":code,"stdout":out,"stderr":err}; emit(data,a.json)
if __name__=="__main__": main()
