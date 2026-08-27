"""Profile a CSV file: columns, missing cells, and example values."""
import argparse, csv
from collections import Counter
from mac_tinker.common import add_output_args, emit

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); add_output_args(p); p.add_argument("file"); p.add_argument("--delimiter",default=","); a=p.parse_args(argv); rows=[]
    with open(a.file,newline="",encoding="utf-8-sig") as f: reader=csv.DictReader(f,delimiter=a.delimiter); rows=list(reader)
    cols=reader.fieldnames or []; profile={}
    for c in cols:
        vals=[r.get(c,"") for r in rows]; profile[c]={"missing":sum(v=="" for v in vals),"unique":len(set(vals)),"examples":list(dict.fromkeys(vals))[:5]}
    emit({"file":a.file,"rows":len(rows),"columns":cols,"profile":profile},a.json)
if __name__=="__main__": main()
