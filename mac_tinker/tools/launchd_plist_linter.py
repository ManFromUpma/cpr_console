"""Lint a launchd plist without loading or changing it."""
import argparse, plistlib
from pathlib import Path
from mac_tinker.common import add_output_args, emit

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); add_output_args(p); p.add_argument("path"); a=p.parse_args(argv); issues=[]
    try:
        with Path(a.path).open("rb") as f: data=plistlib.load(f)
        if not isinstance(data,dict): issues.append("Top level value is not a dictionary")
        for key in ("Label","ProgramArguments"):
            if key not in data: issues.append(f"Missing recommended/required key: {key}")
        if "ProgramArguments" in data and not isinstance(data["ProgramArguments"],list): issues.append("ProgramArguments should be a list")
        if "Program" in data: issues.append("Prefer ProgramArguments for explicit arguments")
        result={"valid_plist":True,"issues":issues,"keys":sorted(data) if isinstance(data,dict) else []}
    except Exception as e: result={"valid_plist":False,"issues":[str(e)]}
    emit(result,a.json)
if __name__=="__main__": main()
