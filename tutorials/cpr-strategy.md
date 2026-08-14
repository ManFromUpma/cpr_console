# Daily CPR tutorial

Research / education only. Not investment advice. This matches how **this repo** uses Central Pivot Range: one completed NSE cash session prints the map for the **next** session.

If you only remember one thing: **a daily CPR does not last the month.**

---

## The question: I look at a stock on 1 Aug. Do I hold until 31 Aug?

No.

| You look at | What those levels are | When you may enter | How long you hold |
|---|---|---|---|
| Scan dated **1 Aug** (after 1 Aug close) | CPR from 1 Aug high, low, close | The **next trading session** (2 Aug, or Monday if 1 Aug is a weekend) | **That session**, by default. Not the rest of August. |

When that next session closes, the map is finished. 2 Aug H/L/C print a **new** CPR for 3 Aug. Yesterday’s Long is not automatically today’s Long.

1 Aug 2026 was a Saturday. In that calendar the last completed session is **31 Jul**, and that CPR applies to **Monday 3 Aug**. The rule is the same: previous completed bar → next session only.

---

## What CPR is

CPR is three lines from the previous daily bar:

```
Pivot = (High + Low + Close) / 3
BC    = (High + Low) / 2          # bottom of the range
TC    = 2 × Pivot − BC            # top of the range
```

The scanner stores CPR Top = max(TC, BC) and CPR Bottom = min(TC, BC). Width % = (Top − Bottom) / Close × 100.

- Price **above CPR** (close > TC) = finished the previous day in the long half of the map.
- Price **below CPR** (close < BC) = finished in the short half.
- Price **inside** = still coiled in the band.

That is a **next-day floor/ceiling**, not a monthly trend model. Weekly or monthly CPR exists if you feed weekly/monthly H/L/C into the same formulas. This console does **daily** bars only.

---

## Clock: 1 Aug scan → 2 Aug trade

1. **1 Aug 15:30** — session ends. H, L, C exist. You do **not** trade 1 Aug with 1 Aug CPR; that bar *built* the map.
2. **1 Aug evening** — EOD scan dated 1 Aug. Pivot / BC / TC, width, overlay, Setup. This is the **2 Aug watchlist**.
3. **2 Aug 09:15** — same CPR as last night. Enter only if price opens and **holds** on the Setup side of TC (long) or BC (short).
4. **2 Aug 15:15** — default flatten. Daily CPR is a session strategy. This repo’s 15m breakout engine is explicitly flat by 15:15 IST.
5. **2 Aug evening** — new scan. New CPR from 2 Aug H/L/C. Overlay vs the 1 Aug band. Re-qualify from scratch.

A Friday scan is the map for Monday, not for Saturday.

If you want to **hold a week or a month**, you must use **weekly or monthly CPR**, not the daily box. Same formulas, bigger bars. See `tutorials/cpr-weekly-monthly.md`.

---

## How long to hold after you enter on 2 Aug

Daily CPR is **not** “buy the coil and sit until month-end.”

**Default — same session.**  
Enter 2 Aug. If price fails back inside the band, you are out. If it trends, trail toward the day high (long) or day low (short). Flatten into the close.

**Optional — one overnight.**  
Only if 2 Aug **closes** still outside the band, in your direction, and you accept gap risk. On 3 Aug the CPR is new. Keep the trade only if:

- overlay is still **Higher** (long) or **Lower** (short), and
- price holds the **new** TC / BC.

New day, new stop: long stop belongs at the new BC, not at yesterday’s BC.

**Do not hold the month.**  
By 10 Aug the 1 Aug band is unrelated. If you want a multi-week swing, compute **weekly or monthly CPR** from those bars. That is a different map and this scanner does not print it.

| If this happens on 2 Aug | Hold? | Exit |
|---|---|---|
| Opens above TC, holds, Setup was Long | Intraday yes | Trail; flatten 15:15 unless overlay still agrees tomorrow |
| Opens above TC, slips back inside CPR | No | Stop. The break failed. |
| Opens inside CPR | Usually no | Wait for a 15m close through TC/BC, or skip |
| Closes strong, next CPR is Higher | Optional 3 Aug | Re-validate on the new TC. New stop = new BC |
| Closes strong, next CPR is Lower or Inside | No | The map flipped. Daily thesis is over. |

---

## Width: why “above CPR” is not a Long

A tight band means the previous day was compressed. The next session often expands. A wide band means the previous day already expanded. Close-above-TC after a huge range is often **late**, not a coil.

This scanner:

- **CPR class** (Narrow ≤ 0.25%, Moderate 0.25–0.75%, Wide > 0.75%) — same cut for every name, a label only.
- **Own_Narrow** — this name’s width is in the bottom 25% of **its own** last ~60 sessions. That is the coil filter.

**Setup Long** needs all three: Own_Narrow + close above CPR + overlay **Higher**.  
**Setup Short**: Own_Narrow + close below CPR + overlay **Lower**.  
**Watch**: Own_Narrow and still inside the band (no EOD side; use the 15m breakout app next morning).

Overlay is today’s CPR vs the **prior session’s** CPR:

- **Higher** — entire band shifted up (trend continuation, long side).
- **Lower** — entire band shifted down (short side).
- **Inside / Outside / Overlapping** — chop or squeeze; not an automatic Long just because close > TC.

### Worked contrast (14 Aug 2026 EOD → next session 18 Aug)

| Name | Position | Overlay | Width | Setup | Read |
|---|---|---|---|---|---|
| DLF | Above CPR | Higher | Own-narrow | **Long** | Coil + side. Candidate for the next session only. |
| LICHSGFIN | Below CPR | Lower | Own-narrow | **Short** | Coil + side the other way. |
| TARSONS | Above CPR | Higher | Wide, rank 0.95 | **No setup** | Already ran (311.9–375). Close above TC is not a Long. |

TARSONS closed 360.30 vs CPR 343.45–354.68. Above CPR is true. Own_Narrow is false. The scanner is doing the right thing.

---

## How the three apps fit

| App | When | Job |
|---|---|---|
| EOD site / `eod_app.py` (port 8503) | After close | Tomorrow’s CPR and Setup list |
| Shah console `app.py` (8501) | During the session | Virgin CPR, open vs band, live overlay |
| Breakout `breakout_app.py` (8502) | First 15m | First confirmed TC/BC break; flat 15:15 |

Night: pick Long / Short / Watch. Morning: act only if the open agrees. Afternoon: flatten. Evening: the map resets.

---

## Checklist before you click buy on “2 Aug”

1. The date on the site is the **previous completed session**, not today.
2. Setup is Long or Short — not merely Above CPR.
3. Prefer F&O names; cash-only thin names gap through stops.
4. 2 Aug open is **on the Setup side** of TC/BC and holds.
5. Stop is back inside the band (through BC for a long, through TC for a short).
6. You have a same-day exit. You are not marrying the name until 31 Aug.
