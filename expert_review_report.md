# Professional Expert Review: CPR Console

**Generated:** 2026-08-25T21:55:44.128105+00:00  
**Mode:** Review-only, offline, repository-evidence driven  
**Scope:** Software engineering, data quality, CPR research correctness, efficiency, testing, operations, and AI transparency

> This report is a technical and research-process review. It does not issue investment recommendations and does not claim that any CPR setup is profitable.

## Executive assessment

The repository has a clear separation between live analysis, intraday breakout research, and EOD publication. It also contains useful safeguards around completed periods, deterministic CPR contracts, explainable scoring, and publication validation. The highest-value improvements are to make **data provenance and corporate-action policy explicit**, preserve **look-ahead protections as shared release-gate invariants**, make **backtest execution assumptions more realistic**, and improve **incremental history acquisition and CI quality gates**. The review found **6 findings**, including **0 critical** and **0 high-severity** items.

## Repository evidence snapshot

| Evidence | Value |
|---|---:|
| Tracked files observed | 1708 |
| Generated output files summarized | 1664 |
| Findings | 6 |
| Analysis network access | None |
| Source modification by reviewer | None |

## Prioritized recommendations

| Priority | ID | Severity | Recommendation | Effort |
|---:|---|---|---|---|
| 3 | ARCH-001 | Medium | Keep one canonical CPR implementation | Medium |
| 2 | PERF-001 | Medium | History refresh can be made incremental and parallel-safe | Medium |
| 4 | PERF-002 | Low | Generated archive growth should be managed | Medium |
| 2 | OPS-001 | Medium | Separate scan publication permissions from repository write access where possible | Medium |
| 5 | AI-001 | Informational | The current repository is deterministic, not an AI predictor | Small |
| 3 | REPO-001 | Medium | Keep generated market data out of default review prompts | Medium |

## Detailed findings

### ARCH-001: Keep one canonical CPR implementation

**Category:** Architecture  
**Severity:** Medium  
**Confidence:** High  
**Priority:** 3

**Impact.** Multiple formula representations can drift in thresholds, denominator conventions, or edge-case handling.

> **Repository evidence:** The repository has a canonical contract, plus separate live and breakout adapters that repeat formula-oriented logic and column mappings.

**Files.** `cpr_contract.py`, `cpr_engine.py`, `cpr_breakout_engine.py`, `nse_cpr_scanner.py`.

**Recommendation.** Keep numerical math exclusively in cpr_contract.py and test adapters only as compatibility mappings.

**Acceptance criteria.** A repository test asserts all consumers use calculate_cpr/calculate_cpr_frame and no consumer contains independent CPR arithmetic.

### PERF-001: History refresh can be made incremental and parallel-safe

**Category:** Efficiency  
**Severity:** Medium  
**Confidence:** High  
**Priority:** 2

**Impact.** A 252-session cache fill can issue many sequential network requests and repeatedly load/concatenate large Pandas panels.

> **Repository evidence:** ensure_bhavcopy_history loops dates sequentially and load_history_panel reads every cached CSV for each scan/backfill path.

**Files.** `nse_cpr_scanner.py`, `eod_publish.py`.

**Recommendation.** Add a cache manifest, skip known unavailable holidays, separate acquisition from computation, and benchmark a bounded concurrent downloader with rate limits.

**Acceptance criteria.** A benchmark records scan time, request count, and memory for 60 and 252 sessions; repeated scans do not re-read unchanged inputs unnecessarily.

### PERF-002: Generated archive growth should be managed

**Category:** Efficiency and storage  
**Severity:** Low  
**Confidence:** High  
**Priority:** 4

**Impact.** Daily full tables, shortlist files, caches, and site downloads accumulate indefinitely and increase clone, build, and deployment cost.

> **Repository evidence:** The repository tracks a large date-stamped cpr_output archive and the site builder writes per-date pages and downloads.

**Files.** `eod_site.py`, `eod_publish.py`, `.github/workflows/eod-publish.yml`.

**Recommendation.** Define retention tiers, compress archival inputs, avoid duplicating identical exports, and publish a compact manifest/index.

**Acceptance criteria.** A documented retention policy exists and a year-scale fixture stays within an agreed repository and build-size budget.

### OPS-001: Separate scan publication permissions from repository write access where possible

**Category:** Operations and security  
**Severity:** Medium  
**Confidence:** High  
**Priority:** 2

**Impact.** A compromised workflow or dependency could modify the repository as well as publish the site.

> **Repository evidence:** The scheduled workflow grants contents: write, pages: write, and id-token: write, and commits generated CSVs.

**Files.** `.github/workflows/eod-publish.yml`, `eod_publish.py`.

**Recommendation.** Use a least-privilege design: publish artifacts without write access when possible, or isolate archive commits in a narrowly scoped workflow with pinning and review.

**Acceptance criteria.** The workflow’s permissions are justified in documentation and a dry-run proves site deployment still works with the minimum required scopes.

### AI-001: The current repository is deterministic, not an AI predictor

**Category:** AI and transparency  
**Severity:** Informational  
**Confidence:** High  
**Priority:** 5

**Impact.** Calling rule-based scoring or validation AI could mislead users about what the system has learned or forecast.

> **Repository evidence:** The tracked Python source contains CPR formulas, rolling indicators, fixed scoring, and backtests, but no LLM or machine-learning inference pipeline.

**Files.** `cpr_scoring.py`, `walk_forward_validation.py`, `signal_contract.py`.

**Recommendation.** Keep the reviewer and signal logic explicitly labelled as deterministic. If an LLM reviewer is added, keep it advisory, schema-validated, and separate from signal generation.

**Acceptance criteria.** Documentation distinguishes deterministic strategy rules, automation, and any future LLM-assisted code review.

### REPO-001: Keep generated market data out of default review prompts

**Category:** Repository hygiene  
**Severity:** Medium  
**Confidence:** High  
**Priority:** 3

**Impact.** Large historical CSV archives make code review, cloning, and LLM analysis expensive and can drown out source evidence.

> **Repository evidence:** The repository inventory contains 1664 generated files under cpr_output.

**Files.** `cpr_output/`, `.gitignore`, `eod_publish.py`.

**Recommendation.** Use a manifest plus sampled schemas in review tooling, and consider storing bulky archives in release artifacts or object storage while keeping reproducible fixtures in Git.

**Acceptance criteria.** The review agent reads schemas and metadata by default, never sends full generated archives to an analysis model, and CI remains reproducible from a small fixture.

## Suggested roadmap

### Immediate: protect correctness and trust

Adopt an explicit corporate-action and provider-provenance policy, preserve previous-period and no-look-ahead invariants in shared tests, and document conservative intrabar fill behavior with slippage, fees, and gap handling.

### Near term: improve repeatability and speed

Add a cache manifest and incremental acquisition path, benchmark 60- versus 252-session scans, add CI coverage/lint/type gates, and reduce the cost of generated archive growth.

### Longer term: improve research quality

Build fixture-driven out-of-sample evaluation with survivorship-aware universes, explicit liquidity and transaction-cost assumptions, and a comparison of vendor data. Keep any LLM use limited to advisory review and explanation rather than signal creation.

## Review boundaries

This agent does not fetch live market data, does not assess current securities, does not place trades, does not modify files, and does not guarantee strategy performance. Its findings are recommendations for engineering and research-process improvement, grounded in the repository snapshot.

## Machine-readable evidence

The companion JSON file contains the bounded inventory and structured findings for CI or later dashboards.
