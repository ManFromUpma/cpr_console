"""Resolve a hostname using Python sockets and optionally macOS lookup tools."""
import argparse, socket, time
from mac_tinker.common import add_output_args, emit, run_command

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); add_output_args(p); p.add_argument("host"); a=p.parse_args(argv); start=time.perf_counter()
    data={"host":a.host}
    try: data["addresses"]=[x[4][0] for x in socket.getaddrinfo(a.host,None)]
    except socket.gaierror as e: data["error"]=str(e)
    data["elapsed_ms"]=round((time.perf_counter()-start)*1000,2); c,o,e=run_command(["nslookup",a.host],10); data["nslookup"]={"returncode":c,"stdout":o,"stderr":e}; emit(data,a.json)
if __name__=="__main__": main()
