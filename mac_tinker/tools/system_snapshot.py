"""Compact hardware and software orientation report."""
import argparse, json, platform, os, socket
from mac_tinker.common import add_output_args, emit, mac_command

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); add_output_args(p); a=p.parse_args(argv)
    data={"platform":platform.platform(),"system":platform.system(),"release":platform.release(),"machine":platform.machine(),"python":platform.python_version(),"hostname":socket.gethostname(),"cpu_count":os.cpu_count()}
    if platform.system()=="Darwin":
        data["system_profiler"]=mac_command("system_profiler",["SPHardwareDataType","SPSoftwareDataType","-json"],30)
    emit(data,a.json)
if __name__=="__main__": main()
