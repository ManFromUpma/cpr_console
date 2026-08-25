# CPR Console Improvements: A Plain-English Guide

**What changed:** The repository was reviewed by a professional expertise agent, and the most important practical improvements were implemented.  
**What this is not:** It is not a promise that the CPR strategy will make money, and it does not turn the system into an automatic trading bot.

## 1. The short version

The CPR Console already had a useful structure: it downloaded market data, calculated CPR levels, looked for narrow-band situations, checked direction and trend, and published results. The improvements make it harder for the system to give a misleading impression of certainty.

The main improvements are:

| Improvement | Simple meaning |
|---|---|
| Clear price-data policy | The system now says whether it uses adjusted or unadjusted prices instead of leaving that assumption hidden. |
| Better download retries | Temporary NSE problems are retried instead of immediately producing an incomplete history. |
| History-quality record | The system records how many historical sessions it wanted, how many it actually has, and which dates were missing. |
| Visible data source | Users can see the provider, timezone, and price policy behind a result. |
| More realistic backtests | Simulations now account for slippage, price gaps, and bars where the stop and target were both touched. |
| Stronger tests | New tests check these protections so a future code change is less likely to remove them accidentally. |
| Better CI checks | Automated builds now compile Python, run tests with coverage, and run static checks. |
| Expert review remains advisory | The review agent gives recommendations but does not edit code, trade, publish, or send alerts by itself. |

## 2. Why these changes matter

A stock screener is like a measuring instrument. Even if the formula is correct, the result can be misleading when the measuring tape is inconsistent, the data is missing, or the experiment assumes perfect execution. The changes improve the measuring process before anyone interprets the signal.

For example, a narrow CPR may look attractive because it suggests compression. But if the historical data is missing several sessions, the system may not know whether the band is truly unusual for that stock. Similarly, a backtest may look profitable if it assumes that a trade always exits exactly at a stop or target even when the market jumps over that price.

## 3. The data policy in everyday language

The system now uses the label `unadjusted_ohlc`. This means that the CPR calculation uses the reported Open, High, Low, and Close values as provided by the data source rather than silently rewriting old prices for splits, bonuses, or dividends.

This is like comparing old ruler readings without changing the ruler after a company changes its share structure. It is a consistent choice, but it has consequences. A stock split can make historical prices look dramatically different from current prices. That can affect CPR width, moving averages, ATR, and backtest results.

Therefore, every serious analysis should record the price policy. If the project later adds adjusted prices, it should use a clearly different mode and test the transition with a corporate-action example. The new policy is stored in `cpr_contract.py`, live rows, the EOD publication manifest, and the cache manifest.

## 4. What happens when NSE data temporarily fails?

Previously, an unavailable download could simply result in a missing session while the larger process continued. The improved downloader now distinguishes a known missing archive from a temporary problem.

A weekend or market holiday may correctly have no bhavcopy. That is not necessarily an error. A server error, timeout, connection problem, malformed zip file, or rate limit may be temporary. Those cases are retried up to a fixed limit with increasing waits: approximately 1 second, then 2 seconds, then 4 seconds by default.

The waiting limit is intentional. The program should not hang forever waiting for a website. If all attempts fail, the failure remains visible and the history-quality record can show that the requested history was not fully obtained.

## 5. The history-quality record

The scanner now writes `cpr_output/bhavcopy_manifest.json`. Think of it as a packing list for historical data.

| Question | Manifest answer |
|---|---|
| What date did the scan cover? | `end_date` |
| How many sessions were requested? | `requested_sessions` |
| How many were found or downloaded? | `cached_sessions` |
| Which dates were checked? | `attempted_dates` |
| Which attempted dates were not available? | `missing_dates` |
| Is the requested history complete? | `complete` |
| Which price convention was used? | `price_adjustment_policy` |
| Which market clock was used? | `session_timezone` |

If the manifest says `complete: false`, be cautious with results that depend on history, such as Own_Narrow, ATR, SMA, weekly CPR, and monthly CPR. It does not automatically mean that every row is useless; it means the user should know that the historical context is incomplete.

## 6. What users will see on the website and live console

The EOD website’s status banner now includes the data session, source, price policy, timezone, and history count. It can warn when the requested history is incomplete. This prevents a user from seeing a polished table without seeing the conditions under which it was produced.

The live console now adds fields such as:

| Field | Everyday meaning |
|---|---|
| `Data Source` | Which data courier supplied the prices. |
| `Price Adjustment Policy` | Whether old prices were adjusted or left as supplied. |
| `Session Timezone` | Which local clock determines whether a bar belongs to today or yesterday. |
| `Data Timestamp` | When the data was fetched. |
| `Data Status` | Whether the data is live, acceptable, delayed, stale, or unavailable. |

## 7. Backtesting: what became more realistic

A backtest is a replay of old market data. It is useful, but it is not a time machine. Historical OHLC bars tell us the opening, highest, lowest, and closing prices, but they usually do not tell us the exact order of events inside the bar.

### 7.1 Slippage

Slippage is the difference between the price a strategy wants and the price it actually receives. In a fast market, a long entry may fill slightly higher than the signal close. A long exit may fill slightly lower. The reverse applies to short trades.

The backtest now accepts `slippage_bps`. “Bps” means basis points; 100 basis points equals 1%. The default is zero to preserve existing behavior, but the UI now allows the user to enter a more realistic assumption.

### 7.2 Gaps

A gap occurs when the market opens beyond a stop or target. For example, if a long trade has a stop at ₹100 but the next bar opens at ₹98, the simulation should not claim that it exited at exactly ₹100. The improved model fills at the opening price, records `stop_gap`, and sets `gap_exit` to true.

This is like trying to catch a bus at a stop: if the bus jumps past the stop, you cannot pretend you boarded at the old location.

### 7.3 Stop and target touched in the same bar

Suppose a 15-minute bar has a low below the stop and a high above the target. The bar does not tell us which happened first. The improved backtest records this as an `ambiguous_bar`.

The default rule is `stop_first`, which is deliberately conservative. The user can test `target_first` as a sensitivity comparison, but should not quietly mix the two assumptions when comparing results.

### 7.4 New trade-record fields

The generated trade table now explains what happened instead of showing only a final profit number.

| Field | Meaning |
|---|---|
| `entry_raw` and `exit_raw` | Prices before slippage. |
| `entry` and `exit` | Prices after adverse slippage. |
| `exit_reason` | Stop, target, gap, end-of-day, or ambiguous collision. |
| `ambiguous_bar` | Whether stop and target were both touched in one bar. |
| `gap_exit` | Whether the opening price caused a gap exit. |
| `slippage_bps` | Slippage assumption used. |
| `cost_bps` | Cost allowance used. |

## 8. What the professional review agent does

The repository now includes `run_expert_review.py`. It is a software and research-quality reviewer, not a trading oracle.

Run it from the repository root:

```bash
python3 run_expert_review.py .
```

It creates:

- `expert_review_report.md`, which is the readable report.
- `expert_review_evidence.json`, which is the structured evidence and findings.

The agent reads the source and configuration, summarizes generated CSV archives instead of loading every row, and checks areas such as data handling, duplicate CPR logic, look-ahead risk, backtest realism, performance, testing, and publication safety.

It does not fetch current prices, place orders, change source code, deploy the site, or send alerts. Its output should be treated like a careful code-review memo: useful for deciding what to investigate and improve, but still subject to human review.

## 9. What the automated quality checks do

The continuous-integration workflow now performs several checks before publication:

1. It compiles Python files to catch syntax errors.
2. It runs the test suite with branch coverage.
3. It reports which lines were not exercised.
4. It runs a static checker for common Python errors and warnings.
5. It builds and validates the EOD site as before.

This is similar to checking a car’s engine, brakes, and dashboard lights before a long trip. Passing the checks does not guarantee that the car will never fail, but skipping them would be irresponsible.

## 10. How to interpret a result safely

A good-looking CPR row should be read as a structured research candidate, not as an instruction to buy or sell. Ask the following questions:

| Question | Why it matters |
|---|---|
| Is the data session the one I intended? | A daily CPR applies to the next session, not automatically to the rest of the month. |
| Is the history complete? | Width ranks and moving indicators need enough history. |
| What provider and price policy were used? | Different sources and adjustments can produce different values. |
| Is the band narrow for this stock’s own history? | A fixed narrow label alone may not mean unusual compression. |
| Does price, bias, overlay, and regime agree? | A single column should not be treated as the entire setup. |
| Is the stock liquid enough? | Thin trading can cause large gaps and difficult exits. |
| Were costs, slippage, gaps, and collisions included in any backtest? | Perfect fills can make historical performance look better than reality. |
| Is the signal aligned with weekly and monthly context? | A one-day move can conflict with a larger trend. |

## 11. Remaining work in simple terms

The improvements intentionally stop short of changing the strategy itself. The project still needs a formal corporate-action data source and test fixture, deeper incremental caching, a least-privilege redesign for the workflow that commits generated CSVs, pinned dependency hashes, formal coverage thresholds, and broader out-of-sample research.

These are future improvements because they require decisions about data vendors, storage, deployment, and research methodology. They should not be added silently, because changing them can change the meaning of historical results.

## 12. Where to read the technical details

Maintainers should start with `TECHNICAL_HARDENING_DOCUMENTATION.md`, then inspect the changed implementation files and tests listed there. Users who want the original CPR concepts should also read `CPR_CONSOLE_LAYMAN_DOCUMENTATION.md`.
