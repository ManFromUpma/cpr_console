"""Check whether a TCP port accepts connections."""
import argparse, socket, time
from mac_tinker.common import add_output_args, emit

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); add_output_args(p); p.add_argument("host"); p.add_argument("port",type=int); p.add_argument("--timeout",type=float,default=2); a=p.parse_args(argv); start=time.perf_counter(); s=socket.socket(); s.settimeout(a.timeout)
    try: code=s.connect_ex((a.host,a.port)); ok=code==0
    except OSError as e: code=-1; ok=False; err=str(e)
    else: err=""
    finally: s.close()
    emit({"host":a.host,"port":a.port,"open":ok,"connect_code":code,"error":err,"elapsed_ms":round((time.perf_counter()-start)*1000,2)},a.json)
if __name__=="__main__": main()
