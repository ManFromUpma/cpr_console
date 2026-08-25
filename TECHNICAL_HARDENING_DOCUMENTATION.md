# CPR Console Technical Hardening Documentation

**Status:** Implemented review recommendations  
**Audience:** Maintainers, quantitative researchers, data engineers, and reviewers  
**Scope:** Data correctness, backtest execution realism, provenance, cache quality, site visibility, CI quality gates, and regression testing

## 1. Purpose and design principles

The CPR Console is a rule-based research system. The hardening work improves the reliability and auditability of its calculations and generated outputs without claiming that CPR signals are profitable. The implementation preserves the project’s existing signal definitions and adds safeguards around how the system obtains data, how it records assumptions, and how it simulates trades.

The changes follow five principles:

| Principle | Implementation |
|---|---|
| One numerical source of truth | CPR constants and formulas remain centralized in `cpr_contract.py`. |
| No accidental future information | Previous completed bars remain the only CPR inputs for subsequent periods; regression tests cover this contract. |
| Data assumptions are visible | Publication manifests and live rows expose provider, timezone, and price-adjustment policy. |
| Backtests must disclose execution assumptions | Slippage, gap fills, same-bar collisions, fees, and exit reasons are recorded. |
| Review and automation remain advisory | The professional review agent does not modify source code, trade, deploy, or send alerts. |

## 2. Files changed

| File | Change |
|---|---|
| `cpr_contract.py` | Added `PRICE_ADJUSTMENT_POLICY = "unadjusted_ohlc"` and `DATA_POLICY_VERSION = 1`. |
| `nse_cpr_scanner.py` | Added bounded retries/backoff for NSE downloads; added `bhavcopy_manifest.json` creation and reading; imported the shared data policy. |
| `publication_contract.py` | Added provider, timezone, adjustment policy, data-policy version, cache completeness, and missing-date metadata to the publication manifest. |
| `eod_site.py` | Updated the data-status banner to show source, policy, timezone, and cached/requested history counts, warning when history is incomplete. |
| `data_provider.py` | Added `price_adjustment_policy` to `OHLCVData`. |
| `app.py` | Added provider, adjustment-policy, and session-timezone columns to live-console rows. |
| `cpr_breakout_engine.py` | Added slippage, gap-aware fills, same-bar collision policy, exit reasons, ambiguity flags, and execution metadata. |
| `breakout_app.py` | Added UI controls for slippage and collision policy and displays them in the backtest summary. |
| `requirements-ci.txt` | Added `coverage` and `ruff` for CI quality checks. |
| `.github/workflows/eod-publish.yml` | Added Python compilation, coverage execution/reporting, and Ruff checks. |
| `test_cpr_breakout.py` | Added regression tests for slippage, ambiguous bars, and gap exits. |
| `test_publication_contract.py` | Added manifest provenance/history-quality assertions. |
| `test_actionable_hardening.py` | Added offline tests for transient download retry and cache manifests. |
| `README.md` | Added instructions for the professional review agent. |
| `EXPERT_REVIEW_AGENT.md` | Added review-agent operating instructions. |
| `expert_review_agent.py` and `run_expert_review.py` | Added the offline evidence collector and professional review runner. |

## 3. Data policy and provenance

### 3.1 Price-adjustment policy

The repository now declares an explicit policy in `cpr_contract.py`:

```python
PRICE_ADJUSTMENT_POLICY = "unadjusted_ohlc"
DATA_POLICY_VERSION = 1
```

This means CPR levels and the current EOD history path are calculated from the supplied OHLC values without applying a split/dividend adjustment inside the CPR contract. The Yahoo provider already requests `auto_adjust=False`, and NSE bhavcopies are treated as the reported exchange values. This is a consistency policy, not a claim that unadjusted prices are universally superior.

A future adjusted-price workflow must not silently reuse the current outputs. It should introduce a distinct policy value, document whether OHLC and volume are adjusted, record the adjustment source, and add a corporate-action regression fixture.

### 3.2 Manifest metadata

`publication_contract.build_manifest()` now records:

```json
{
  "source": {
    "name": "NSE UDI bhavcopy",
    "mode": "requested_session",
    "provider": "NSE",
    "session_timezone": "Asia/Kolkata",
    "price_adjustment_policy": "unadjusted_ohlc",
    "data_policy_version": 1
  },
  "history": {
    "requested_sessions": 252,
    "cached_sessions": 252,
    "complete": true,
    "missing_dates": [],
    "cache_manifest": "bhavcopy_manifest.json"
  }
}
```

The fields are designed to answer four audit questions: where did the values come from, which clock defines the session, what adjustment convention was used, and whether the requested historical depth was actually available.

### 3.3 Live-console provenance

`OHLCVData` now carries `price_adjustment_policy`. `app.py` includes the following fields in live rows:

| Field | Meaning |
|---|---|
| `Data Source` | Yahoo Finance, Perplexity Finance, or mock provider label. |
| `Price Adjustment Policy` | Current explicit policy, normally `unadjusted_ohlc`. |
| `Session Timezone` | Timezone used to identify “today” and completed sessions. |
| Existing `Data Timestamp` / `Data Status` | When the data was fetched and whether it is Live, OK, Delayed, Stale, or unavailable. |

## 4. NSE retry and cache-completeness design

### 4.1 Download behavior

`download_bhavcopy()` now accepts `retries` and `backoff_seconds`. The default is three retries with exponential delays of 1, 2, and 4 seconds. HTTP 404 is treated as an unavailable archive date, which is normal for weekends and holidays. HTTP 429, server errors, connection errors, timeouts, malformed zip files, and CSV parser failures receive bounded retries. After the retry budget is exhausted, the function returns `None`, preserving the caller’s existing failure-handling contract.

The retry policy is bounded to prevent a scheduled job from hanging indefinitely. It also avoids retrying a known missing date. A future production enhancement could honor `Retry-After` when supplied by the server.

### 4.2 Cache manifest

`ensure_bhavcopy_history()` now records attempted and successfully cached dates in `cpr_output/bhavcopy_manifest.json`. The manifest includes:

| Field | Meaning |
|---|---|
| `end_date` | Scan endpoint date. |
| `requested_sessions` | Requested number of completed sessions. |
| `cached_sessions` | Number successfully present or downloaded. |
| `attempted_dates` | Weekday dates checked. |
| `missing_dates` | Attempted dates without a valid cached bhavcopy. |
| `complete` | True when cached sessions meet the request. |
| `session_timezone` | Timezone used by the scanner. |
| `price_adjustment_policy` | Shared data policy. |
| `data_policy_version` | Version for reproducibility. |

The manifest contains metadata only. It does not duplicate market rows or send them into the review agent. In addition, `load_history_panel()` now keeps up to four distinct `(cache directory, requested dates)` panels in a bounded in-process cache. It returns copies so callers cannot mutate the cached frame, and a new date-set key naturally bypasses stale entries. This improves repeated reads during one scan/backfill process without pretending that the cache is a durable database.

## 5. Backtest execution model

### 5.1 New parameters

`simulate_trades()` now accepts:

```python
slippage_bps: float = 0.0
ambiguous_policy: str = "stop_first"
```

`backtest_cpr_breakout()` exposes the same options and writes them into the result dictionary.

| Parameter | Meaning | Default |
|---|---|---:|
| `cost_bps` | Existing round-trip cost allowance used in P&L. | 5.0 |
| `slippage_bps` | Adverse price allowance applied on entry and exit. | 0.0 |
| `ambiguous_policy` | Fill convention when one bar touches both stop and target. | `stop_first` |
| `rr_target` | Target distance as a multiple of initial risk. | 2.0 |
| `risk_pct` | Fraction of equity risked relative to initial stop distance. | 0.01 |
| `eod_flat` | Time after which an open position is closed. | 15:15 IST |

### 5.2 Entry and exit price rules

For a long entry, the raw signal close is increased by slippage. For a short entry, it is reduced by slippage. The stop remains at the opposite CPR edge: BC for long and TC for short. The target is calculated from the slipped entry price and the configured reward-to-risk multiple.

At exit, slippage is adverse to the direction: a long exit is reduced and a short exit is increased. The configured round-trip cost allowance is then subtracted from directional P&L. Existing callers that leave slippage at zero preserve their prior price behavior, aside from the newly explicit metadata fields.

### 5.3 Gap handling

If the bar opens beyond the stop or target, the backtest uses the opening price as the raw fill. This avoids pretending that a stop at a price below a gap-down open was filled exactly at the stop. The output records `stop_gap` or `target_gap` in `exit_reason` and sets `gap_exit = True`.

### 5.4 Same-bar collisions

If a bar’s high and low touch both the stop and target, the sequence of intrabar events is unknowable from OHLC bars alone. The default `stop_first` policy is conservative. The alternative `target_first` policy is available for sensitivity analysis. The trade record includes:

| Field | Meaning |
|---|---|
| `ambiguous_bar` | Both stop and target were touched. |
| `exit_reason` | Stop, target, EOD flat, gap, or collision-specific result. |
| `entry_raw` / `exit_raw` | Prices before slippage. |
| `entry` / `exit` | Prices after adverse slippage. |
| `slippage_bps` / `cost_bps` | Assumptions used for that trade. |

The backtest summary includes the selected policy and a human-readable execution-policy statement.

## 6. CI and quality gates

The CI dependency file now includes `coverage` and `ruff`. The GitHub workflow performs the following checks before scanning and publishing:

1. Python bytecode compilation with `python -m compileall -q .`.
2. Full unittest discovery under branch coverage.
3. Coverage report generation with missing lines shown.
4. Ruff checks for common errors and warnings using `E,F,W` selections.
5. Existing scan/site build and publication-contract validation.
6. Existing generated-site smoke checks and CSV archive commit/deployment.

The current workflow still needs repository write permission because it commits generated CSV archives. That is a documented residual operational risk. A future least-privilege redesign should split archive commits from Pages deployment or publish generated archives outside the source repository.

## 7. Test coverage added

The new tests are offline and do not require NSE or Yahoo access:

| Test | What it proves |
|---|---|
| `test_download_retries_transient_server_error` | A transient 503 is retried and succeeds within the configured budget. |
| `test_cache_manifest_records_incompleteness_and_policy` | Missing dates, completeness, and data policy are persisted. |
| `test_manifest_includes_provenance_and_history_quality` | Publication manifests expose provider, adjustment policy, and cache manifest reference. |
| `test_slippage_is_recorded_and_reduces_long_entry` | Slippage is applied and recorded. |
| `test_stop_first_ambiguous_bar_is_reported` | Same-bar stop/target collision is visible and follows the conservative default. |
| `test_stop_gap_uses_open_and_is_reported` | Gap exits use the open and are labelled. |

## 8. Operational runbook

Before trusting a published scan, inspect `publication_manifest.json` and confirm that `source.provider`, `source.session_timezone`, `source.price_adjustment_policy`, `actual_data_date`, and `history.complete` match the intended run. If history is incomplete, treat Own_Narrow, ATR, SMA, weekly, and monthly results as potentially under-informed.

For a historical breakout evaluation, report the interval, date window, narrow quantile, confirmation-bar count, reward-to-risk target, risk percentage, costs, slippage, collision policy, and whether gaps/ambiguous bars occurred. Do not compare two backtests unless these assumptions are held constant.

For CI failures, distinguish dependency/import errors from test failures, and distinguish source/test failures from live-NSE archive availability. The scan should fail visibly when the requested current data cannot be obtained; it should not manufacture a successful fresh result from missing data.

## 9. Known residual work

The implementation deliberately does not change trading thresholds, add corporate-action adjustment, introduce an LLM into signal generation, or automatically rewrite source code. Recommended future work includes a formal corporate-action dataset/fixture, an incremental cache index that avoids repeated full-panel reads, a separate least-privilege publication architecture, pinned dependency hashes, coverage thresholds for core modules, and out-of-sample evaluation that accounts for survivorship bias and realistic order mechanics.
