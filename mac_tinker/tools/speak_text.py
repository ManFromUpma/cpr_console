"""Speak text with macOS's built-in speech command; nothing is saved by this tool."""
import argparse, subprocess
from mac_tinker.common import add_output_args, emit

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); add_output_args(p); p.add_argument("text"); p.add_argument("--voice"); p.add_argument("--rate",type=int); a=p.parse_args(argv); args=["say"]; 
    if a.voice: args += ["-v",a.voice]
    if a.rate: args += ["-r",str(a.rate)]
    args.append(a.text); c=subprocess.run(args,capture_output=True,text=True); emit({"command":args,"returncode":c.returncode,"stdout":c.stdout,"stderr":c.stderr},a.json)
if __name__=="__main__": main()
