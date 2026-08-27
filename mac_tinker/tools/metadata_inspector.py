"""Read Spotlight metadata for a file with mdls when available."""
import argparse
from mac_tinker.common import add_output_args, emit, mac_command

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); add_output_args(p); p.add_argument("path"); p.add_argument("--raw",action="store_true"); a=p.parse_args(argv); args=[] if a.raw else ["-json"]; args.append(a.path); emit(mac_command("mdls",args),a.json)
if __name__=="__main__": main()
