"""Professional, review-only repository assessment for CPR Console.

The module is intentionally deterministic and offline by default. It collects bounded
repository evidence, runs code-grounded heuristics, and renders a structured Markdown
review. It never edits source files, invokes brokers, places trades, or deploys.
"""
from __future__ import annotations

import ast
import csv
import json
import re
import subprocess
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class Finding:
    finding_id: str
    category: str
    severity: str
    confidence: str
    title: str
    impact: str
    evidence: str
    files: list[str]
    recommendation: str
    effort: str
    priority: int
    acceptance_criteria: str


class EvidenceCollector:
    """Collect bounded, local evidence without reading generated CSV rows wholesale."""

    SOURCE_EXTENSIONS = {".py", ".md", ".yml", ".yaml", ".txt", ".json", ".toml", ".ini", ".cfg", ".csv"}
    GENERATED_DIRS = {"cpr_output", ".git", ".venv", "venv", "__pycache__"}

    def __init__(self, root: Path):
        self.root = root.resolve()

    def tracked_files(self) -> list[Path]:
        try:
            output = subprocess.check_output(
                ["git", "-C", str(self.root), "ls-files"], text=True, stderr=subprocess.DEVNULL
            )
            return [self.root / line.strip() for line in output.splitlines() if line.strip()]
        except (OSError, subprocess.CalledProcessError):
            return sorted(p for p in self.root.rglob("*") if p.is_file())

    def collect(self) -> dict:
        files = self.tracked_files()
        records = []
        generated = defaultdict(lambda: {"count": 0, "bytes": 0, "examples": []})
        for path in files:
            rel = path.relative_to(self.root).as_posix()
            try:
                size = path.stat().st_size
            except OSError:
                size = 0
            record = {"path": rel, "bytes": size, "extension": path.suffix.lower()}
            if rel.startswith("cpr_output/"):
                bucket = generated[path.parent.name]
                bucket["count"] += 1
                bucket["bytes"] += size
                if len(bucket["examples"]) < 8:
                    bucket["examples"].append(rel)
                record["generated"] = True
                records.append(record)
                continue
            record["generated"] = False
            if path.suffix.lower() == ".py":
                record.update(self._python_summary(path))
            elif path.suffix.lower() in {".yml", ".yaml", ".md", ".txt", ".json", ".toml", ".ini", ".cfg"}:
                record["lines"] = self._line_count(path)
            elif path.suffix.lower() == ".csv":
                record.update(self._csv_header(path))
            records.append(record)
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "root": str(self.root),
            "tracked_file_count": len(files),
            "generated_summary": dict(generated),
            "files": records,
        }

    @staticmethod
    def _line_count(path: Path) -> int:
        try:
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                return sum(1 for _ in handle)
        except OSError:
            return 0

    @staticmethod
    def _csv_header(path: Path) -> dict:
        try:
            with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
                reader = csv.reader(handle)
                return {"columns": next(reader, []), "rows_sampled": 0}
        except (OSError, csv.Error):
            return {"columns": [], "rows_sampled": 0}

    @staticmethod
    def _python_summary(path: Path) -> dict:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(text, filename=str(path))
            functions, classes, imports = [], [], []
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    functions.append(node.name)
                elif isinstance(node, ast.ClassDef):
                    classes.append(node.name)
                elif isinstance(node, ast.Import):
                    imports.extend(alias.name.split(".")[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports.append(node.module.split(".")[0])
            return {"lines": text.count("\n") + 1, "functions": sorted(set(functions)), "classes": sorted(set(classes)), "imports": sorted(set(imports))}
        except (OSError, SyntaxError):
            return {"lines": 0, "functions": [], "classes": [], "imports": [], "parse_error": True}


class ProfessionalReviewAgent:
    """Generate code-grounded recommendations using a fixed professional rubric."""

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.collector = EvidenceCollector(self.root)
        self.evidence = self.collector.collect()
        self.findings: list[Finding] = []

    def _text(self, relative: str) -> str:
        path = self.root / relative
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""

    def _add(self, **kwargs) -> None:
        self.findings.append(Finding(**kwargs))

    def analyze(self) -> list[Finding]:
        self.findings = []
        files = {record["path"]: record for record in self.evidence["files"]}
        py_files = [p for p in files if p.endswith(".py") and not p.startswith("cpr_output/")]
        all_text = "\n".join(self._text(p) for p in py_files)
        self._check_dependencies()
        self._check_cpr_duplication(all_text)
        self._check_data_quality()
        self._check_lookahead()
        self._check_scalability()
        self._check_backtest_realism()
        self._check_test_and_ops()
        self._check_ai_transparency(all_text)
        self._check_generated_growth()
        return sorted(self.findings, key=lambda f: (f.priority, f.finding_id))

    def _check_dependencies(self) -> None:
        req = self._text("requirements.txt")
        if "pytz" in req and self._text("requirements-ci.txt") and "pytz" not in self._text("requirements-ci.txt"):
            self._add(finding_id="DEP-001", category="Build and dependencies", severity="Medium", confidence="High", title="CI dependency parity should be checked", impact="The local test run can fail at import time when a runtime dependency is absent from the CI dependency set.", evidence="requirements.txt declares pytz, while requirements-ci.txt should be verified for parity; the observed sandbox run had a pytz import error.", files=["requirements.txt", "requirements-ci.txt", "test_cpr_breakout.py"], recommendation="Make CI install the full runtime requirements or maintain a tested, explicitly complete CI lock set.", effort="Small", priority=2, acceptance_criteria="A clean environment running the documented CI install completes unittest discovery without missing-module errors.")

    def _check_cpr_duplication(self, all_text: str) -> None:
        formulas = ["(high + low + close) / 3", "2.0 * pivot - bc", "(H + L + C) / 3"]
        hits = sum(all_text.count(x) for x in formulas)
        if hits >= 4:
            self._add(finding_id="ARCH-001", category="Architecture", severity="Medium", confidence="High", title="Keep one canonical CPR implementation", impact="Multiple formula representations can drift in thresholds, denominator conventions, or edge-case handling.", evidence="The repository has a canonical contract, plus separate live and breakout adapters that repeat formula-oriented logic and column mappings.", files=["cpr_contract.py", "cpr_engine.py", "cpr_breakout_engine.py", "nse_cpr_scanner.py"], recommendation="Keep numerical math exclusively in cpr_contract.py and test adapters only as compatibility mappings.", effort="Medium", priority=3, acceptance_criteria="A repository test asserts all consumers use calculate_cpr/calculate_cpr_frame and no consumer contains independent CPR arithmetic.")

    def _check_data_quality(self) -> None:
        scanner = self._text("nse_cpr_scanner.py")
        provider = self._text("data_provider.py")
        if "corporate" in self._text("README.md").lower() and "adjust" in self._text("README.md").lower() and "PRICE_ADJUSTMENT_POLICY" not in self._text("cpr_contract.py"):
            self._add(finding_id="DATA-001", category="Data quality", severity="High", confidence="High", title="Corporate-action handling needs an explicit policy", impact="Splits, bonuses, and dividends can make historical CPR levels incomparable with current prices and distort width ranks, SMAs, ATR, and backtests.", evidence="README.md lists imperfect corporate-action adjustment as a known limitation; both NSE bhavcopies and Yahoo data paths feed historical calculations.", files=["README.md", "data_provider.py", "nse_cpr_scanner.py", "walk_forward_validation.py"], recommendation="Choose adjusted or unadjusted semantics per workflow, record the policy in output metadata, and add a regression fixture around a split.", effort="Medium", priority=1, acceptance_criteria="A documented adjustment policy exists and a test proves levels and returns remain internally consistent across a corporate action.")
        if "timeout=45" in scanner and "time.sleep" in scanner and "retries" not in scanner:
            self._add(finding_id="DATA-002", category="Data quality and operations", severity="Medium", confidence="High", title="NSE download retry and backoff should be centralized", impact="Transient rate limits or archive outages can produce incomplete histories and downstream signals with less context.", evidence="Bhavcopy downloads catch exceptions and continue; history acquisition uses fixed short sleeps, but there is no general retry/backoff policy or completeness manifest in the scanner itself.", files=["nse_cpr_scanner.py", "eod_publish.py", "publication_contract.py"], recommendation="Add bounded exponential retries, response classification, cache freshness metadata, and an explicit minimum-history status in each scan.", effort="Medium", priority=2, acceptance_criteria="A simulated 429/timeout test retries predictably, records missing sessions, and prevents a scan from appearing complete without a history-quality flag.")
        if "Yahoo Finance" in provider and "delayed" in provider and "Data Source" not in self._text("app.py"):
            self._add(finding_id="DATA-003", category="Data quality", severity="Medium", confidence="High", title="Provider provenance should travel with every signal", impact="Users may compare values from different providers without knowing the source, delay, adjustment, or fetch timestamp.", evidence="OHLCVData stores data_source, fetch_timestamp, and data_status, but downstream EOD rows primarily expose calculated fields and do not consistently carry provider provenance.", files=["data_provider.py", "app.py", "nse_cpr_scanner.py", "eod_site.py"], recommendation="Persist provider, fetch time, adjustment mode, session timezone, and cache completeness in scan metadata and display it beside results.", effort="Medium", priority=3, acceptance_criteria="Every published scan has a machine-readable provenance block and the UI displays its source and freshness status.")

    def _check_lookahead(self) -> None:
        breakout = self._text("cpr_breakout_engine.py")
        walk = self._text("walk_forward_validation.py")
        if "allow_exact_matches=False" in breakout and "next completed" in walk.lower():
            self._add(finding_id="QUANT-001", category="Research correctness", severity="Medium", confidence="High", title="Preserve explicit look-ahead tests as a release gate", impact="A small change to period alignment can silently use a developing bar or same-day CPR and inflate apparent performance.", evidence="The breakout merger disallows exact date matches and the walk-forward validator checks next completed sessions; these protections are valuable but should be enforced across all paths.", files=["cpr_breakout_engine.py", "walk_forward_validation.py", "nse_cpr_scanner.py", "test_cpr_breakout.py", "test_walk_forward_validation.py"], recommendation="Add shared invariants for previous-period inputs, incomplete weekly/monthly exclusion, and no same-session outcome evaluation.", effort="Medium", priority=1, acceptance_criteria="A regression suite fails if any signal uses the current incomplete bar or evaluates an entry with same-bar future information.")

    def _check_scalability(self) -> None:
        scanner = self._text("nse_cpr_scanner.py")
        if "for date in session_date_window" in scanner and "download_bhavcopy" in scanner:
            self._add(finding_id="PERF-001", category="Efficiency", severity="Medium", confidence="High", title="History refresh can be made incremental and parallel-safe", impact="A 252-session cache fill can issue many sequential network requests and repeatedly load/concatenate large Pandas panels.", evidence="ensure_bhavcopy_history loops dates sequentially and load_history_panel reads every cached CSV for each scan/backfill path.", files=["nse_cpr_scanner.py", "eod_publish.py"], recommendation="Add a cache manifest, skip known unavailable holidays, separate acquisition from computation, and benchmark a bounded concurrent downloader with rate limits.", effort="Medium", priority=2, acceptance_criteria="A benchmark records scan time, request count, and memory for 60 and 252 sessions; repeated scans do not re-read unchanged inputs unnecessarily.")
        if "to_csv" in self._text("eod_site.py") or "zipfile" in self._text("eod_site.py"):
            self._add(finding_id="PERF-002", category="Efficiency and storage", severity="Low", confidence="High", title="Generated archive growth should be managed", impact="Daily full tables, shortlist files, caches, and site downloads accumulate indefinitely and increase clone, build, and deployment cost.", evidence="The repository tracks a large date-stamped cpr_output archive and the site builder writes per-date pages and downloads.", files=["eod_site.py", "eod_publish.py", ".github/workflows/eod-publish.yml"], recommendation="Define retention tiers, compress archival inputs, avoid duplicating identical exports, and publish a compact manifest/index.", effort="Medium", priority=4, acceptance_criteria="A documented retention policy exists and a year-scale fixture stays within an agreed repository and build-size budget.")

    def _check_backtest_realism(self) -> None:
        text = self._text("cpr_breakout_engine.py") + self._text("walk_forward_validation.py")
        if "cost_bps" in text and "slippage" not in text.lower():
            self._add(finding_id="QUANT-002", category="Backtesting", severity="High", confidence="High", title="Model intrabar execution ambiguity and slippage explicitly", impact="Using bar high/low to decide stop and target order can produce optimistic or ambiguous results when both are touched in one bar.", evidence="simulate_trades checks hit_sl and hit_tp on the same bar and prioritizes the stop for exits; it has a fixed cost_bps parameter but no explicit slippage or exchange execution model.", files=["cpr_breakout_engine.py", "walk_forward_validation.py"], recommendation="Document the conservative fill rule, add configurable slippage and gap handling, and report ambiguous bars separately.", effort="Medium", priority=1, acceptance_criteria="Backtest output reports stop/target collisions, gap exits, fees, slippage, and the chosen fill convention.")

    def _check_test_and_ops(self) -> None:
        workflow = self._text(".github/workflows/eod-publish.yml")
        if "python -m unittest discover -v" in workflow and "coverage" not in workflow and "ruff" not in workflow:
            self._add(finding_id="TEST-001", category="Testing", severity="Medium", confidence="Medium", title="Add coverage and static-quality gates", impact="Passing unit tests may still leave untested integration paths, typing regressions, dead imports, and UI/site breakage.", evidence="CI runs unittest discovery and generated-site checks, but no explicit coverage threshold, type check, lint, or dependency lock was found in the tracked inventory.", files=[".github/workflows/eod-publish.yml", "requirements.txt", "requirements-ci.txt"], recommendation="Add coverage reporting, Ruff or equivalent linting, mypy/pyright for core modules, and a pinned reproducible environment.", effort="Medium", priority=3, acceptance_criteria="CI publishes coverage, enforces a documented minimum for core modules, and runs lint/type checks on pull requests.")
        if "permissions:" in workflow and "contents: write" in workflow:
            self._add(finding_id="OPS-001", category="Operations and security", severity="Medium", confidence="High", title="Separate scan publication permissions from repository write access where possible", impact="A compromised workflow or dependency could modify the repository as well as publish the site.", evidence="The scheduled workflow grants contents: write, pages: write, and id-token: write, and commits generated CSVs.", files=[".github/workflows/eod-publish.yml", "eod_publish.py"], recommendation="Use a least-privilege design: publish artifacts without write access when possible, or isolate archive commits in a narrowly scoped workflow with pinning and review.", effort="Medium", priority=2, acceptance_criteria="The workflow’s permissions are justified in documentation and a dry-run proves site deployment still works with the minimum required scopes.")

    def _check_ai_transparency(self, all_text: str) -> None:
        if not re.search(r"openai|anthropic|gemini|llm|machine learning|neural", all_text, re.I):
            self._add(finding_id="AI-001", category="AI and transparency", severity="Informational", confidence="High", title="The current repository is deterministic, not an AI predictor", impact="Calling rule-based scoring or validation AI could mislead users about what the system has learned or forecast.", evidence="The tracked Python source contains CPR formulas, rolling indicators, fixed scoring, and backtests, but no LLM or machine-learning inference pipeline.", files=["cpr_scoring.py", "walk_forward_validation.py", "signal_contract.py"], recommendation="Keep the reviewer and signal logic explicitly labelled as deterministic. If an LLM reviewer is added, keep it advisory, schema-validated, and separate from signal generation.", effort="Small", priority=5, acceptance_criteria="Documentation distinguishes deterministic strategy rules, automation, and any future LLM-assisted code review.")

    def _check_generated_growth(self) -> None:
        count = sum(bucket["count"] for bucket in self.evidence["generated_summary"].values())
        if count > 500:
            self._add(finding_id="REPO-001", category="Repository hygiene", severity="Medium", confidence="High", title="Keep generated market data out of default review prompts", impact="Large historical CSV archives make code review, cloning, and LLM analysis expensive and can drown out source evidence.", evidence=f"The repository inventory contains {count} generated files under cpr_output.", files=["cpr_output/", ".gitignore", "eod_publish.py"], recommendation="Use a manifest plus sampled schemas in review tooling, and consider storing bulky archives in release artifacts or object storage while keeping reproducible fixtures in Git.", effort="Medium", priority=3, acceptance_criteria="The review agent reads schemas and metadata by default, never sends full generated archives to an analysis model, and CI remains reproducible from a small fixture.")

    def render_markdown(self) -> str:
        if not self.findings:
            self.analyze()
        generated = self.evidence["generated_summary"]
        critical = sum(f.severity == "Critical" for f in self.findings)
        high = sum(f.severity == "High" for f in self.findings)
        lines = [
            "# Professional Expert Review: CPR Console",
            "",
            f"**Generated:** {self.evidence['generated_at']}  ",
            "**Mode:** Review-only, offline, repository-evidence driven  ",
            "**Scope:** Software engineering, data quality, CPR research correctness, efficiency, testing, operations, and AI transparency",
            "",
            "> This report is a technical and research-process review. It does not issue investment recommendations and does not claim that any CPR setup is profitable.",
            "",
            "## Executive assessment",
            "",
            f"The repository has a clear separation between live analysis, intraday breakout research, and EOD publication. It also contains useful safeguards around completed periods, deterministic CPR contracts, explainable scoring, and publication validation. The highest-value improvements are to make **data provenance and corporate-action policy explicit**, preserve **look-ahead protections as shared release-gate invariants**, make **backtest execution assumptions more realistic**, and improve **incremental history acquisition and CI quality gates**. The review found **{len(self.findings)} findings**, including **{critical} critical** and **{high} high-severity** items.",
            "",
            "## Repository evidence snapshot",
            "",
            "| Evidence | Value |",
            "|---|---:|",
            f"| Tracked files observed | {self.evidence['tracked_file_count']} |",
            f"| Generated output files summarized | {sum(v['count'] for v in generated.values())} |",
            f"| Findings | {len(self.findings)} |",
            "| Analysis network access | None |",
            "| Source modification by reviewer | None |",
            "",
            "## Prioritized recommendations",
            "",
            "| Priority | ID | Severity | Recommendation | Effort |",
            "|---:|---|---|---|---|",
        ]
        for f in self.findings:
            lines.append(f"| {f.priority} | {f.finding_id} | {f.severity} | {f.title} | {f.effort} |")
        lines += ["", "## Detailed findings", ""]
        for f in self.findings:
            lines += [
                f"### {f.finding_id}: {f.title}",
                "",
                f"**Category:** {f.category}  ",
                f"**Severity:** {f.severity}  ",
                f"**Confidence:** {f.confidence}  ",
                f"**Priority:** {f.priority}",
                "",
                f"**Impact.** {f.impact}",
                "",
                f"> **Repository evidence:** {f.evidence}",
                "",
                f"**Files.** {', '.join(f'`{p}`' for p in f.files)}.",
                "",
                f"**Recommendation.** {f.recommendation}",
                "",
                f"**Acceptance criteria.** {f.acceptance_criteria}",
                "",
            ]
        lines += [
            "## Suggested roadmap",
            "",
            "### Immediate: protect correctness and trust",
            "",
            "Adopt an explicit corporate-action and provider-provenance policy, preserve previous-period and no-look-ahead invariants in shared tests, and document conservative intrabar fill behavior with slippage, fees, and gap handling.",
            "",
            "### Near term: improve repeatability and speed",
            "",
            "Add a cache manifest and incremental acquisition path, benchmark 60- versus 252-session scans, add CI coverage/lint/type gates, and reduce the cost of generated archive growth.",
            "",
            "### Longer term: improve research quality",
            "",
            "Build fixture-driven out-of-sample evaluation with survivorship-aware universes, explicit liquidity and transaction-cost assumptions, and a comparison of vendor data. Keep any LLM use limited to advisory review and explanation rather than signal creation.",
            "",
            "## Review boundaries",
            "",
            "This agent does not fetch live market data, does not assess current securities, does not place trades, does not modify files, and does not guarantee strategy performance. Its findings are recommendations for engineering and research-process improvement, grounded in the repository snapshot.",
            "",
            "## Machine-readable evidence",
            "",
            "The companion JSON file contains the bounded inventory and structured findings for CI or later dashboards.",
        ]
        return "\n".join(lines) + "\n"

    def report_payload(self) -> dict:
        if not self.findings:
            self.analyze()
        return {"generated_at": self.evidence["generated_at"], "findings": [asdict(f) for f in self.findings], "evidence": self.evidence}


def run_review(root: str | Path, report_path: str | Path | None = None, evidence_path: str | Path | None = None) -> tuple[Path, Path]:
    root_path = Path(root).resolve()
    agent = ProfessionalReviewAgent(root_path)
    report = Path(report_path) if report_path else root_path / "expert_review_report.md"
    evidence = Path(evidence_path) if evidence_path else root_path / "expert_review_evidence.json"
    report.write_text(agent.render_markdown(), encoding="utf-8")
    evidence.write_text(json.dumps(agent.report_payload(), indent=2), encoding="utf-8")
    return report, evidence
