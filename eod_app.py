"""
NSE EOD CPR Scanner — standalone Streamlit app.

Separate from the Shah CPR console (`app.py` on port 8501) and the
CPR Breakout Screener (`breakout_app.py` on port 8502).

Run with: streamlit run eod_app.py --server.port 8503
"""

from __future__ import annotations

import io
from datetime import datetime, timedelta

import pandas as pd
import pytz
import streamlit as st

from nse_cpr_scanner import DISPLAY_COLS, HISTORY_LOOKBACK, scan_eod_cpr

IST = pytz.timezone("Asia/Kolkata")


st.set_page_config(
    page_title="NSE EOD CPR Scanner",
    page_icon="📥",
    layout="wide",
    initial_sidebar_state="expanded",
)

if "eod_scan" not in st.session_state:
    st.session_state.eod_scan = None
if "eod_error" not in st.session_state:
    st.session_state.eod_error = None


def last_weekday(today=None):
    today = today or datetime.now(IST).date()
    d = today - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def color_bias(val: str) -> str:
    if val == "Bullish":
        return "color: #2e7d32; font-weight: 600"
    if val == "Bearish":
        return "color: #c62828; font-weight: 600"
    return ""


def color_class(val: str) -> str:
    if val == "Narrow":
        return "color: #6a1b9a; font-weight: 600"
    if val == "Wide":
        return "color: #ef6c00"
    return ""


def color_segment(val: str) -> str:
    if val == "F&O + Cash":
        return "color: #6a1b9a"
    if val == "Cash Only":
        return "color: #1565c0"
    return ""


def color_position(val: str) -> str:
    if val == "Above CPR":
        return "color: #2e7d32"
    if val == "Below CPR":
        return "color: #c62828"
    return ""


def color_overlay(val: str) -> str:
    if val == "Higher":
        return "color: #2e7d32; font-weight: 600"
    if val == "Lower":
        return "color: #c62828; font-weight: 600"
    return ""


def color_setup(val: str) -> str:
    if val == "Long":
        return "color: #2e7d32; font-weight: 600"
    if val == "Short":
        return "color: #c62828; font-weight: 600"
    if val == "Watch":
        return "color: #6a1b9a; font-weight: 600"
    return ""


def style_table(df: pd.DataFrame):
    styled = df.style
    if "Bias" in df.columns:
        styled = styled.map(color_bias, subset=["Bias"])
    if "CPR_Class" in df.columns:
        styled = styled.map(color_class, subset=["CPR_Class"])
    if "Segment" in df.columns:
        styled = styled.map(color_segment, subset=["Segment"])
    if "Price_Position" in df.columns:
        styled = styled.map(color_position, subset=["Price_Position"])
    if "Overlay" in df.columns:
        styled = styled.map(color_overlay, subset=["Overlay"])
    if "Setup" in df.columns:
        styled = styled.map(color_setup, subset=["Setup"])
    return styled


def format_view(df: pd.DataFrame) -> pd.DataFrame:
    show = df.copy()
    money = ["CLOSE", "Pivot", "BC", "TC", "CPR_Bottom", "CPR_Top", "CPR_Width"]
    for col in money:
        if col in show.columns:
            show[col] = show[col].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "—")
    if "CPR_Width_Pct" in show.columns:
        show["CPR_Width_Pct"] = show["CPR_Width_Pct"].apply(lambda x: f"{x:.4f}" if pd.notna(x) else "—")
    if "Width_Rank_Pct" in show.columns:
        show["Width_Rank_Pct"] = show["Width_Rank_Pct"].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "—")
    cols = [c for c in DISPLAY_COLS if c in show.columns]
    extra = [c for c in show.columns if c not in cols]
    return show[cols + extra]


def csv_bytes(df: pd.DataFrame) -> bytes:
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")


with st.sidebar:
    st.header("📥 EOD config")
    st.caption("Independent of the CPR console (8501) and breakout screener (8502).")

    scan_date = st.date_input(
        "Bhavcopy date",
        value=last_weekday(),
        max_value=datetime.now(IST).date(),
        help="NSE cash + F&O UDI bhavcopy. Use the last completed session.",
    )
    date_str = scan_date.strftime("%Y%m%d")
    lookback = st.number_input(
        "History lookback (sessions)",
        min_value=0,
        max_value=120,
        value=HISTORY_LOOKBACK,
        help="Cash bhavcopies cached under cpr_output/bhavcopy for overlay and own-width rank.",
    )

    segment_filter = st.selectbox("Segment", ["Any", "F&O + Cash", "Cash Only"], index=0)
    industries = ["Any"]
    if st.session_state.eod_scan is not None and "Industry" in st.session_state.eod_scan.full.columns:
        industries += sorted(
            st.session_state.eod_scan.full["Industry"].dropna().astype(str).unique().tolist()
        )
    industry_filter = st.selectbox("Industry", industries, index=0)
    class_filter = st.selectbox("CPR class", ["Any", "Narrow", "Moderate", "Wide"], index=0)
    bias_filter = st.selectbox("Bias", ["Any", "Bullish", "Bearish", "Neutral"], index=0)
    position_filter = st.selectbox(
        "Price position",
        ["Any", "Above CPR", "Inside CPR", "Below CPR"],
        index=0,
    )
    overlay_filter = st.selectbox(
        "Overlay vs prior CPR",
        ["Any", "Higher", "Lower", "Inside", "Outside", "Overlapping", "Unknown"],
        index=0,
    )
    setup_filter = st.selectbox("Setup", ["Any", "Long", "Short", "Watch", "No setup"], index=0)
    own_narrow_filter = st.selectbox("Own-history narrow", ["Any", "Yes", "No"], index=0)

    st.caption("Absolute Narrow ≤ 0.25% · Own_Narrow = bottom 25% of that name’s last 60 sessions")


st.title("📥 NSE EOD CPR Scanner")
st.markdown(
    """
**Separate from the Shah CPR console (port 8501) and the breakout screener (port 8502).**
Downloads NSE **cash + F&O bhavcopies**, caches ~60 prior cash sessions,
computes CPR from that session's H/L/C, ranks width vs each name's own history,
and tags overlay / Setup for the **next** session. *Research only. Not investment advice.*
"""
)

col_a, col_b = st.columns([1, 3])
with col_a:
    run_scan = st.button("🔍 Scan bhavcopy", type="primary", use_container_width=True)
with col_b:
    st.caption(f"NSE archives · listed equity only (no ETF/AMC/MF) · {lookback}d history · date {date_str}")

if run_scan:
    with st.spinner(f"Downloading NSE bhavcopies and {lookback}-session history for {date_str}…"):
        try:
            st.session_state.eod_scan = scan_eod_cpr(date_str, lookback=int(lookback))
            st.session_state.eod_error = None
        except Exception as exc:
            st.session_state.eod_scan = None
            st.session_state.eod_error = str(exc)

if st.session_state.eod_error:
    st.error(st.session_state.eod_error)

result = st.session_state.eod_scan
if result is None:
    st.info("Pick a session date and click **Scan bhavcopy**. Typical choice is the last trading day.")
    st.stop()

m1, m2, m3, m4, m5, m6 = st.columns(6)
m1.metric("EQ symbols", result.cash_rows)
m2.metric("Narrow", len(result.narrow))
m3.metric("Own narrow", int(result.full["Own_Narrow"].sum()) if "Own_Narrow" in result.full.columns else "—")
m4.metric("Setups", int(result.full["Setup"].isin(["Long", "Short", "Watch"]).sum()) if "Setup" in result.full.columns else "—")
m5.metric("Bullish CPR", len(result.bullish))
m6.metric("F&O tagged", "Yes" if result.fo_available else "No")
st.caption(f"Session {result.date} · files in `{result.output_dir}`")


def apply_filters(df: pd.DataFrame) -> pd.DataFrame:
    view = df.copy()
    if segment_filter != "Any" and "Segment" in view.columns:
        view = view[view["Segment"] == segment_filter]
    if industry_filter != "Any" and "Industry" in view.columns:
        view = view[view["Industry"] == industry_filter]
    if class_filter != "Any" and "CPR_Class" in view.columns:
        view = view[view["CPR_Class"] == class_filter]
    if bias_filter != "Any" and "Bias" in view.columns:
        view = view[view["Bias"] == bias_filter]
    if position_filter != "Any" and "Price_Position" in view.columns:
        view = view[view["Price_Position"] == position_filter]
    if overlay_filter != "Any" and "Overlay" in view.columns:
        view = view[view["Overlay"] == overlay_filter]
    if setup_filter != "Any" and "Setup" in view.columns:
        view = view[view["Setup"] == setup_filter]
    if own_narrow_filter != "Any" and "Own_Narrow" in view.columns:
        want = own_narrow_filter == "Yes"
        view = view[view["Own_Narrow"].astype(bool) == want]
    return view.reset_index(drop=True)


tab_full, tab_narrow, tab_bull, tab_bear, tab_top, tab_rules = st.tabs(
    ["Full table", "Narrow", "Bullish CPR", "Bearish CPR", "Top 20 narrow", "Rules"]
)

with tab_full:
    view = apply_filters(result.full)
    st.caption(f"{len(view)} rows after sidebar filters (of {len(result.full)})")
    if view.empty:
        st.info("No rows match the current filters.")
    else:
        st.dataframe(style_table(format_view(view)), use_container_width=True, height=480)
        st.download_button(
            "📥 Download full table (CSV)",
            data=csv_bytes(view),
            file_name=f"cpr_full_{result.date}.csv",
            mime="text/csv",
            use_container_width=True,
        )

with tab_narrow:
    view = apply_filters(result.narrow)
    st.caption(f"{len(view)} narrow names")
    if view.empty:
        st.info("No narrow CPR names for this date / filters.")
    else:
        st.dataframe(style_table(format_view(view)), use_container_width=True, height=480)
        st.download_button(
            "📥 Download narrow (CSV)",
            data=csv_bytes(view),
            file_name=f"cpr_narrow_{result.date}.csv",
            mime="text/csv",
            use_container_width=True,
        )

with tab_bull:
    view = apply_filters(result.bullish)
    st.caption("Close above CPR + bullish bias + width < 0.25%")
    if view.empty:
        st.info("No bullish CPR shortlist rows.")
    else:
        st.dataframe(style_table(format_view(view)), use_container_width=True, height=480)
        st.download_button(
            "📥 Download bullish (CSV)",
            data=csv_bytes(view),
            file_name=f"cpr_bullish_{result.date}.csv",
            mime="text/csv",
            use_container_width=True,
        )

with tab_bear:
    view = apply_filters(result.bearish)
    st.caption("Close below CPR + bearish bias")
    if view.empty:
        st.info("No bearish CPR shortlist rows.")
    else:
        st.dataframe(style_table(format_view(view)), use_container_width=True, height=480)
        st.download_button(
            "📥 Download bearish (CSV)",
            data=csv_bytes(view),
            file_name=f"cpr_bearish_{result.date}.csv",
            mime="text/csv",
            use_container_width=True,
        )

with tab_top:
    st.caption("Tradable setups: Own_Narrow + overlay, day’s turnover ≥ ₹2 cr, ranked by width percentile")
    if result.top20.empty:
        st.info("No narrow names to rank.")
    else:
        st.dataframe(style_table(format_view(result.top20)), use_container_width=True, height=480)
        st.download_button(
            "📥 Download top 20 (CSV)",
            data=csv_bytes(result.top20),
            file_name=f"cpr_top20_narrow_{result.date}.csv",
            mime="text/csv",
            use_container_width=True,
        )

with tab_rules:
    st.markdown(
        """
### What this app does (and does not)

The main **CPR Screening Console** stays on **port 8501**. The **breakout screener** stays on **port 8502**.

This app on **port 8503** is a **third screener**:

1. Download NSE cash (`CM`) and F&O (`FO`) UDI bhavcopies for one session
2. Keep **EQ operating companies** — drop ETFs, AMC schemes, mutual funds, liquid/gilt products
3. Join **Industry** from the Nifty 500 constituent list (other names = Unclassified)
4. CPR from that session's H/L/C:
   `P = (H+L+C)/3`, `BC = (H+L)/2`, `TC = 2P − BC`
5. Width % = `(CPR Top − CPR Bottom) / Close × 100`
6. **Narrow** ≤ 0.25% · **Moderate** 0.25–0.75% · **Wide** > 0.75% (absolute labels)
7. **Own_Narrow**: this name’s width is in the bottom 25% of its last ~60 sessions
8. **Overlay**: today’s CPR vs the prior session — Higher / Lower / Inside / Outside / Overlapping
9. **Setup**: Long = Own_Narrow + Above CPR + Higher overlay; Short = Own_Narrow + Below + Lower; Watch = Own_Narrow + Inside
10. **Bullish CPR** (legacy): close above CPR + Pivot > BC + width < 0.25%
11. **Bearish CPR** (legacy): close below CPR + Pivot < BC
12. Tag each cash symbol **F&O + Cash** if it appears in the F&O bhavcopy
13. Top 20 ranks Setup names with VALUE ≥ ₹2 cr by width percentile, not raw Width %

**Not the same as the live console.** This is EOD, exchange bhavcopy, no Yahoo, no virgin-CPR live quotes.
"""
    )

st.divider()
st.markdown(
    '<div style="text-align: center; color: gray; font-size: 0.9em;">'
    "NSE EOD CPR Scanner · port 8503 · separate from CPR console on 8501 and breakout on 8502 · research only"
    "</div>",
    unsafe_allow_html=True,
)
