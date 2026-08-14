"""
Static website for daily NSE EOD CPR scans.

Builds HTML + CSV/ZIP downloads from `cpr_output/`. Does not change the
Shah CPR console or the breakout screener.

Usage:
    python eod_site.py                  # rebuild from existing CSVs
    python eod_site.py --serve 8504     # rebuild and preview locally
"""

from __future__ import annotations

import argparse
import html
import json
import shutil
import zipfile
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Iterable, List, Optional

import pandas as pd

from nse_cpr_scanner import (
    IST,
    ScanResult,
    WEB_EXPORT_COLS,
    discover_scan_dates,
    load_scan_result,
    web_frame,
)

SITE_DIR = Path("site")
ROUND_2 = {
    "OPEN",
    "HIGH",
    "LOW",
    "CLOSE",
    "Pivot",
    "BC",
    "TC",
    "CPR_Bottom",
    "CPR_Top",
    "CPR_Width",
}
TABLE_COLS = [
    "SYMBOL",
    "Industry",
    "CLOSE",
    "CPR_Width_Pct",
    "CPR_Class",
    "Bias",
    "Price_Position",
    "Segment",
    "Pivot",
    "BC",
    "TC",
]


def _date_label(date: str) -> str:
    return datetime.strptime(date, "%Y%m%d").strftime("%d %b %Y")


def _records(df: pd.DataFrame) -> list:
    frame = web_frame(df)
    cols = [c for c in TABLE_COLS if c in frame.columns]
    out = []
    for row in frame.loc[:, cols].itertuples(index=False):
        rec = {}
        for col, val in zip(cols, row):
            if pd.isna(val):
                rec[col] = None
            elif col in ROUND_2:
                rec[col] = round(float(val), 2)
            elif col == "CPR_Width_Pct":
                rec[col] = round(float(val), 4)
            elif col in ("Bullish_CPR", "Bearish_CPR"):
                rec[col] = bool(val)
            else:
                rec[col] = val
        out.append(rec)
    return out


def _write_downloads(result: ScanResult, dest: Path) -> dict:
    dest.mkdir(parents=True, exist_ok=True)
    mapping = {
        "full": ("cpr_full.csv", result.full),
        "narrow": ("cpr_narrow.csv", result.narrow),
        "bullish": ("cpr_bullish.csv", result.bullish),
        "bearish": ("cpr_bearish.csv", result.bearish),
        "top20": ("cpr_top20_narrow.csv", result.top20),
    }
    files = []
    for key, (name, frame) in mapping.items():
        path = dest / name
        web_frame(frame).to_csv(path, index=False)
        files.append(path)

    zip_name = f"cpr_{result.date}.zip"
    zip_path = dest / zip_name
    readme = dest / "README.txt"
    readme.write_text(
        "\n".join(
            [
                f"NSE EOD CPR scan — session {result.date} ({_date_label(result.date)})",
                "CPR from that session's H/L/C applies to the next session.",
                "Research / educational use. Not investment advice.",
                "OHLC sourced from NSE UDI bhavcopy. Not an NSE product.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(readme, "README.txt")
        for path in files:
            zf.write(path, path.name)
    readme.unlink()
    return {
        "full": "downloads/cpr_full.csv",
        "narrow": "downloads/cpr_narrow.csv",
        "bullish": "downloads/cpr_bullish.csv",
        "bearish": "downloads/cpr_bearish.csv",
        "top20": "downloads/cpr_top20_narrow.csv",
        "zip": f"downloads/{zip_name}",
    }


def _payload(result: ScanResult, downloads: dict, dates: Iterable[str], home_href: str) -> dict:
    fo_n = int((result.full["Segment"] == "F&O + Cash").sum()) if "Segment" in result.full.columns else 0
    industries = []
    if "Industry" in result.full.columns:
        industries = sorted(result.full["Industry"].dropna().astype(str).unique().tolist())
    return {
        "date": result.date,
        "label": _date_label(result.date),
        "home": home_href,
        "dates": [{"id": d, "label": _date_label(d)} for d in dates],
        "industries": industries,
        "metrics": {
            "symbols": int(result.cash_rows),
            "narrow": int(len(result.narrow)),
            "bullish": int(len(result.bullish)),
            "bearish": int(len(result.bearish)),
            "fo": fo_n,
        },
        "downloads": downloads,
        "tables": {
            "full": _records(result.full),
            "narrow": _records(result.narrow),
            "bullish": _records(result.bullish),
            "bearish": _records(result.bearish),
            "top20": _records(result.top20),
        },
    }


def _industry_options(payload: dict) -> str:
    parts = ['<option value="Any">Any industry</option>']
    for name in payload.get("industries") or []:
        safe = html.escape(str(name), quote=True)
        parts.append(f'<option value="{safe}">{safe}</option>')
    return "\n      ".join(parts)


def _page_html(payload: dict, asset_prefix: str) -> str:
    data = json.dumps(payload, separators=(",", ":"), ensure_ascii=True)
    industry_opts = _industry_options(payload)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>EOD CPR · {html.escape(payload["label"])}</title>
  <base href="{asset_prefix}">
  <link rel="stylesheet" href="assets/style.css?v=2"/>
</head>
<body>
  <header class="top">
    <div>
      <p class="kicker">Daily scan · next-session CPR</p>
      <h1>NSE EOD CPR</h1>
    </div>
    <label class="date-nav">Session
      <select id="dateSelect"></select>
    </label>
  </header>

  <section class="banner">
    Research only. Not investment advice. Levels are from NSE bhavcopy H/L/C for
    <strong>{html.escape(payload["label"])}</strong> and apply to the <strong>next</strong> session.
    Not an NSE product.
  </section>

  <section class="metrics" id="metrics"></section>

  <section class="downloads" id="downloads"></section>

  <section class="toolbar">
    <input id="search" type="search" placeholder="Search symbol…" autocomplete="off"/>
    <select id="segment"><option value="Any">Any segment</option><option>F&amp;O + Cash</option><option>Cash Only</option></select>
    <label class="filter-label">Industry
      <select id="industry">{industry_opts}</select>
    </label>
    <select id="klass"><option value="Any">Any class</option><option>Narrow</option><option>Moderate</option><option>Wide</option></select>
    <select id="bias"><option value="Any">Any bias</option><option>Bullish</option><option>Bearish</option><option>Neutral</option></select>
  </section>

  <nav class="tabs" id="tabs">
    <button data-tab="full" class="on">Full</button>
    <button data-tab="narrow">Narrow</button>
    <button data-tab="bullish">Bullish</button>
    <button data-tab="bearish">Bearish</button>
    <button data-tab="top20">Top 20</button>
  </nav>

  <p class="count" id="count"></p>
  <div class="table-wrap">
    <table>
      <thead id="head"></thead>
      <tbody id="body"></tbody>
    </table>
  </div>

  <footer>
    Equity stocks only (ETFs, AMCs, mutual funds excluded). Industry from Nifty 500.
    Built from NSE UDI cash + F&amp;O bhavcopy. CPR = Pivot (H+L+C)/3, BC (H+L)/2, TC 2P−BC.
    Narrow ≤ 0.25% · Moderate 0.25–0.75% · Wide &gt; 0.75%.
    Bullish CPR = close above CPR + Pivot &gt; BC + narrow.
  </footer>
  <script>window.CPR_DATA = {data};</script>
  <script src="assets/app.js?v=2"></script>
</body>
</html>
"""


CSS = """
:root {
  --bg: #101418;
  --card: #1a2128;
  --line: #2a343e;
  --text: #e7eef5;
  --muted: #93a0ad;
  --bull: #3ecf8e;
  --bear: #ef6b6b;
  --accent: #8ec0f5;
  --narrow: #c9a7ff;
}
* { box-sizing: border-box; }
html, body { margin: 0; background: var(--bg); color: var(--text); font: 15px/1.45 "IBM Plex Sans", "Segoe UI", sans-serif; }
.top { display: flex; justify-content: space-between; align-items: end; gap: 16px; padding: 28px 24px 12px; border-bottom: 1px solid var(--line); }
.kicker { margin: 0; color: var(--accent); letter-spacing: .12em; text-transform: uppercase; font-size: 11px; }
h1 { margin: 4px 0 0; font-size: 28px; font-weight: 650; }
.date-nav, .filter-label { color: var(--muted); font-size: 12px; display: flex; flex-direction: column; gap: 6px; }
#industry { min-width: 220px; }
select, input { background: var(--card); color: var(--text); border: 1px solid var(--line); border-radius: 8px; padding: 8px 10px; }
.banner { margin: 16px 24px; padding: 12px 14px; background: #18202a; border: 1px solid var(--line); border-radius: 10px; color: var(--muted); font-size: 13px; }
.metrics { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 10px; padding: 0 24px 16px; }
.metric { background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 12px 14px; }
.metric span { display: block; color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: .08em; }
.metric b { font-size: 22px; }
.downloads { display: flex; flex-wrap: wrap; gap: 8px; padding: 0 24px 16px; }
.downloads a { color: var(--bg); background: var(--accent); text-decoration: none; padding: 8px 12px; border-radius: 999px; font-size: 13px; font-weight: 600; }
.downloads a.zip { background: var(--bull); }
.toolbar { display: flex; flex-wrap: wrap; gap: 8px; padding: 0 24px 10px; }
.toolbar input { min-width: 220px; flex: 1; }
.tabs { display: flex; gap: 6px; padding: 0 24px; }
.tabs button { background: transparent; color: var(--muted); border: 1px solid var(--line); border-radius: 999px; padding: 7px 12px; cursor: pointer; }
.tabs button.on { color: var(--bg); background: var(--text); border-color: var(--text); }
.count { padding: 8px 24px; color: var(--muted); font-size: 13px; }
.table-wrap { padding: 0 24px 40px; overflow: auto; max-height: 70vh; }
table { width: 100%; border-collapse: collapse; font-variant-numeric: tabular-nums; }
th { position: sticky; top: 0; background: #151b21; text-align: left; font-size: 11px; letter-spacing: .06em; text-transform: uppercase; color: var(--muted); padding: 8px; border-bottom: 1px solid var(--line); }
td { padding: 7px 8px; border-bottom: 1px solid #232b33; }
tr:hover td { background: #182028; }
.bull { color: var(--bull); font-weight: 600; }
.bear { color: var(--bear); font-weight: 600; }
.narrow { color: var(--narrow); }
footer { padding: 12px 24px 32px; color: var(--muted); font-size: 12px; border-top: 1px solid var(--line); }
@media (max-width: 800px) {
  .metrics { grid-template-columns: repeat(2, 1fr); }
  .top { flex-direction: column; align-items: start; }
}
"""

JS = r"""
const DATA = window.CPR_DATA;
const COLS = ["SYMBOL","Industry","CLOSE","CPR_Width_Pct","CPR_Class","Bias","Price_Position","Segment","Pivot","BC","TC"];
let tab = "full";

function $(id) { return document.getElementById(id); }

function fillIndustry() {
  const sel = $("industry");
  if (!sel || sel.options.length > 1) return;
  (DATA.industries || []).forEach(name => {
    const opt = document.createElement("option");
    opt.value = name;
    opt.textContent = name;
    sel.appendChild(opt);
  });
}

function fillDates() {
  const sel = $("dateSelect");
  DATA.dates.forEach(d => {
    const opt = document.createElement("option");
    opt.value = d.id;
    opt.textContent = d.label;
    if (d.id === DATA.date) opt.selected = true;
    sel.appendChild(opt);
  });
  sel.addEventListener("change", () => {
    const id = sel.value;
    if (id === DATA.date) return;
    const latest = DATA.dates[0] && DATA.dates[0].id;
    if (id === latest) {
      window.location.href = DATA.home;
    } else {
      const prefix = DATA.home === "./" ? `archive/${id}/` : `../${id}/`;
      window.location.href = prefix;
    }
  });
}

function metrics() {
  const m = DATA.metrics;
  $("metrics").innerHTML = [
    ["EQ symbols", m.symbols],
    ["Narrow", m.narrow],
    ["Bullish CPR", m.bullish],
    ["Bearish CPR", m.bearish],
    ["F&O names", m.fo],
  ].map(([k,v]) => `<div class="metric"><span>${k}</span><b>${v}</b></div>`).join("");
}

function downloads() {
  const d = DATA.downloads;
  $("downloads").innerHTML = [
    ["Full CSV", d.full],
    ["Narrow", d.narrow],
    ["Bullish", d.bullish],
    ["Bearish", d.bearish],
    ["Top 20", d.top20],
    ["All ZIP", d.zip],
  ].map(([label, href], i) => `<a class="${i===5?"zip":""}" href="${href}" download>${label}</a>`).join("");
}

function fmt(col, val) {
  if (val === null || val === undefined) return "—";
  if (col === "CPR_Width_Pct") return Number(val).toFixed(4);
  if (["CLOSE","Pivot","BC","TC"].includes(col)) return Number(val).toFixed(2);
  return val;
}

function klass(col, val) {
  if (col === "Bias" && val === "Bullish") return "bull";
  if (col === "Bias" && val === "Bearish") return "bear";
  if (col === "Price_Position" && val === "Above CPR") return "bull";
  if (col === "Price_Position" && val === "Below CPR") return "bear";
  if (col === "CPR_Class" && val === "Narrow") return "narrow";
  return "";
}

function rows() {
  const q = $("search").value.trim().toUpperCase();
  const segment = $("segment").value;
  const industry = $("industry").value;
  const klassv = $("klass").value;
  const bias = $("bias").value;
  return (DATA.tables[tab] || []).filter(r => {
    if (q && !(String(r.SYMBOL || "").includes(q))) return false;
    if (segment !== "Any" && r.Segment !== segment) return false;
    if (industry !== "Any" && r.Industry !== industry) return false;
    if (klassv !== "Any" && r.CPR_Class !== klassv) return false;
    if (bias !== "Any" && r.Bias !== bias) return false;
    return true;
  });
}

function render() {
  const data = rows();
  $("count").textContent = `${data.length} rows`;
  $("head").innerHTML = "<tr>" + COLS.map(c => `<th>${c.replaceAll("_"," ")}</th>`).join("") + "</tr>";
  $("body").innerHTML = data.map(r =>
    "<tr>" + COLS.map(c => `<td class="${klass(c, r[c])}">${fmt(c, r[c])}</td>`).join("") + "</tr>"
  ).join("");
}

document.querySelectorAll(".tabs button").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tabs button").forEach(b => b.classList.remove("on"));
    btn.classList.add("on");
    tab = btn.dataset.tab;
    render();
  });
});
["search","segment","industry","klass","bias"].forEach(id => $(id).addEventListener("input", render));
fillDates();
fillIndustry();
metrics();
downloads();
render();
"""


def _write_assets(site_dir: Path) -> None:
    assets = site_dir / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    (assets / "style.css").write_text(CSS.strip() + "\n", encoding="utf-8")
    (assets / "app.js").write_text(JS.strip() + "\n", encoding="utf-8")
    (site_dir / ".nojekyll").write_text("", encoding="utf-8")


def _write_page(result: ScanResult, dest: Path, dates: List[str], home_href: str, asset_prefix: str) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    downloads = _write_downloads(result, dest / "downloads")
    payload = _payload(result, downloads, dates, home_href)
    (dest / "index.html").write_text(_page_html(payload, asset_prefix), encoding="utf-8")
    (dest / "manifest.json").write_text(json.dumps({"date": result.date, "metrics": payload["metrics"]}, indent=2), encoding="utf-8")


def build_site(output_dir: Path = Path("cpr_output"), site_dir: Path = SITE_DIR) -> List[str]:
    dates = discover_scan_dates(output_dir)
    if not dates:
        raise FileNotFoundError(f"No cpr_full_*.csv files in {output_dir}")

    if site_dir.exists():
        shutil.rmtree(site_dir)
    site_dir.mkdir(parents=True)
    _write_assets(site_dir)

    latest = dates[0]
    for date in dates:
        result = load_scan_result(date, output_dir=output_dir)
        if date == latest:
            _write_page(result, site_dir, dates, home_href="./", asset_prefix="./")
        archive_dir = site_dir / "archive" / date
        _write_page(result, archive_dir, dates, home_href="../../", asset_prefix="../../")

    archive_index = site_dir / "archive" / "index.html"
    links = "\n".join(
        f'<li><a href="{d}/">{_date_label(d)}</a></li>' for d in dates
    )
    archive_index.write_text(
        f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"/><title>Archive</title>
<link rel="stylesheet" href="../assets/style.css"/></head>
<body><header class="top"><div><p class="kicker">Archive</p><h1>Past sessions</h1></div>
<a href="../" style="color:var(--accent)">Latest</a></header>
<ul style="padding:24px;line-height:2">{links}</ul></body></html>
""",
        encoding="utf-8",
    )
    (site_dir / "archive.json").write_text(json.dumps(dates), encoding="utf-8")
    print(f"✓ Site: {site_dir.resolve()} ({len(dates)} session(s), latest {latest})")
    return dates


def serve(site_dir: Path, port: int) -> None:
    handler = SimpleHTTPRequestHandler
    httpd = ThreadingHTTPServer(("127.0.0.1", port), lambda *a, **k: handler(*a, directory=str(site_dir), **k))
    print(f"Preview: http://127.0.0.1:{port}")
    httpd.serve_forever()


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Build the EOD CPR static site")
    parser.add_argument("--output-dir", default="cpr_output")
    parser.add_argument("--site-dir", default="site")
    parser.add_argument("--serve", type=int, nargs="?", const=8504, help="Serve preview (default port 8504)")
    args = parser.parse_args(argv)
    build_site(Path(args.output_dir), Path(args.site_dir))
    if args.serve:
        serve(Path(args.site_dir), args.serve)


if __name__ == "__main__":
    main()
