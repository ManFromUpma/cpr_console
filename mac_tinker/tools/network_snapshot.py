"""Capture a readable snapshot of interfaces, routes, and DNS configuration."""
import argparse
from mac_tinker.common import add_output_args, emit, run_command

def cmd(args):
    c,o,e=run_command(args,10); return {"returncode":c,"stdout":o,"stderr":e}
def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); add_output_args(p); a=p.parse_args(argv); data={"interfaces":cmd(["ifconfig"]),"routes":cmd(["netstat","-rn"]),"dns":cmd(["scutil","--dns"])}; emit(data,a.json)
if __name__=="__main__": main()
