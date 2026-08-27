"""Show Homebrew formulae and casks, if Homebrew is installed."""
import argparse
from mac_tinker.common import add_output_args, emit, run_command

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); add_output_args(p); a=p.parse_args(argv); data={}
    for key,args in (("formulae",["brew","list","--formula","--versions"]),("casks",["brew","list","--cask","--versions"]),("outdated",["brew","outdated"])):
        c,o,e=run_command(args,30); data[key]={"returncode":c,"stdout":o,"stderr":e}
    emit(data,a.json)
if __name__=="__main__": main()
