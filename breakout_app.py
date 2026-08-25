"""
CPR Breakout Screener — standalone Streamlit app.

Separate from the Shah CPR console (`app.py` on port 8501).
Run with: streamlit run breakout_app.py --server.port 8502
"""

from __future__ import annotations

import io
from datetime import datetime, timedelta
from typing import List

import pandas as pd
import pytz
import streamlit as st

from cpr_breakout_engine import (
    INTRADAY_MAX_DAYS,
    SESSION_TZ,
    backtest_cpr_breakout,
    screen_cpr_breakout,
)
from universe import INDEX_UNIVERSES, load_universe, universe_counts


st.set_page_config(
    page_title="CPR Breakout Screener",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

if "breakout_scan_results" not in st.session_state:
    st.session_state.breakout_scan_results = None
if "breakout_backtest" not in st.session_state:
    st.session_state.breakout_backtest = None


def parse_symbols_csv(csv_content: str) -> List[str]:
    symbols = []
    for line in csv_content.strip().split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        symbol = line.split(",")[0].strip() if "," in line else line
        if symbol:
            symbols.append(symbol)
    return symbols


def color_signal(val: str) -> str:
    if val == "Long":
        return "color: #2e7d32; font-weight: 600"
    if val == "Short":
        return "color: #c62828; font-weight: 600"
    if val == "Watch":
        return "color: #f57c00"
    return ""


def color_segment(val: str) -> str:
    if val == "Cash":
        return "color: #1565c0"
    if val == "F&O":
        return "color: #6a1b9a"
    return ""


with st.sidebar:
    st.header("⚡ Breakout config")
    st.caption("Independent of the CPR console (port 8501). Same universes, different rules.")

    symbol_input_method = st.radio(
        "Input method",
        ["Built-in universe", "Paste CSV", "Upload CSV"],
        index=0,
        key="breakout_input_method",
    )

    symbols: List[str] = []
    if symbol_input_method == "Built-in universe":
        universe_name = st.selectbox(
            "Universe",
            INDEX_UNIVERSES,
            index=INDEX_UNIVERSES.index("Nifty 50") if "Nifty 50" in INDEX_UNIVERSES else 0,
            key="breakout_universe",
            help="15m Yahoo data is heavy. Start with Nifty 50 or F&O.",
        )
        symbols = load_universe(universe_name)
        total_n, cash_n, fo_n = universe_counts(symbols)
        st.caption(f"{total_n} names · {cash_n} cash · {fo_n} F&O")
    elif symbol_input_method == "Paste CSV":
        csv_paste = st.text_area(
            "Paste symbols",
            height=160,
            placeholder="RELIANCE.NS\nTCS.NS\nINFY.NS",
            key="breakout_paste",
        )
        if csv_paste:
            symbols = parse_symbols_csv(csv_paste)
    else:
        uploaded = st.file_uploader("Upload CSV", type=["csv", "txt"], key="breakout_upload")
        if uploaded:
            symbols = parse_symbols_csv(uploaded.read().decode("utf-8"))

    st.markdown(f"**Symbols loaded:** {len(symbols)}")
    if len(symbols) > 80:
        st.warning("Large universe: 15m download will be slow and may time out.")

    st.divider()
    st.subheader("Strategy")
    narrow_quantile = st.slider(
        "Narrow quantile",
        min_value=0.05,
        max_value=0.50,
        value=0.20,
        step=0.05,
        help="Bottom X% of this symbol's own CPR width history = narrow.",
        key="breakout_q",
    )
    confirm_bars = st.number_input(
        "Confirm bars",
        min_value=1,
        max_value=5,
        value=1,
        help="Consecutive 15m closes beyond TC (long) or BC (short).",
        key="breakout_confirm",
    )
    rr_target = st.number_input(
        "Reward : risk",
        min_value=0.5,
        max_value=5.0,
        value=2.0,
        step=0.5,
        key="breakout_rr",
    )
    interval = st.selectbox(
        "Intraday interval",
        ["15m", "5m", "30m", "60m"],
        index=0,
        key="breakout_interval",
        help="Yahoo caps 5m/15m/30m at about 60 days of history.",
    )
    include_watch = st.checkbox(
        "Include Watch (narrow, not yet broken)",
        value=True,
        key="breakout_watch",
    )
    segment_filter = st.selectbox(
        "Segment",
        ["Any", "Cash", "F&O"],
        index=0,
        key="breakout_segment",
    )


st.title("⚡ CPR Breakout Screener")
st.markdown(
    """
**Separate from the Shah CPR console (port 8501).** This app screens **narrow-CPR breakouts**:
previous-day H/L/C → today's CPR, then **intraday closes through TC (long) or BC (short)**.
First signal of the day. Stop at the opposite band. Target = RR × risk. Flat at 15:15 IST.

*Research only. Yahoo 15m history is ~60 days. Not investment advice.*
"""
)

tab_screen, tab_backtest, tab_rules = st.tabs(["Live screener", "Backtest", "Rules"])

with tab_screen:
    col_a, col_b = st.columns([1, 3])
    with col_a:
        run_scan = st.button("🔍 Scan breakouts", type="primary", use_container_width=True)
    with col_b:
        st.caption(
            f"Yahoo {interval} · narrow ≤ {int(narrow_quantile * 100)}th pctile · "
            f"{confirm_bars} bar confirm · RR {rr_target:.1f}"
        )

    if run_scan:
        if not symbols:
            st.warning("No symbols loaded. Pick a universe in the sidebar.")
        else:
            with st.spinner(f"Downloading daily + {interval} bars for {len(symbols)} symbols…"):
                try:
                    result = screen_cpr_breakout(
                        symbols,
                        narrow_quantile=float(narrow_quantile),
                        confirm_bars=int(confirm_bars),
                        rr_target=float(rr_target),
                        interval=interval,
                        include_watch=include_watch,
                    )
                    st.session_state.breakout_scan_results = result
                except Exception as exc:
                    st.error(f"Scan failed: {exc}")

    df = st.session_state.breakout_scan_results
    if df is None:
        st.info("Click **Scan breakouts** to fetch Yahoo data and score today's setups.")
    elif df.empty:
        st.info("No rows returned. Try a smaller universe or a higher narrow quantile.")
    else:
        view = df.copy()
        if segment_filter != "Any" and "Segment" in view.columns:
            view = view[view["Segment"] == segment_filter]
        if not include_watch:
            view = view[view["Signal"].isin(["Long", "Short"])]
        missing = df[df["Data Status"] == "Data unavailable"] if "Data Status" in df.columns else pd.DataFrame()
        if "Data Status" in view.columns:
            view = view[view["Data Status"] != "Data unavailable"]

        longs = int((view["Signal"] == "Long").sum()) if not view.empty else 0
        shorts = int((view["Signal"] == "Short").sum()) if not view.empty else 0
        watches = int((view["Signal"] == "Watch").sum()) if not view.empty else 0

        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Scanned", len(symbols))
        m2.metric("Longs", longs)
        m3.metric("Shorts", shorts)
        m4.metric("Watch", watches)
        m5.metric("Rows shown", len(view))

        st.caption(
            datetime.now(pytz.timezone(SESSION_TZ)).strftime("%Y-%m-%d %H:%M:%S %Z")
            + " · first signal of the day · SL at BC (long) / TC (short)"
        )

        if view.empty:
            st.info("No names match the current filters.")
        else:
            show = view.copy()
            for col in ["Width %", "Last", "Pivot", "TC", "BC", "Entry", "SL", "TP", "Dist %"]:
                if col in show.columns:
                    show[col] = show[col].apply(lambda x: f"{x:.3f}" if pd.notna(x) else "—")

            styled = show.style
            if "Signal" in show.columns:
                styled = styled.map(color_signal, subset=["Signal"])
            if "Segment" in show.columns:
                styled = styled.map(color_segment, subset=["Segment"])
            st.dataframe(styled, use_container_width=True, height=440)

            buf = io.StringIO()
            view.to_csv(buf, index=False)
            st.download_button(
                "📥 Download breakout scan (CSV)",
                data=buf.getvalue().encode("utf-8"),
                file_name=f"cpr_breakout_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True,
            )

        if not missing.empty:
            with st.expander(f"Unavailable ({len(missing)})"):
                st.dataframe(missing[["Symbol", "Segment", "Data Status"]], use_container_width=True)

with tab_backtest:
    st.markdown("Run the same breakout rules on one symbol. Yahoo limits 15m/5m history to about **60 days**.")
    default_symbol = symbols[0] if symbols else "RELIANCE.NS"
    b1, b2, b3, b4 = st.columns(4)
    with b1:
        bt_symbol = st.text_input("Symbol", value=default_symbol, key="bt_symbol")
    with b2:
        max_days = INTRADAY_MAX_DAYS.get(interval, 59)
        bt_start = st.date_input(
            "Start",
            value=datetime.now().date() - timedelta(days=max_days),
            key="bt_start",
        )
    with b3:
        bt_end = st.date_input("End", value=datetime.now().date() + timedelta(days=1), key="bt_end")
    with b4:
        capital = st.number_input("Capital", min_value=10000, value=100000, step=10000, key="bt_capital")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        risk_pct = st.number_input(
            "Risk % per trade", min_value=0.001, max_value=0.05, value=0.01, step=0.005, key="bt_risk"
        )
    with c2:
        cost_bps = st.number_input("Cost (bps round-trip)", min_value=0.0, value=5.0, step=1.0, key="bt_cost")
    with c3:
        slippage_bps = st.number_input(
            "Slippage (bps per side)", min_value=0.0, value=0.0, step=1.0,
            help="Adverse execution allowance applied to both entry and exit.", key="bt_slippage"
        )
    with c4:
        ambiguous_policy = st.selectbox(
            "Same-bar collision", ["stop_first", "target_first"], index=0,
            help="If one bar touches stop and target, choose the conservative stop-first rule by default.",
            key="bt_ambiguous_policy"
        )

    run_bt = st.button("▶️ Run backtest", type="primary", use_container_width=True)

    if run_bt:
        with st.spinner(f"Backtesting {bt_symbol} on {interval}…"):
            try:
                st.session_state.breakout_backtest = backtest_cpr_breakout(
                    symbol=bt_symbol.strip(),
                    start=bt_start.isoformat(),
                    end=bt_end.isoformat(),
                    narrow_quantile=float(narrow_quantile),
                    confirm_bars=int(confirm_bars),
                    rr_target=float(rr_target),
                    risk_pct=float(risk_pct),
                    capital=float(capital),
                    cost_bps=float(cost_bps),
                    slippage_bps=float(slippage_bps),
                    ambiguous_policy=ambiguous_policy,
                    interval=interval,
                )
            except Exception as exc:
                st.error(f"Backtest failed: {exc}")

    bt = st.session_state.breakout_backtest
    if bt is None:
        st.info("Set a symbol and click **Run backtest**.")
    elif bt.get("trades") == 0 or bt.get("total_trades", 0) == 0:
        st.warning(bt.get("message", "No trades generated"))
        if bt.get("start"):
            st.caption(f"Window used: {bt.get('start')} → {bt.get('end')} ({bt.get('interval')})")
    else:
        k1, k2, k3, k4, k5, k6 = st.columns(6)
        k1.metric("Trades", bt["total_trades"])
        k2.metric("Win rate", f"{bt['win_rate_pct']}%")
        k3.metric("Profit factor", bt["profit_factor"])
        k4.metric("Total return", f"{bt['total_return_pct']}%")
        k5.metric("Final equity", f"₹{bt['final_equity']:,.0f}")
        k6.metric("Avg CPR width", f"{bt['avg_cpr_width_pct']}%")
        st.caption(
            f"{bt['symbol']} · {bt.get('interval')} · {bt.get('start')} → {bt.get('end')} · "
            f"avg win {bt['avg_win_pct']}% / avg loss {bt['avg_loss_pct']}% · "
            f"cost {bt.get('cost_bps', cost_bps)} bps · slippage {bt.get('slippage_bps', slippage_bps)} bps/side · "
            f"collision {bt.get('ambiguous_policy', ambiguous_policy)}"
        )
        tdf = bt.get("trades_df")
        if tdf is not None and not tdf.empty:
            show_t = tdf.copy()
            st.dataframe(show_t, use_container_width=True, height=360)
            tbuf = io.StringIO()
            show_t.to_csv(tbuf, index=False)
            st.download_button(
                "📥 Download trades (CSV)",
                data=tbuf.getvalue().encode("utf-8"),
                file_name=f"cpr_breakout_trades_{bt_symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True,
            )

with tab_rules:
    st.markdown(
        f"""
### What this app does (and does not)

The main **CPR Screening Console** stays on **port 8501**: Shah bands, virgin CPR, overlay, live watchlist.

This app on **port 8502** is a **second screener**:

1. Daily CPR from previous H/L/C: `P = (H+L+C)/3`, `BC = (H+L)/2`, `TC = 2P − BC`
2. **Narrow** if that width % is in the bottom **{int(narrow_quantile * 100)}%** of *this symbol's* history
3. On `{interval}` bars, **long** after {confirm_bars} close(s) above TC, **short** after {confirm_bars} close(s) below BC
4. Only the **first** signal of the session
5. Stop at BC (long) or TC (short); target = **{rr_target:.1f}×** risk; flatten at **15:15 IST**
6. Backtests apply configured cost and slippage; gap exits fill at the bar open; same-bar stop/target collisions use the selected policy (default: stop-first)

Yahoo Finance does not provide years of 15-minute history. Backtests on 15m/5m are capped at about 60 days.

**Not the same as the CPR console filters.** A name can be “narrow” here (quantile vs its own past) and not match the console’s absolute Width % cut.
"""
    )

st.divider()
st.markdown(
    '<div style="text-align: center; color: gray; font-size: 0.9em;">'
    "CPR Breakout Screener · port 8502 · separate from CPR console on 8501 · research only"
    "</div>",
    unsafe_allow_html=True,
)
