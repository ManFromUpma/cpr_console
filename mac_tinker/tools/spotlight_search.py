"""Search the local Spotlight index with mdfind, returning paths only."""
import argparse
from mac_tinker.common import add_output_args, emit, mac_command

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); add_output_args(p); p.add_argument("query",help="Spotlight query, for example 'kMDItemFSName == *.pdf'"); p.add_argument("--path"); a=p.parse_args(argv); args=[]
    if a.path: args += ["-onlyin",a.path]
    args.append(a.query); emit(mac_command("mdfind",args,20),a.json)
if __name__=="__main__": main()
