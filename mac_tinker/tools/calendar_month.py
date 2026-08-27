"""Render a month calendar and highlight an optional date."""
import argparse, calendar, datetime
from mac_tinker.common import add_output_args, emit

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); add_output_args(p); p.add_argument("year",type=int); p.add_argument("month",type=int); p.add_argument("--day",type=int); a=p.parse_args(argv); text=calendar.month(a.year,a.month); data={"year":a.year,"month":a.month,"calendar":text}
    if a.day:
        try: data["date_valid"]=datetime.date(a.year,a.month,a.day).isoformat()
        except ValueError as e: data["date_valid"]=False; data["error"]=str(e)
    emit(data,a.json)
if __name__=="__main__": main()
