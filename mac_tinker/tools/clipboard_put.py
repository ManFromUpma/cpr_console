"""Copy explicitly supplied text to the macOS clipboard."""
import argparse, subprocess
from mac_tinker.common import add_output_args, emit

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); add_output_args(p); p.add_argument("text"); a=p.parse_args(argv); c=subprocess.run(["pbcopy"],input=a.text,text=True,capture_output=True); emit({"characters":len(a.text),"returncode":c.returncode,"stderr":c.stderr},a.json)
if __name__=="__main__": main()
