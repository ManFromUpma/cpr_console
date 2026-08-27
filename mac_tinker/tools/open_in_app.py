"""Ask macOS to open a file, folder, or URL with an optional app."""
import argparse, subprocess
from mac_tinker.common import add_output_args, emit

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); add_output_args(p); p.add_argument("target"); p.add_argument("--app",help="Application name, such as Safari or TextEdit."); a=p.parse_args(argv); args=["open"]+(["-a",a.app] if a.app else [])+[a.target]; c=subprocess.run(args,capture_output=True,text=True); emit({"command":args,"returncode":c.returncode,"stdout":c.stdout,"stderr":c.stderr},a.json)
if __name__=="__main__": main()
