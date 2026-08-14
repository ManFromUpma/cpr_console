# Weekly and monthly CPR

Daily CPR is a **next-session** map. If you do not want to flatten at 15:15, you do not “stretch” that daily box for a week. You draw a **new box from a bigger bar**.

Same formulas. Different H, L, C.

```
Pivot = (High + Low + Close) / 3
BC    = (High + Low) / 2
TC    = 2 × Pivot − BC
```

---

## Kid picture

- **Daily box** = last night’s lunch box. For **tomorrow** only.  
- **Weekly box** = last week’s lunch box (Mon–Fri high, low, Friday close). For **next week**.  
- **Monthly box** = last month’s lunch box. For **next month**.

You cannot keep Monday’s daily sandwich until 31 Aug. You *can* keep July’s monthly sandwich until August ends — because that is the map August is supposed to use.

---

## When the bigger box is drawn

| Timeframe | Completed bar | That CPR is for | You hold |
|---|---|---|---|
| Daily | One NSE session | Next session | That session (default flatten 15:15) |
| Weekly | Last completed week (usually Friday) | Next Mon–Fri | The next week, while price respects the weekly band |
| Monthly | Last completed calendar month | Next calendar month | That month, while price respects the monthly band |

**Mid-week:** Wednesday 12 Aug still uses the week that **ended last Friday**. This week’s weekly CPR is not finished until this Friday closes.

**Mid-month:** 14 Aug still uses **July’s** monthly CPR. August’s monthly CPR is printed after the **last trading day of August**. Then it applies to **September**.

Scan dated Friday **14 Aug 2026**:

- Daily CPR → next session **18 Aug** (Monday)  
- Weekly CPR (week ending 14 Aug) → week **17–21 Aug**  
- Monthly CPR (July complete) → **August 2026** (the month you are still in)

---

## Overlay and coil on the bigger box

Overlay is still **box vs previous box**, just weekly vs last week, or August vs July.

Own_Narrow weekly = this week’s width is in the tightest 25% of **this stock’s last ~52 weeks** (from the 252-day cache).

Own_Narrow monthly uses ~12 completed monthly bars. **Levels still print.** Monthly coil is stronger than before now that the cache holds ~252 trading days — but a newly listed stock still needs months of history before monthly Own_Narrow counts.

Setup Long on weekly: weekly Own_Narrow + week close above weekly CPR + weekly overlay Higher. You then **hold the next week**, stop if price closes back inside the **weekly** band (not the daily band).

---

## How this repo shows it

EOD site and Streamlit (port 8503) have **Weekly** and **Monthly** tabs. They roll cached daily bhavcopies into week/month bars. Daily tabs are unchanged. Shah console (8501) and 15m breakout (8502) stay intraday.

**Cache:** the bhavcopy cache defaults to ~252 trading days (`--lookback 252`). Daily `Own_Narrow` still ranks against the **last 60 sessions only**; the extra history exists so weekly and monthly bars have real depth (~52 weeks, ~12 months). Run `python eod_publish.py --lookback 252` (or `python nse_cpr_scanner.py YYYYMMDD --lookback 252`) to grow the cache.

Research only. Not investment advice.
