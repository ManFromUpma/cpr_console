"""Encode or decode URL query text to learn how web data travels."""
import argparse, urllib.parse
from mac_tinker.common import add_output_args, emit

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); add_output_args(p); g=p.add_mutually_exclusive_group(required=True); g.add_argument("--encode"); g.add_argument("--decode"); a=p.parse_args(argv); data={"input":a.encode if a.encode is not None else a.decode,"result":urllib.parse.quote_plus(a.encode) if a.encode is not None else urllib.parse.unquote_plus(a.decode)}; emit(data,a.json)
if __name__=="__main__": main()
