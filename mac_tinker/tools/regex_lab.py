"""Try a regular expression against text and show match spans."""
import argparse, re
from mac_tinker.common import add_output_args, emit

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); add_output_args(p); p.add_argument("pattern"); p.add_argument("text"); p.add_argument("--ignore-case",action="store_true"); a=p.parse_args(argv); flags=re.I if a.ignore_case else 0
    try: matches=[{"text":m.group(0),"start":m.start(),"end":m.end(),"groups":m.groups()} for m in re.finditer(a.pattern,a.text,flags)] ; data={"pattern":a.pattern,"matches":matches}
    except re.error as e: data={"pattern":a.pattern,"error":str(e)}
    emit(data,a.json)
if __name__=="__main__": main()
