"""Read selected macOS preference domains without writing changes."""
import argparse
from mac_tinker.common import add_output_args, emit, mac_command

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); add_output_args(p); p.add_argument("domain",help="For example: NSGlobalDomain or com.apple.dock"); p.add_argument("key",nargs="?"); a=p.parse_args(argv); args=["read",a.domain]+(([a.key]) if a.key else []); emit(mac_command("defaults",args),a.json)
if __name__=="__main__": main()
