"""Encode or decode Base64 text, a gentle binary-data experiment."""
import argparse, base64, binascii
from mac_tinker.common import add_output_args, emit

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); add_output_args(p); g=p.add_mutually_exclusive_group(required=True); g.add_argument("--encode"); g.add_argument("--decode"); a=p.parse_args(argv)
    try:
        if a.encode is not None: result=base64.b64encode(a.encode.encode()).decode(); kind="encoded"
        else: result=base64.b64decode(a.decode,validate=True).decode(errors="replace"); kind="decoded"
        data={"kind":kind,"result":result}
    except (binascii.Error,UnicodeError) as e: data={"error":str(e)}
    emit(data,a.json)
if __name__=="__main__": main()
