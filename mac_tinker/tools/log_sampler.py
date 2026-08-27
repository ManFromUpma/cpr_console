"""Read a bounded slice of recent macOS unified logs for observation."""
import argparse
from mac_tinker.common import add_output_args, emit, mac_command

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); add_output_args(p); p.add_argument("--last",default="10m",help="Examples: 10m, 1h, 1d"); p.add_argument("--predicate",help="Optional unified-log predicate"); a=p.parse_args(argv); args=["show","--last",a.last,"--style","compact","--info","--debug"]; 
    if a.predicate: args += ["--predicate",a.predicate]
    emit(mac_command("log",args,30),a.json)
if __name__=="__main__": main()
