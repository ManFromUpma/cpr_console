"""Inspect Unicode code points, names, categories, and normalization."""
import argparse, unicodedata
from mac_tinker.common import add_output_args, emit

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); add_output_args(p); p.add_argument("text"); a=p.parse_args(argv); rows=[]
    for ch in a.text:
        rows.append({"character":ch,"codepoint":f"U+{ord(ch):04X}","name":unicodedata.name(ch,"UNKNOWN"),"category":unicodedata.category(ch),"combining":unicodedata.combining(ch),"nfc":unicodedata.normalize("NFC",ch),"nfd":unicodedata.normalize("NFD",ch)})
    emit(rows,a.json)
if __name__=="__main__": main()
