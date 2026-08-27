"""Check local Markdown links without fetching or modifying anything."""
import argparse, re
from pathlib import Path
from mac_tinker.common import add_output_args, emit
LINK=re.compile(r"!?\[[^\]]*\]\(([^)\s]+)")
def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); add_output_args(p); p.add_argument("file"); a=p.parse_args(argv); root=Path(a.file).resolve().parent; rows=[]
    for target in LINK.findall(Path(a.file).read_text(encoding="utf-8")):
        if target.startswith(("http://","https://","mailto:","#")): state="external-or-anchor"
        else:
            clean=target.split("#",1)[0]; q=(root/clean).resolve(); state="ok" if q.exists() else "missing"
        rows.append({"target":target,"status":state})
    emit({"file":a.file,"links":rows,"missing":sum(x["status"]=="missing" for x in rows)},a.json)
if __name__=="__main__": main()
