"""Poll free space and print a small time series."""
import argparse, shutil, time
from mac_tinker.common import add_output_args, emit, human_bytes

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); add_output_args(p); p.add_argument("path",nargs="?",default="/"); p.add_argument("--seconds",type=int,default=10); p.add_argument("--interval",type=float,default=2); a=p.parse_args(argv); rows=[]; end=time.time()+a.seconds
    while time.time()<end:
        t,u,f=shutil.disk_usage(a.path); rows.append({"time":time.strftime("%H:%M:%S"),"free":f,"free_human":human_bytes(f)}); time.sleep(max(0,a.interval))
    emit({"path":a.path,"samples":rows},a.json)
if __name__=="__main__": main()
