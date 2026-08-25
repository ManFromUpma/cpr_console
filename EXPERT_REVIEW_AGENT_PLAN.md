# Plan: Add a Professional CPR Repository Review Agent

## Goal

Add a professional expertise agent to `cpr_console` that reviews the repository and produces practical, evidence-based recommendations for making the system more effective, efficient, reliable, maintainable, and useful for CPR research. The agent should review both software engineering and trading-system concerns without presenting its output as personalized investment advice.

## Intended outcome

The repository will contain a repeatable expert-review workflow that can be run against the current codebase and outputs a structured review report. The report will identify strengths, defects, risks, bottlenecks, duplicated logic, data-quality concerns, testing gaps, and prioritized improvements. It will distinguish facts observed in code from recommendations and will include file/line references wherever possible.

## Scope and key decisions

1. **Expert role.** Implement a professional reviewer persona combining senior Python/data-engineering expertise, quantitative research discipline, production reliability, and practical CPR/technical-analysis knowledge. The agent will critique the system rather than generate trading calls.

2. **Review target.** Cover the complete repository: live Streamlit console, intraday breakout engine, NSE EOD scanner, weekly/monthly aggregation, scoring, wide-CPR strategy, walk-forward validation, publication workflow, tests, configuration, symbol universes, generated-output conventions, and documentation.

3. **Review method.** Use deterministic repository evidence first: file inventory, imports, dependency configuration, function/class structure, tests, generated schemas, and execution paths. If an LLM is used to synthesize findings, it must receive bounded excerpts and a fixed review rubric, and its output must be validated against repository evidence. The implementation must not silently invent behavior that is absent from the code.

4. **Output format.** Produce Markdown by default, with sections for executive assessment, architecture, effectiveness, efficiency, correctness/data quality, finance-logic risks, testing, operations/deployment, security/privacy, prioritized roadmap, and file-level findings. Include severity, impact, evidence, recommendation, effort, and acceptance criteria in tables.

5. **Action boundary.** The first version is review-only: it generates recommendations and does not automatically edit source code, change trading rules, deploy, commit, or send alerts. Any future auto-fix mode must be explicit, opt-in, patch-based, and reviewed by a human.

6. **AI transparency.** The report must explicitly state whether the repository contains machine learning, deterministic scoring, external LLM calls, or only automation. Any LLM-assisted review must label generated synthesis separately from code-derived facts and record the model/configuration used.

## Implementation phases

### Phase 1: Establish the agent contract

Define the reviewer’s system prompt or role specification, review rubric, severity levels, evidence requirements, and report schema. Include separate lenses for software architecture, runtime efficiency, data correctness, CPR/timeframe logic, backtesting validity, and production publication safety.

### Phase 2: Build repository evidence collection

Create a small review package or command-line entrypoint that inventories tracked files while excluding or summarizing bulky generated CSVs. Collect source text, configuration, test names/results, dependency declarations, public function/class definitions, output schemas, and Git metadata. Add safeguards for secrets and untrusted file instructions. Make the evidence snapshot reproducible and timestamped.

### Phase 3: Implement expert analysis

Add the expert-review agent module. It should analyze evidence in bounded chunks, produce structured findings, deduplicate overlapping observations, and map each finding to one or more files and, where available, line ranges. Prefer structured JSON output internally so findings can be validated before rendering Markdown. Use a cost-aware model strategy: a capable reasoning model for synthesis, with programmatic checks for required fields and unsupported claims.

### Phase 4: Add review checks specific to this repository

The agent should explicitly evaluate:

- duplicated CPR formulas or inconsistent thresholds between `cpr_contract.py`, `cpr_engine.py`, `nse_cpr_scanner.py`, and `cpr_breakout_engine.py`;
- leakage or look-ahead risk in daily, weekly, monthly, breakout, backtest, and walk-forward logic;
- session timezone, holiday, incomplete-bar, and previous-period handling;
- data-provider reliability, Yahoo/NSE availability, rate limits, retries, stale data, corporate actions, and cache invalidation;
- performance of large-universe downloads, Pandas groupby/rolling operations, repeated scans, and static-site generation;
- maintainability across the three applications and duplicated presentation logic;
- signal score calibration, threshold documentation, liquidity assumptions, F&O classification, survivorship bias, slippage, and transaction-cost assumptions;
- unit, integration, regression, property-based, and end-to-end test coverage;
- CI publication, staging/atomic swap behavior, permissions, generated CSV growth, and failure recovery;
- absence or presence of ML/LLM logic and the risks of adding one to a deterministic trading research tool.

### Phase 5: Validate the reviewer

Add tests for evidence collection, schema validation, deterministic rule checks, malformed or missing files, large generated-output directories, and report rendering. Run the full test suite and record environmental failures separately from code failures. Include a sample review fixture so the agent can be tested without network access or live market data.

### Phase 6: Produce and document the first expert report

Run the agent against the repository and generate a dated Markdown report. Add usage documentation explaining how to run a review, how to interpret severity and confidence, how to refresh the evidence snapshot, and how humans should approve recommendations. Keep the report separate from the existing layman documentation.

## Proposed report structure

1. Executive verdict and top five priorities.
2. Repository map and runtime entrypoints.
3. Architecture and separation-of-concerns assessment.
4. CPR and timeframe correctness review.
5. Signal, scoring, breakout, and backtest assessment.
6. Data-quality and market-session review.
7. Efficiency and scalability review.
8. Testing and reproducibility review.
9. CI, publication, and operational reliability review.
10. Security, privacy, and dependency review.
11. AI/automation assessment.
12. Prioritized roadmap: immediate, near-term, and longer-term.
13. File-by-file findings.
14. Appendix containing evidence sources and assumptions.

## Prioritization model

Each finding should receive:

| Field | Meaning |
|---|---|
| Severity | Critical, High, Medium, Low, or Informational. |
| Confidence | High, Medium, or Low, based on direct repository evidence. |
| Impact | Effect on correctness, performance, maintainability, or user trust. |
| Effort | Small, Medium, or Large implementation estimate. |
| Priority | Recommended order based on risk reduction and effort. |
| Acceptance criteria | A testable condition showing the recommendation is complete. |

## Test and acceptance plan

The feature is complete when the reviewer can run offline against a checked-out repository, produce a valid structured result and readable Markdown report, cite evidence for every nontrivial finding, and avoid modifying source or external state. It must handle missing optional dependencies and generated-output directories gracefully. The repository test suite must pass after installing declared dependencies, and the new reviewer tests must cover malformed input, unsupported claims, duplicate findings, and report-schema failures.

The first review should be considered successful if it surfaces actionable, code-grounded recommendations in at least these areas: data/session correctness, look-ahead protection, duplicated logic, large-universe efficiency, backtest realism, test coverage, and publication reliability.

## Assumptions and open risks

- “Professional expertise agent” is assumed to mean an in-repository, repeatable expert-review capability rather than a human consultant or an automatic code-editing bot.
- LLM-assisted synthesis is optional but recommended only behind explicit configuration; deterministic checks remain authoritative.
- No broker execution, personalized advice, automated trading, or alert delivery is included.
- Current repository behavior may change as generated CSV archives grow; the evidence collector must summarize rather than load every generated row into an LLM prompt.
- Live NSE/Yahoo calls should not be required for the review test suite. Network-dependent checks should be optional and clearly labelled.
- Model IDs and request parameters must be discovered from the live configured catalog at implementation time rather than hardcoded from memory.
- Any recommendation involving changes to trading rules must preserve the distinction between improving software correctness and asserting that a strategy is profitable.

## Deliverables

- Expert-review agent module and command-line entrypoint.
- Review rubric/schema and bounded evidence collector.
- Tests and an offline sample fixture.
- Usage documentation.
- First dated professional review report with prioritized recommendations.
- No automatic source changes unless separately approved after review.
