"""Inspect SQLite tables and row counts without mutating the database."""
import argparse, sqlite3
from mac_tinker.common import add_output_args, emit

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); add_output_args(p); p.add_argument("file"); a=p.parse_args(argv); con=sqlite3.connect(f"file:{a.file}?mode=ro",uri=True); con.row_factory=sqlite3.Row
    tables=[r[0] for r in con.execute("select name from sqlite_master where type='table' order by name")]; rows=[]
    for table in tables:
        safe=table.replace('"','""'); count=con.execute(f'SELECT count(*) FROM "{safe}"').fetchone()[0]; cols=[dict(x) for x in con.execute(f'PRAGMA table_info("{safe}")')]; rows.append({"table":table,"rows":count,"columns":cols})
    con.close(); emit({"file":a.file,"tables":rows},a.json)
if __name__=="__main__": main()
