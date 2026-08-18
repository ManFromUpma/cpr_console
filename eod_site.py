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
    attach_htf_to_result,
    discover_scan_dates,
    load_scan_result,
    web_frame,
)
from publication_contract import read_manifest

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
    "ATR14",
    "SMA50",
    "SMA100",
    "Next_Close",
}
TABLE_COLS = [
    "SYMBOL",
    "Industry",
    "CLOSE",
    "Pivot",
    "BC",
    "TC",
    "CPR_Width_Pct",
    "Width_Rank_Pct",
    "CPR_Class",
    "Own_Narrow",
    "Overlay",
    "Setup",
    "Bias",
    "Price_Position",
    "Segment",
    "Nifty500",
    "History_Days",
    "Value_60d",
    "ATR14",
    "Width_ATR",
    "Value_Ratio",
    "Above_SMA50",
    "Above_SMA100",
    "Regime",
    "Confluence_Score",
    "Signal_Direction",
    "Signal_Score",
    "Signal_Grade",
    "Signal_Explanation",
    "Strategy_Type",
    "Strategy_Setup",
    "Strategy_Confirmation",
    "Strategy_Explanation",
    "Applies",
    "Follow_Through",
    "Next_Close",
]


def _date_label(date: str) -> str:
    return datetime.strptime(date, "%Y%m%d").strftime("%d %b %Y")


def _records(df: pd.DataFrame) -> list:
    frame = web_frame(df)
    cols = [c for c in TABLE_COLS if c in frame.columns]
    out = []
    for rec_in in frame.loc[:, cols].to_dict(orient="records"):
        rec = {}
        for col in cols:
            val = rec_in.get(col)
            if pd.isna(val):
                rec[col] = None
            elif col in ROUND_2:
                rec[col] = round(float(val), 2)
            elif col == "CPR_Width_Pct":
                rec[col] = round(float(val), 4)
            elif col == "Width_Rank_Pct":
                rec[col] = round(float(val), 3)
            elif col == "Value_Ratio":
                rec[col] = round(float(val), 2)
            elif col in ("Bullish_CPR", "Bearish_CPR", "Own_Narrow", "History_OK", "Above_SMA50", "Above_SMA100", "Nifty500"):
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
        "best": ("cpr_best.csv", result.best),
        "watchlist": ("cpr_watchlist.csv", result.watchlist),
        "weekly": ("cpr_weekly.csv", result.weekly),
        "monthly": ("cpr_monthly.csv", result.monthly),
    }
    if not result.wide.empty:
        mapping["wide"] = ("cpr_wide.csv", result.wide)
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
                "Weekly CPR applies to the next week after the last completed Friday week.",
                "Monthly CPR applies to the next month after the last completed calendar month.",
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
        "best": "downloads/cpr_best.csv",
        "watchlist": "downloads/cpr_watchlist.csv",
        "weekly": "downloads/cpr_weekly.csv",
        "monthly": "downloads/cpr_monthly.csv",
        "wide": "downloads/cpr_wide.csv" if not result.wide.empty else None,
        "zip": f"downloads/{zip_name}",
    }


def _payload(result: ScanResult, downloads: dict, dates: Iterable[str], home_href: str, publication: Optional[dict] = None) -> dict:
    fo_n = int((result.full["Segment"] == "F&O + Cash").sum()) if "Segment" in result.full.columns else 0
    industries = []
    if "Industry" in result.full.columns:
        industries = sorted(result.full["Industry"].dropna().astype(str).unique().tolist())
    own_n = int(result.full["Own_Narrow"].sum()) if "Own_Narrow" in result.full.columns else 0
    setups = int(result.full["Setup"].isin(["Long", "Short", "Watch Long", "Watch Short", "Watch"]).sum()) if "Setup" in result.full.columns else 0
    w_setups = int(result.weekly["Setup"].isin(["Long", "Short", "Watch Long", "Watch Short", "Watch"]).sum()) if not result.weekly.empty and "Setup" in result.weekly.columns else 0
    m_setups = int(result.monthly["Setup"].isin(["Long", "Short", "Watch Long", "Watch Short", "Watch"]).sum()) if not result.monthly.empty and "Setup" in result.monthly.columns else 0
    regime = ""
    if "Regime" in result.full.columns:
        regimes = result.full["Regime"].dropna().astype(str)
        if not regimes.empty:
            regime = regimes.value_counts().idxmax()
    return {
        "date": result.date,
        "label": _date_label(result.date),
        "home": home_href,
        "dates": [{"id": d, "label": _date_label(d)} for d in dates],
        "industries": industries,
        "htf": {
            "weekly_applies": result.weekly_applies or "",
            "monthly_applies": result.monthly_applies or "",
            "weekly_setups": w_setups,
            "monthly_setups": m_setups,
        },
        "metrics": {
            "symbols": int(result.cash_rows),
            "narrow": int(len(result.narrow)),
            "own_narrow": own_n,
            "setups": setups,
            "bullish": int(len(result.bullish)),
            "fo": fo_n,
            "regime": regime,
        },
        "downloads": downloads,
        "publication": publication or {},
        "tables": {
            "full": _records(result.full),
            "narrow": _records(result.narrow),
            "bullish": _records(result.bullish),
            "bearish": _records(result.bearish),
            "top20": _records(result.top20),
            "best": _records(result.best) if not result.best.empty else [],
            "watchlist": _records(result.watchlist) if not result.watchlist.empty else [],
            "wide": _records(result.wide) if not result.wide.empty else [],
            "follow": _records(result.follow_through) if not result.follow_through.empty else [],
            "weekly": _records(result.weekly) if not result.weekly.empty else [],
            "monthly": _records(result.monthly) if not result.monthly.empty else [],
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
  <link rel="stylesheet" href="assets/style.css?v=6"/>
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
    Research only. Not investment advice. Daily levels apply to the <strong>next</strong> session.
    Weekly CPR applies to <strong>the next week</strong>. Monthly CPR applies to <strong>the next month</strong>
    after the last completed month — not the rest of the current month unless that month is finished.
    Not an NSE product.
  </section>
  <section class="data-status" id="dataStatus"></section>

  <section class="metrics" id="metrics"></section>

  <section class="downloads" id="downloads"></section>

  <section class="toolbar">
    <input id="search" type="search" placeholder="Search symbol…" autocomplete="off"/>
    <select id="segment"><option value="Any">Any segment</option><option>F&amp;O + Cash</option><option>Cash Only</option></select>
    <label class="filter-label">Industry
      <select id="industry">{industry_opts}</select>
    </label>
    <select id="klass"><option value="Any">Any CPR class</option><option>Narrow</option><option>Moderate</option><option>Wide</option></select>
    <select id="bias"><option value="Any">Any bias</option><option>Bullish</option><option>Bearish</option><option>Neutral</option></select>
    <select id="overlay"><option value="Any">Any overlay</option><option>Higher</option><option>Lower</option><option>Inside</option><option>Outside</option><option>Overlapping</option></select>
    <select id="setup"><option value="Any">Any setup</option><option>Long</option><option>Short</option><option>Watch Long</option><option>Watch Short</option><option>Watch</option><option>No setup</option></select>
    <select id="ownNarrow"><option value="Any">Own-narrow: any</option><option value="Yes">Own-narrow</option><option value="No">Not own-narrow</option></select>
    <label class="filter-check"><input id="niftyOnly" type="checkbox"/> Nifty 500</label>
    <label class="filter-check"><input id="hideUnclassified" type="checkbox"/> Hide Unclassified</label>
  </section>
  <p class="count" style="padding-top:0">
    CPR class is the band as % of close: Narrow ≤ 0.25%, Moderate 0.25–0.75%, Wide &gt; 0.75%.
    Own-narrow is that stock versus its own history (60 days, ~12 weeks, or completed months).
    Setups require a ≥ 0.2% close beyond the band plus a Higher/Lower overlay, and Long / Short are
    paused in a Risk-Off / Risk-On NIFTY regime. Daily Pivot / BC / TC are tomorrow’s levels.
    Use the Weekly / Monthly tabs to hold longer.
  </p>

  <nav class="tabs" id="tabs">
    <button data-tab="best" class="on">Best today</button>
    <button data-tab="full">Full</button>
    <button data-tab="narrow">Narrow</button>
    <button data-tab="bullish">Bullish</button>
    <button data-tab="bearish">Bearish</button>
    <button data-tab="top20">Top 20</button>
    <button data-tab="watchlist">Watchlist</button>
    <button data-tab="wide">Wide CPR</button>
    <button data-tab="follow">Follow-through</button>
    <button data-tab="weekly">Weekly</button>
    <button data-tab="monthly">Monthly</button>
  </nav>

  <p class="count" id="count"></p>
  <div class="table-wrap">
    <table>
      <thead id="head"></thead>
      <tbody id="body"></tbody>
    </table>
  </div>

  <div id="drawerBackdrop" class="drawer-backdrop" hidden></div>
  <aside id="symbolDrawer" class="symbol-drawer" hidden aria-labelledby="drawerTitle" aria-modal="true" role="dialog">
    <div class="drawer-head">
      <div>
        <p class="kicker">Symbol context</p>
        <h2 id="drawerTitle">Symbol</h2>
        <p id="drawerSubtitle" class="drawer-subtitle"></p>
      </div>
      <button id="drawerClose" class="drawer-close" type="button" aria-label="Close symbol context">Close</button>
    </div>
    <div id="drawerBody"></div>
  </aside>

  <footer>
    Equity stocks only (ETFs, AMCs, mutual funds excluded). Industry from Nifty 500.
    Built from NSE UDI cash + F&amp;O bhavcopy plus ~252 prior cash sessions.
    CPR = Pivot (H+L+C)/3, BC (H+L)/2, TC 2P−BC.
    Absolute Narrow ≤ 0.25%. Own_Narrow = bottom 25% of that name’s last 60 widths.
    Overlay = today’s CPR vs prior session. Setup = Own_Narrow + side + overlay +
    a ≥ 0.2% close past the band; Long/Short pause when NIFTY regime opposes.
    Watch Long / Watch Short = Own_Narrow + inside the band + bias.
    Confluence_Score = Daily (Long +2 / Watch Long +1) + Weekly + Monthly signal (−6 … +6).
    Weekly / Monthly tabs use the same formulas on completed week and month bars.
    Top 20 ranks liquid setups (median VALUE ≥ ₹2 cr) by confluence then width percentile.
    Follow-through compares each setup’s prior-day CPR band to this session’s close.
    Wide CPR adds separate consolidation and range-breakout states; it does not replace the existing Narrow CPR setup labels.
  </footer>
  <script>window.CPR_DATA = {data};</script>
  <script src="assets/app.js?v=6"></script>
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
[hidden] { display: none !important; }
html, body { margin: 0; background: var(--bg); color: var(--text); font: 15px/1.45 "IBM Plex Sans", "Segoe UI", sans-serif; }
body.drawer-open { overflow: hidden; }
.top { display: flex; justify-content: space-between; align-items: end; gap: 16px; padding: 28px 24px 12px; border-bottom: 1px solid var(--line); }
.kicker { margin: 0; color: var(--accent); letter-spacing: .12em; text-transform: uppercase; font-size: 11px; }
h1 { margin: 4px 0 0; font-size: 28px; font-weight: 650; }
.date-nav, .filter-label { color: var(--muted); font-size: 12px; display: flex; flex-direction: column; gap: 6px; }
.filter-check { color: var(--muted); font-size: 12px; display: flex; align-items: center; gap: 6px; padding: 8px 2px; }
#industry { min-width: 220px; }
select, input { background: var(--card); color: var(--text); border: 1px solid var(--line); border-radius: 8px; padding: 8px 10px; }
.banner { margin: 16px 24px; padding: 12px 14px; background: #18202a; border: 1px solid var(--line); border-radius: 10px; color: var(--muted); font-size: 13px; }
.data-status { margin: 0 24px 16px; padding: 10px 14px; border: 1px solid var(--line); border-radius: 10px; color: var(--muted); font-size: 13px; }
.metrics { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 10px; padding: 0 24px 16px; }
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
th { position: sticky; top: 0; background: #151b21; text-align: left; font-size: 11px; letter-spacing: .06em; text-transform: uppercase; color: var(--muted); padding: 8px; border-bottom: 1px solid var(--line); cursor: pointer; }
th.sorted { color: var(--text); }
th.sorted.asc { box-shadow: inset 0 -2px 0 var(--accent); }
th.sorted.desc { box-shadow: inset 0 2px 0 var(--accent); }
td { padding: 7px 8px; border-bottom: 1px solid #232b33; }
tr[data-symbol] { cursor: pointer; }
tr[data-symbol]:focus-visible td { outline: 2px solid var(--accent); outline-offset: -2px; }
tr:hover td { background: #182028; }
.bull { color: var(--bull); font-weight: 600; }
.bear { color: var(--bear); font-weight: 600; }
.narrow { color: var(--narrow); }
footer { padding: 12px 24px 32px; color: var(--muted); font-size: 12px; border-top: 1px solid var(--line); }
.drawer-backdrop { position: fixed; inset: 0; z-index: 20; background: rgba(4, 7, 10, .68); }
.symbol-drawer { position: fixed; z-index: 21; top: 0; right: 0; width: min(500px, 100vw); height: 100vh; overflow-y: auto; padding: 24px; background: #151b21; border-left: 1px solid var(--line); box-shadow: -18px 0 48px rgba(0, 0, 0, .34); }
.drawer-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; padding-bottom: 18px; border-bottom: 1px solid var(--line); }
.drawer-head h2 { margin: 3px 0 0; font-size: 28px; }
.drawer-subtitle { margin: 4px 0 0; color: var(--muted); }
.drawer-close { flex: 0 0 auto; background: transparent; color: var(--text); border: 1px solid var(--line); border-radius: 8px; padding: 7px 10px; cursor: pointer; }
.drawer-close:hover, .drawer-close:focus-visible { border-color: var(--accent); color: var(--accent); }
.drawer-section { padding: 18px 0; border-bottom: 1px solid var(--line); }
.drawer-section h3 { margin: 0 0 10px; font-size: 12px; color: var(--muted); letter-spacing: .08em; text-transform: uppercase; }
.drawer-summary { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.detail-item { background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: 10px 12px; }
.detail-item span { display: block; color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: .06em; }
.detail-item strong { display: block; margin-top: 3px; font-size: 16px; }
.detail-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
.badge { display: inline-flex; align-items: center; width: fit-content; border: 1px solid currentColor; border-radius: 999px; padding: 2px 8px; font-size: 11px; font-weight: 700; line-height: 1.35; }
.badge.confirmed { color: var(--bull); background: rgba(62, 207, 142, .1); }
.badge.watch { color: var(--narrow); background: rgba(201, 167, 255, .1); }
.badge.unavailable { color: var(--bear); background: rgba(239, 107, 107, .1); }
.badge.neutral { color: var(--muted); background: rgba(147, 160, 173, .08); }
.cpr-chart { width: 100%; min-height: 180px; margin: 4px 0 0; padding: 8px 0; background: #11171c; border: 1px solid var(--line); border-radius: 10px; }
.cpr-chart svg { display: block; width: 100%; height: auto; }
.cpr-chart .band { fill: rgba(142, 192, 245, .24); stroke: var(--accent); stroke-width: 1; }
.cpr-chart .price-line { stroke: var(--bull); stroke-width: 2; }
.cpr-chart .price-dot { fill: var(--bull); }
.cpr-chart .level-line { stroke: #667482; stroke-width: 1; stroke-dasharray: 4 4; }
.cpr-chart text { fill: var(--muted); font: 11px "IBM Plex Sans", "Segoe UI", sans-serif; }
.drawer-explanation { margin: 0; color: var(--muted); }
@media (max-width: 800px) {
  .metrics { grid-template-columns: repeat(2, 1fr); }
  .top { flex-direction: column; align-items: start; }
  .symbol-drawer { width: 100vw; padding: 18px; }
}
"""

JS = r"""
const DATA = window.CPR_DATA;
const COLS = ["SYMBOL","Industry","CLOSE","Pivot","BC","TC","CPR_Width_Pct","Width_Rank_Pct","CPR_Class","Own_Narrow","Overlay","Setup","Bias","Price_Position","Segment","History_Days","Value_60d","ATR14","Width_ATR","Value_Ratio","Above_SMA50","Above_SMA100","Regime","Confluence_Score","Signal_Direction","Signal_Score","Signal_Grade","Signal_Explanation","Strategy_Type","Strategy_Setup","Strategy_Confirmation","Strategy_Explanation","Applies"];
const FOLLOW_COLS = ["SYMBOL","Industry","Setup","CPR_Width_Pct","Width_Rank_Pct","Segment","Next_Close","Follow_Through"];
let tab = "best";
let sort = {col: null, asc: true};
let drawerTrigger = null;

function $(id) { return document.getElementById(id); }

function esc(value) {
  return String(value ?? "—").replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch]));
}

function finite(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function badgeClass(value) {
  if (value === "Confirmed") return "confirmed";
  if (value === "Watch") return "watch";
  if (value === "Unavailable") return "unavailable";
  return "neutral";
}

function badgeHtml(value) {
  const label = value === null || value === undefined || value === "" ? "—" : value;
  return `<span class="badge ${badgeClass(label)}">${esc(label)}</span>`;
}

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
    ["Own narrow", m.own_narrow ?? "—"],
    ["Setups", m.setups ?? "—"],
    ["Bullish CPR", m.bullish],
    ["F&O names", m.fo],
    ["NIFTY regime", m.regime || "—"],
  ].map(([k,v]) => `<div class="metric"><span>${k}</span><b>${v}</b></div>`).join("");
}

function publicationStatus() {
  const p = DATA.publication || {};
  const freshness = p.freshness || {};
  const source = p.source || {};
  const actual = p.actual_data_date || "unknown";
  const el = $("dataStatus");
  if (!el) return;
  el.textContent = `${freshness.display || "Publication freshness unknown"} · data session ${actual} · source ${source.name || "unknown"}`;
  if (freshness.status !== "known") el.style.borderColor = "var(--bear)";
}

function downloads() {
  const d = DATA.downloads;
  $("downloads").innerHTML = [
    ["Full CSV", d.full],
    ["Best today", d.best],
    ["Watchlist", d.watchlist],
    ["Wide CPR", d.wide],
    ["Narrow", d.narrow],
    ["Bullish", d.bullish],
    ["Bearish", d.bearish],
    ["Top 20", d.top20],
    ["Weekly", d.weekly],
    ["Monthly", d.monthly],
    ["All ZIP", d.zip],
  ].map(([label, href]) => href ? `<a class="${label==="All ZIP"?"zip":""}" href="${href}" download>${label}</a>` : "").join("");
}

function fmt(col, val) {
  if (val === null || val === undefined) return "—";
  if (col === "CPR_Width_Pct") return Number(val).toFixed(4);
  if (col === "Width_Rank_Pct" || col === "Confluence_Score" || col === "Signal_Score") return Number(val).toFixed(2);
  if (col === "Value_Ratio") return Number(val).toFixed(2);
  if (["CLOSE","Pivot","BC","TC","Value_60d","ATR14","Width_ATR","Next_Close"].includes(col)) return Number(val).toFixed(2);
  if (["Own_Narrow","Nifty500","Above_SMA50","Above_SMA100","History_OK"].includes(col)) return val ? "Yes" : "No";
  return val;
}

function cellHtml(col, val) {
  const rendered = fmt(col, val);
  return col === "Strategy_Confirmation" ? badgeHtml(rendered) : esc(rendered);
}

function klass(col, val) {
  if (col === "Bias" && val === "Bullish") return "bull";
  if (col === "Bias" && val === "Bearish") return "bear";
  if (col === "Price_Position" && val === "Above CPR") return "bull";
  if (col === "Price_Position" && val === "Below CPR") return "bear";
  if (col === "CPR_Class" && val === "Narrow") return "narrow";
  if (col === "Overlay" && val === "Higher") return "bull";
  if (col === "Overlay" && val === "Lower") return "bear";
  if (col === "Setup" && (val === "Long" || val === "Watch Long")) return "bull";
  if (col === "Setup" && (val === "Short" || val === "Watch Short")) return "bear";
  if (col === "Setup" && val === "Watch") return "narrow";
  if (col === "Signal_Score" && Number(val) >= 65) return "bull";
  if (col === "Signal_Score" && Number(val) < 50) return "bear";
  if (col === "Strategy_Confirmation" && val === "Confirmed") return "bull";
  if (col === "Strategy_Confirmation" && val === "Watch") return "narrow";
  if (col === "Strategy_Confirmation" && val === "Unavailable") return "bear";
  if (col === "Own_Narrow" && val === true) return "narrow";
  if (col === "Follow_Through" && val === "Followed") return "bull";
  if (col === "Follow_Through" && val === "Failed") return "bear";
  return "";
}

function parseFilters() {
  try {
    const q = new URLSearchParams(window.location.hash.slice(1));
    const t = q.get("tab");
    if (t && document.querySelector(`.tabs button[data-tab="${t}"]`)) {
      document.querySelectorAll(".tabs button").forEach(b => b.classList.remove("on"));
      document.querySelector(`.tabs button[data-tab="${t}"]`).classList.add("on");
      tab = t;
    }
    const sel = (id, name) => { const v = q.get(name); if (v) $(id).value = v; };
    sel("search","q"); sel("segment","seg"); sel("industry","ind");
    sel("klass","cls"); sel("bias","bias"); sel("overlay","ovl");
    sel("setup","setup"); sel("ownNarrow","nn");
    if (q.get("nifty") === "1") $("niftyOnly").checked = true;
    if (q.get("hide") === "1") $("hideUnclassified").checked = true;
  } catch (e) {}
}

function rows() {
  const q = $("search").value.trim().toUpperCase();
  const segment = $("segment").value;
  const industry = $("industry").value;
  const klassv = $("klass").value;
  const bias = $("bias").value;
  const overlay = $("overlay").value;
  const setup = $("setup").value;
  const ownNarrow = $("ownNarrow").value;
  const niftyOnly = $("niftyOnly").checked;
  const hideUncl = $("hideUnclassified").checked;
  return (DATA.tables[tab] || []).filter(r => {
    if (q && !(String(r.SYMBOL || "").toUpperCase().includes(q))) return false;
    if (segment !== "Any" && r.Segment !== segment) return false;
    if (industry !== "Any" && r.Industry !== industry) return false;
    if (klassv !== "Any" && r.CPR_Class !== klassv) return false;
    if (bias !== "Any" && r.Bias !== bias) return false;
    if (overlay !== "Any" && r.Overlay !== overlay) return false;
    if (setup !== "Any" && r.Setup !== setup) return false;
    if (ownNarrow === "Yes" && !r.Own_Narrow) return false;
    if (ownNarrow === "No" && r.Own_Narrow) return false;
    if (niftyOnly && r.Nifty500 !== true) return false;
    if (hideUncl && r.Industry === "Unclassified") return false;
    return true;
  });
}

function sortRows(data) {
  if (!sort.col) return data;
  const col = sort.col;
  const dir = sort.asc ? 1 : -1;
  return data.slice().sort((a, b) => {
    const va = a[col], vb = b[col];
    if (va == null) return 1;
    if (vb == null) return -1;
    if (typeof va === "number" && typeof vb === "number") return (va - vb) * dir;
    return String(va).localeCompare(String(vb)) * dir;
  });
}

function cprMiniChart(row) {
  const pivot = finite(row.Pivot), bc = finite(row.BC), tc = finite(row.TC), close = finite(row.CLOSE);
  const levels = [pivot, bc, tc, close].filter(value => value !== null);
  if (!levels.length) return `<div class="drawer-explanation">CPR levels unavailable for this row.</div>`;
  const min = Math.min(...levels), max = Math.max(...levels);
  const span = Math.max(max - min, Math.abs(max) * 0.0025, 0.01);
  const low = min - span * 0.35, high = max + span * 0.35;
  const y = value => 148 - ((value - low) / (high - low)) * 112;
  const bandLow = bc === null || tc === null ? null : Math.min(bc, tc);
  const bandHigh = bc === null || tc === null ? null : Math.max(bc, tc);
  const bandTop = bandHigh === null ? 0 : y(bandHigh);
  const bandHeight = bandLow === null ? 0 : Math.max(2, y(bandLow) - bandTop);
  const marks = [];
  if (bandLow !== null) marks.push(`<rect class="band" x="38" y="${bandTop.toFixed(1)}" width="344" height="${bandHeight.toFixed(1)}" rx="4"/>`);
  if (pivot !== null) marks.push(`<line class="level-line" x1="38" x2="382" y1="${y(pivot).toFixed(1)}" y2="${y(pivot).toFixed(1)}"/>`);
  if (close !== null) marks.push(`<line class="price-line" x1="38" x2="382" y1="${y(close).toFixed(1)}" y2="${y(close).toFixed(1)}"/><circle class="price-dot" cx="382" cy="${y(close).toFixed(1)}" r="4"/>`);
  const label = value => value === null ? "—" : Number(value).toFixed(2);
  return `<div class="cpr-chart" role="img" aria-label="CPR band mini chart for ${esc(row.SYMBOL)}">
    <svg viewBox="0 0 420 180" preserveAspectRatio="none">
      ${marks.join("")}
      <text x="6" y="${Math.min(170, Math.max(18, (bandTop || 18) + 4)).toFixed(1)}">CPR</text>
      <text x="38" y="172">BC ${esc(label(bc))}</text>
      <text x="170" y="172">Pivot ${esc(label(pivot))}</text>
      <text x="300" y="172">Close ${esc(label(close))}</text>
    </svg>
  </div>`;
}

function detailItem(label, value) {
  return `<div class="detail-item"><span>${esc(label)}</span><strong>${esc(value === null || value === undefined || value === "" ? "—" : value)}</strong></div>`;
}

function openDrawer(row, trigger) {
  drawerTrigger = trigger || null;
  $("drawerTitle").textContent = row.SYMBOL || "Symbol";
  $("drawerSubtitle").textContent = [row.Strategy_Setup, row.CPR_Class, row.Price_Position].filter(Boolean).join(" · ");
  const confirmation = row.Strategy_Confirmation;
  $("drawerBody").innerHTML = `
    <section class="drawer-section drawer-summary">
      <div class="detail-item"><span>Confirmation</span><strong>${badgeHtml(confirmation)}</strong></div>
      <div class="detail-item"><span>Signal grade</span><strong>${badgeHtml(row.Signal_Grade || row.Signal_Direction)}</strong></div>
    </section>
    <section class="drawer-section">
      <h3>Next-session CPR band</h3>
      ${cprMiniChart(row)}
    </section>
    <section class="drawer-section">
      <h3>Context</h3>
      <div class="detail-grid">
        ${detailItem("Close", fmt("CLOSE", row.CLOSE))}
        ${detailItem("CPR width %", fmt("CPR_Width_Pct", row.CPR_Width_Pct))}
        ${detailItem("Price position", row.Price_Position)}
        ${detailItem("Overlay", row.Overlay)}
        ${detailItem("Value ratio", fmt("Value_Ratio", row.Value_Ratio))}
        ${detailItem("Trend", `${row.Above_SMA50 === true ? "Above" : row.Above_SMA50 === false ? "Below" : "—"} SMA50 · ${row.Above_SMA100 === true ? "Above" : row.Above_SMA100 === false ? "Below" : "—"} SMA100`)}
      </div>
    </section>
    <section class="drawer-section">
      <h3>Explanation</h3>
      <p class="drawer-explanation">${esc(row.Strategy_Explanation || row.Signal_Explanation || "No explanation available.")}</p>
    </section>`;
  $("drawerBackdrop").hidden = false;
  $("symbolDrawer").hidden = false;
  document.body.classList.add("drawer-open");
  $("drawerClose").focus();
}

function closeDrawer() {
  $("drawerBackdrop").hidden = true;
  $("symbolDrawer").hidden = true;
  document.body.classList.remove("drawer-open");
  if (drawerTrigger) drawerTrigger.focus();
  drawerTrigger = null;
}

function render() {
  const data = sortRows(rows());
  const htf = DATA.htf || {};
  let extra = "";
  if (tab === "weekly" && htf.weekly_applies) extra = ` · applies to ${htf.weekly_applies}`;
  if (tab === "monthly" && htf.monthly_applies) extra = ` · applies to ${htf.monthly_applies}`;
  if (tab === "follow") extra = " · prior-day setups vs this session's close";
  if (tab === "watchlist") extra = " · every setup with levels to trade next session";
  if (tab === "best") extra = " · Daily Long/Short ranked by confluence, liquid, F&O first";
  $("count").textContent = `${data.length} rows${extra}`;
  const cols = tab === "follow" ? FOLLOW_COLS : COLS;
  $("head").innerHTML = "<tr>" + cols.map(c =>
    `<th data-col="${c}" class="${sort.col===c?(sort.asc?'sorted asc':'sorted desc'):''}">${c.replaceAll("_"," ")}${sort.col===c?(sort.asc?' ▲':' ▼'):''}</th>`
  ).join("") + "</tr>";
  $("body").innerHTML = data.map((r, index) =>
    `<tr tabindex="0" data-symbol="${esc(r.SYMBOL)}" data-index="${index}" title="Open symbol context">` + cols.map(c => `<td class="${klass(c, r[c])}">${cellHtml(c, r[c])}</td>`).join("") + "</tr>"
  ).join("");
  document.querySelectorAll("#body tr[data-index]").forEach(tr => {
    const open = () => openDrawer(data[Number(tr.dataset.index)], tr);
    tr.addEventListener("click", open);
    tr.addEventListener("keydown", event => {
      if (event.key === "Enter" || event.key === " ") { event.preventDefault(); open(); }
    });
  });
  document.querySelectorAll("th").forEach(th => th.addEventListener("click", () => {
    const col = th.dataset.col;
    if (sort.col === col) sort.asc = !sort.asc; else { sort.col = col; sort.asc = true; }
    render();
  }));
  syncUrl();
}

function syncUrl() {
  const p = new URLSearchParams();
  if (tab !== "best") p.set("tab", tab);
  if ($("search").value) p.set("q", $("search").value);
  if ($("segment").value !== "Any") p.set("seg", $("segment").value);
  if ($("industry").value !== "Any") p.set("ind", $("industry").value);
  if ($("klass").value !== "Any") p.set("cls", $("klass").value);
  if ($("bias").value !== "Any") p.set("bias", $("bias").value);
  if ($("overlay").value !== "Any") p.set("ovl", $("overlay").value);
  if ($("setup").value !== "Any") p.set("setup", $("setup").value);
  if ($("ownNarrow").value !== "Any") p.set("nn", $("ownNarrow").value);
  if ($("niftyOnly").checked) p.set("nifty", "1");
  if ($("hideUnclassified").checked) p.set("hide", "1");
  const h = p.toString();
  if (window.location.hash !== "#" + h) {
    history.replaceState(null, "", "#" + h);
  }
}

$("drawerClose").addEventListener("click", closeDrawer);
$("drawerBackdrop").addEventListener("click", closeDrawer);
document.addEventListener("keydown", event => { if (event.key === "Escape" && !$("symbolDrawer").hidden) closeDrawer(); });
document.querySelectorAll(".tabs button").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tabs button").forEach(b => b.classList.remove("on"));
    btn.classList.add("on");
    tab = btn.dataset.tab;
    render();
  });
});
["search","segment","industry","klass","bias","overlay","setup","ownNarrow"].forEach(id => {
  const el = $(id);
  if (el) el.addEventListener("input", render);
});
["niftyOnly","hideUnclassified"].forEach(id => {
  const el = $(id);
  if (el) el.addEventListener("change", render);
});
parseFilters();
fillDates();
fillIndustry();
metrics();
publicationStatus();
downloads();
render();
"""


def _write_assets(site_dir: Path) -> None:
    assets = site_dir / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    (assets / "style.css").write_text(CSS.strip() + "\n", encoding="utf-8")
    (assets / "app.js").write_text(JS.strip() + "\n", encoding="utf-8")
    (site_dir / ".nojekyll").write_text("", encoding="utf-8")


def _write_page(result: ScanResult, dest: Path, dates: List[str], home_href: str, asset_prefix: str, publication: Optional[dict] = None) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    downloads = _write_downloads(result, dest / "downloads")
    payload = _payload(result, downloads, dates, home_href, publication=publication)
    (dest / "index.html").write_text(_page_html(payload, asset_prefix), encoding="utf-8")
    (dest / "manifest.json").write_text(json.dumps({"date": result.date, "metrics": payload["metrics"]}, indent=2), encoding="utf-8")


def build_site(output_dir: Path = Path("cpr_output"), site_dir: Path = SITE_DIR) -> List[str]:
    dates = discover_scan_dates(output_dir)
    if not dates:
        raise FileNotFoundError(f"No cpr_full_*.csv files in {output_dir}")

    publication = read_manifest(output_dir) or {}

    if site_dir.exists():
        shutil.rmtree(site_dir)
    site_dir.mkdir(parents=True)
    _write_assets(site_dir)

    latest = dates[0]
    for i, date in enumerate(dates):
        prev = dates[i + 1] if i + 1 < len(dates) else None
        result = load_scan_result(date, output_dir=output_dir, previous=prev)
        if date == latest and result.weekly.empty:
            result = attach_htf_to_result(result, output_dir=output_dir, write_csv=True)
        if date == latest:
            _write_page(result, site_dir, dates, home_href="./", asset_prefix="./", publication=publication)
        archive_dir = site_dir / "archive" / date
        _write_page(result, archive_dir, dates, home_href="../../", asset_prefix="../../", publication=publication)

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
    (site_dir / "publication_manifest.json").write_text(
        json.dumps(publication, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
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
