"""Explain which Python interpreter and packages are active."""
import argparse, importlib.metadata, platform, sys
from mac_tinker.common import add_output_args, emit, run_command

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); add_output_args(p); a=p.parse_args(argv); c,o,e=run_command([sys.executable,"-m","pip","--version"],10); packages=sorted((d.metadata.get("Name") or "",d.version) for d in importlib.metadata.distributions()); emit({"executable":sys.executable,"version":platform.python_version(),"prefix":sys.prefix,"venv":sys.prefix!=getattr(sys,"base_prefix",sys.prefix),"pip":{"returncode":c,"stdout":o,"stderr":e},"packages":[{"name":n,"version":v} for n,v in packages]},a.json)
if __name__=="__main__": main()
