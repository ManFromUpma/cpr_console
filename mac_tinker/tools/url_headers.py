"""Fetch only HTTP response headers, useful for learning web diagnostics."""
import argparse, urllib.request, urllib.error
from mac_tinker.common import add_output_args, emit

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); add_output_args(p); p.add_argument("url"); a=p.parse_args(argv); req=urllib.request.Request(a.url,method="HEAD",headers={"User-Agent":"mac-tinker/1.0"})
    try:
        with urllib.request.urlopen(req,timeout=10) as r: data={"url":a.url,"status":r.status,"headers":dict(r.headers)}
    except urllib.error.HTTPError as e: data={"url":a.url,"status":e.code,"headers":dict(e.headers),"error":str(e)}
    except Exception as e: data={"url":a.url,"error":str(e)}
    emit(data,a.json)
if __name__=="__main__": main()
