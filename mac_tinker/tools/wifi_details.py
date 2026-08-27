"""Inspect the current Wi-Fi association and nearby network names."""
import argparse
from mac_tinker.common import add_output_args, emit, mac_command

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); add_output_args(p); p.add_argument("--scan",action="store_true",help="Request a nearby-network scan; may take a moment."); a=p.parse_args(argv)
    data={"current":mac_command("networksetup",["-getinfo","Wi-Fi"])}
    data["airport"]=mac_command("/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport",["-I"])
    if a.scan: data["scan"]=mac_command("networksetup",["-listpreferredwirelessnetworks","en0"])
    emit(data,a.json)
if __name__=="__main__": main()
