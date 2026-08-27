"""Show the bytes, hexadecimal form, and printable view of a file prefix."""
import argparse, string
from pathlib import Path
from mac_tinker.common import add_output_args, emit

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); add_output_args(p); p.add_argument("file"); p.add_argument("--bytes",type=int,default=128); a=p.parse_args(argv); data=Path(a.file).read_bytes()[:a.bytes]; emit({"file":a.file,"bytes_read":len(data),"hex":data.hex(" "),"printable":"".join(chr(x) if chr(x) in string.printable and x not in (10,13,9) else "." for x in data)},a.json)
if __name__=="__main__": main()
