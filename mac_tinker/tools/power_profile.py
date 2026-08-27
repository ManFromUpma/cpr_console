"""Inspect current power-management settings."""
import argparse
from mac_tinker.common import add_output_args, emit, mac_command

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); add_output_args(p); a=p.parse_args(argv); emit(mac_command("pmset",["-g","custom"]),a.json)
if __name__=="__main__": main()
