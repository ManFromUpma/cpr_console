"""Inventory .app bundles and their bundle identifiers."""
import argparse, plistlib
from pathlib import Path
from mac_tinker.common import add_output_args, emit

def read_app(path):
    info=path/"Contents/Info.plist"; row={"path":str(path),"name":path.stem}
    try:
        with info.open("rb") as f: d=plistlib.load(f)
        row.update({"bundle_id":d.get("CFBundleIdentifier"),"version":d.get("CFBundleShortVersionString") or d.get("CFBundleVersion")})
    except Exception as e: row["error"]=str(e)
    return row

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); add_output_args(p); p.add_argument("root",nargs="?",default="/Applications"); a=p.parse_args(argv); root=Path(a.root); apps=[]
    try: apps=[read_app(x) for x in root.glob("*.app")]
    except OSError: pass
    emit(sorted(apps,key=lambda x:x["name"].lower()),a.json)
if __name__=="__main__": main()
