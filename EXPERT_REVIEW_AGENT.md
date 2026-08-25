# Professional Expert Review Agent

`run_expert_review.py` runs a **review-only** assessment of the CPR Console repository. It evaluates software architecture, data quality, CPR/timeframe correctness, backtesting assumptions, efficiency, testing, CI/publication, security, and AI transparency.

## Run locally

From the repository root:

```bash
python3 run_expert_review.py .
```

The command writes:

- `expert_review_report.md`: readable Markdown findings.
- `expert_review_evidence.json`: bounded inventory and machine-readable findings.

Custom paths are supported:

```bash
python3 run_expert_review.py . \
  --report /tmp/cpr-review.md \
  --evidence /tmp/cpr-review.json
```

## Design guarantees

The first version is offline and deterministic. It reads tracked source/configuration files, summarizes generated CSVs without loading their full contents, and uses fixed checks to produce evidence-grounded recommendations. It does not download market data, invoke brokers, place trades, modify source code, deploy, or send alerts.

Every nontrivial finding includes a category, severity, confidence, impact, evidence statement, affected files, recommendation, estimated effort, priority, and acceptance criteria. Generated output directories are summarized by count, size, and a small set of example paths so they do not overwhelm a code review or a future LLM-assisted synthesis step.

## How to use the report

Start with Priority 1 findings, then review High-severity items. Treat the report as an engineering and research-process input, not as a claim that a strategy is profitable. Recommendations that change CPR thresholds, setup definitions, or backtest assumptions should be reviewed as research-methodology changes and validated with out-of-sample tests.

The agent also makes an explicit distinction between deterministic technical rules and AI. The current CPR Console code uses formulas, rolling indicators, fixed scores, and validation logic; it does not contain a machine-learning predictor. If a future LLM is added for narrative synthesis, it should remain advisory, schema-validated, bounded by repository evidence, and separate from signal generation.

## Test

Run the dedicated tests with:

```bash
python3 -m unittest test_expert_review_agent -v
```

The tests use a temporary fixture and do not require network access or a live market-data provider.
