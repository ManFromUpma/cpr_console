"""Find the largest files under a folder; never deletes anything."""
import argparse
from mac_tinker.common import add_output_args, emit, iter_files, path_record
from pathlib import Path

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); add_output_args(p); p.add_argument("path",nargs="?",default="."); p.add_argument("--count",type=int,default=20); p.add_argument("--include-hidden",action="store_true"); a=p.parse_args(argv)
    rows=sorted((path_record(x) for x in iter_files(Path(a.path),a.include_hidden)),key=lambda x:x.get("size",0),reverse=True)[:a.count]; emit(rows,a.json)
if __name__=="__main__": main()
