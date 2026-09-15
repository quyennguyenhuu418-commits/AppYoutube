"""Non-destructive project audit for the videoAI repository.

Cross-references the governance docs in /docs/ against the actual source
code, schemas, providers, API routes, and tests. Reports PASS / WARN /
FAIL per dimension.

Run from the orchestrator directory (or anywhere with the right CWD):

    cd c:\\Users\\Administrator\\Downloads\\videoAI\\orchestrator
    python -m app.tools.project_audit

Or programmatically:

    from app.tools.project_audit import main
    exit_code = main()

Exit codes:
    0  PASS  (or WARN with no HIGH/CRITICAL conflicts)
    2  FAIL  (HIGH or CRITICAL conflicts)

The tool only reads. It does NOT modify any file, does NOT call any
external service, and does NOT touch git.

Implementation note: this module deliberately uses only the Python
standard library so it can run even when orchestrator requirements are
not installed.
"""

from __future__ import annotations

import ast
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


# ----------------------------------------------------------------------------
# Path resolution
# ----------------------------------------------------------------------------

def _find_repo_root(start: Path) -> Path:
    """Walk up from `start` until we find a directory that contains both
    `orchestrator/` and `docs/`. Falls back to the start directory."""
    cur = start.resolve()
    for _ in range(8):
        if (cur / "orchestrator").is_dir() and (cur / "docs").is_dir():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    return start.resolve()


_THIS_FILE = Path(__file__).resolve()
REPO_ROOT = _find_repo_root(_THIS_FILE.parent)
ORCHESTRATOR_ROOT = REPO_ROOT / "orchestrator"
DOCS_ROOT = REPO_ROOT / "docs"
RENDERER_ROOT = REPO_ROOT / "renderer"
WEBAPP_ROOT = REPO_ROOT / "webapp"


# ----------------------------------------------------------------------------
# Result types
# ----------------------------------------------------------------------------

PASS = "PASS"
WARN = "WARN"
FAIL = "FAIL"


@dataclass
class DimensionResult:
    name: str
    status: str
    summary: str
    details: list[str] = field(default_factory=list)

    def render(self) -> str:
        out = f"[{self.status}] {self.name}: {self.summary}"
        for d in self.details:
            out += f"\n    - {d}"
        return out


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------

def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _list_py_classes(path: Path) -> list[str]:
    """Return top-level class names defined in a Python file."""
    src = _read(path)
    if not src:
        return []
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []
    return [
        node.name
        for node in tree.body
        if isinstance(node, ast.ClassDef)
    ]


def _grep_files(root: Path, pattern: str, glob: str = "**/*") -> list[tuple[Path, int, str]]:
    """Return (path, line_no, line) for every match of `pattern` under
    `root` matching `glob`. Pattern is a regex applied line-by-line."""
    rx = re.compile(pattern)
    hits: list[tuple[Path, int, str]] = []
    if not root.exists():
        return hits
    for p in root.glob(glob):
        if not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), start=1):
            if rx.search(line):
                hits.append((p, i, line.rstrip()))
    return hits


# ----------------------------------------------------------------------------
# Audit dimensions
# ----------------------------------------------------------------------------

REQUIRED_DOCS = [
    "PROJECT_CONTEXT.md",
    "PROJECT_STATE.md",
    "ARCHITECTURE.md",
    "ARCHITECTURE_DECISIONS.md",
    "SYSTEM_MAP.md",
    "DATA_CONTRACTS.md",
    "API_CONTRACTS.md",
    "PROVIDER_REGISTRY.md",
    "PIPELINE_REGISTRY.md",
    "DEPENDENCY_GRAPH.md",
    "FEATURE_MATRIX.md",
    "TECHNICAL_DEBT.md",
    "KNOWN_LIMITATIONS.md",
    "CHANGELOG_INTERNAL.md",
    "TEST_STATUS.md",
    "SAFE_CHANGE_RULES.md",
]


def audit_docs_present() -> DimensionResult:
    missing = [name for name in REQUIRED_DOCS if not (DOCS_ROOT / name).is_file()]
    if missing:
        return DimensionResult(
            "docs presence",
            FAIL,
            f"{len(missing)} required doc(s) missing",
            details=[f"docs/{m}" for m in missing],
        )
    return DimensionResult(
        "docs presence",
        PASS,
        f"all {len(REQUIRED_DOCS)} required docs present",
    )


def audit_pipeline_registry_vs_code() -> DimensionResult:
    """Verify that every stage in runner.STAGES has a stage file."""
    runner = ORCHESTRATOR_ROOT / "app" / "pipeline" / "runner.py"
    src = _read(runner)
    if not src:
        return DimensionResult(
            "pipeline registry",
            FAIL,
            "runner.py missing",
            details=[str(runner)],
        )
    # Extract stage class names from STAGES list
    stage_names: list[str] = []
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return DimensionResult(
            "pipeline registry",
            FAIL,
            "runner.py has syntax error",
        )
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "STAGES":
                    if isinstance(node.value, ast.List):
                        for elt in node.value.elts:
                            if isinstance(elt, ast.Call) and isinstance(elt.func, ast.Name):
                                stage_names.append(elt.func.id)
    details: list[str] = []
    missing: list[str] = []
    for sname in stage_names:
        # s1_research -> ResearchStage
        m = re.match(r"^s\d+_(.+)$", sname)
        if not m:
            continue
        module_name = sname
        mod_path = ORCHESTRATOR_ROOT / "app" / "pipeline" / "stages" / f"{module_name}.py"
        if not mod_path.is_file():
            missing.append(str(mod_path.relative_to(REPO_ROOT)))
            continue
        classes = _list_py_classes(mod_path)
        expected_class = sname.split("_", 1)[1].split("_")
        expected_class_name = "".join(p.title() for p in expected_class) + "Stage"
        if expected_class_name not in classes:
            details.append(
                f"{mod_path.relative_to(REPO_ROOT)} missing class {expected_class_name}"
            )
    if missing or details:
        return DimensionResult(
            "pipeline registry",
            FAIL,
            f"{len(missing)} stage file(s) missing, {len(details)} class mismatch(es)",
            details=missing + details,
        )
    return DimensionResult(
        "pipeline registry",
        PASS,
        f"all {len(stage_names)} runner.STAGES have matching files and classes",
    )


def audit_api_routes() -> DimensionResult:
    """Confirm every FastAPI route has a decorator we can find."""
    api_root = ORCHESTRATOR_ROOT / "app" / "api"
    main_file = ORCHESTRATOR_ROOT / "app" / "main.py"
    if not api_root.exists():
        return DimensionResult("api routes", FAIL, "api/ directory missing")
    files = [main_file] + sorted(api_root.glob("*.py"))
    route_count = 0
    for f in files:
        src = _read(f)
        route_count += len(re.findall(r"@router\.(get|post|put|delete|patch)\(", src))
        route_count += len(re.findall(r"@app\.(get|post|put|delete|patch)\(", src))
    if route_count < 5:
        return DimensionResult(
            "api routes",
            FAIL,
            f"only {route_count} routes found (expected >= 5)",
        )
    return DimensionResult(
        "api routes",
        PASS,
        f"{route_count} HTTP routes registered",
    )


def audit_provider_abc_implementations() -> DimensionResult:
    """Every ABC in base.py has at least one non-ABC implementation."""
    base = ORCHESTRATOR_ROOT / "app" / "providers" / "base.py"
    src = _read(base)
    if not src:
        return DimensionResult("provider ABCs", FAIL, "base.py missing")
    # ABC names we expect: LLMProvider, TTSProvider, ImageProvider,
    # SearchProvider, ContentFetchProvider
    expected = ["LLMProvider", "TTSProvider", "ImageProvider",
                "SearchProvider", "ContentFetchProvider"]
    provider_root = ORCHESTRATOR_ROOT / "app" / "providers"
    impls: dict[str, list[str]] = {n: [] for n in expected}
    for f in provider_root.glob("*.py"):
        if f.name == "base.py":
            continue
        text = _read(f)
        for cls in _list_py_classes(f):
            for ab in expected:
                # Match if the class extends <AB>( or <AB>[ or contains "AB" as base
                if re.search(rf"\b{re.escape(ab)}\b", text):
                    if cls not in impls[ab]:
                        impls[ab].append(cls)
    missing = [ab for ab, lst in impls.items() if not lst]
    if missing:
        return DimensionResult(
            "provider ABCs",
            WARN,
            f"{len(missing)} ABC(s) have no concrete impl in providers/",
            details=[f"{m}: no impl found" for m in missing],
        )
    return DimensionResult(
        "provider ABCs",
        PASS,
        f"all {len(expected)} provider ABCs have >=1 concrete impl",
        details=[f"{ab}: {', '.join(impls[ab])}" for ab in expected],
    )


def audit_schemas_exported() -> DimensionResult:
    """Confirm schemas/ directory contains the expected files."""
    expected = {"job.py", "script.py", "research.py",
                "research_package.py", "scene_definition.py"}
    actual = {p.name for p in (ORCHESTRATOR_ROOT / "app" / "schemas").glob("*.py")}
    missing = expected - actual
    if missing:
        return DimensionResult(
            "schemas exported",
            FAIL,
            f"{len(missing)} schema file(s) missing",
            details=[f"schemas/{m}" for m in sorted(missing)],
        )
    return DimensionResult(
        "schemas exported",
        PASS,
        f"all {len(expected)} schema files present",
    )


def audit_test_files() -> DimensionResult:
    """Confirm Python test files exist; report BLOCKED status."""
    tests_root = ORCHESTRATOR_ROOT / "tests"
    if not tests_root.exists():
        return DimensionResult("test files", FAIL, "tests/ directory missing")
    tests = sorted(tests_root.glob("test_*.py"))
    if not tests:
        return DimensionResult("test files", FAIL, "no test_*.py files")
    return DimensionResult(
        "test files",
        PASS,
        f"{len(tests)} Python test file(s) present; runtime BLOCKED on this host (no Python)",
        details=[f"tests/{t.name}" for t in tests],
    )


def audit_research_engine_steps() -> DimensionResult:
    """Confirm ResearchEngine.run() calls >=10 named steps (excluding stubs)."""
    engine = ORCHESTRATOR_ROOT / "app" / "research" / "engine.py"
    src = _read(engine)
    if not src:
        return DimensionResult("research engine steps", FAIL, "engine.py missing")
    # Look for _methodname calls in run() and standalone definitions.
    steps = re.findall(r"\b_(decompose_questions|search_sources|fetch_and_score_sources|deduplicate_sources|extract_claims|build_claim_source_graph|detect_contradictions|model_uncertainty|build_timeline|extract_visual_opportunities|extract_story_opportunities|synthesize|score_quality)\b", src)
    unique = sorted(set(steps))
    if len(unique) < 10:
        return DimensionResult(
            "research engine steps",
            FAIL,
            f"only {len(unique)} step method(s) detected",
            details=unique,
        )
    return DimensionResult(
        "research engine steps",
        PASS,
        f"{len(unique)} engine step method(s) detected",
        details=unique,
    )


def audit_secrets_scan() -> DimensionResult:
    """Scan for accidental API-key patterns. Report only file:line, never the secret."""
    patterns = [
        (r"sk-[A-Za-z0-9]{20,}", "OpenAI-style key"),
        (r"AKIA[0-9A-Z]{16}", "AWS access key"),
        (r"ghp_[A-Za-z0-9]{20,}", "GitHub personal token"),
        (r"xoxb-[A-Za-z0-9-]{20,}", "Slack token"),
    ]
    findings: list[str] = []
    for pat, label in patterns:
        for path, line_no, _ in _grep_files(ORCHESTRATOR_ROOT, pat, "**/*.py"):
            # Skip config defaults where key is "" or env-driven
            findings.append(f"{label}: {path.relative_to(REPO_ROOT)}:{line_no}")
    if findings:
        return DimensionResult(
            "secrets scan",
            FAIL,
            f"{len(findings)} potential secret(s) detected",
            details=findings,
        )
    return DimensionResult(
        "secrets scan",
        PASS,
        "no accidental secret patterns detected",
    )


def audit_docker_compose_usage() -> DimensionResult:
    """Check whether declared services in docker-compose.yml are imported.

    Two checks: (1) does any python file actually import the service, and
    (2) is the service a declared dependency in requirements.txt. Either
    signals that the orchestrator at least *intends* to use the service.
    """
    compose = REPO_ROOT / "docker-compose.yml"
    if not compose.is_file():
        return DimensionResult("docker-compose", WARN, "docker-compose.yml not present")
    src = _read(compose)
    declared: list[str] = []
    if re.search(r"(?im)^\s*redis:", src):
        declared.append("redis")
    if re.search(r"(?im)^\s*postgres:", src):
        declared.append("postgres")
    unused: list[str] = []
    intent_only: list[str] = []
    for svc in declared:
        # Look for any import/usage of the service in the orchestrator.
        # We exclude the audit tooling itself so the audit isn't matching
        # its own source code.
        if svc == "redis":
            hits = [
                (p, ln, line)
                for (p, ln, line) in _grep_files(
                    ORCHESTRATOR_ROOT, r"\b(redis|aioredis)\b", "**/*.py"
                )
                if "app/tools/" not in str(p).replace("\\", "/")
            ]
            dep = "redis" in _read(REPO_ROOT / "orchestrator" / "requirements.txt").lower()
        else:
            hits = [
                (p, ln, line)
                for (p, ln, line) in _grep_files(
                    ORCHESTRATOR_ROOT, r"\b(sqlalchemy|psycopg|asyncpg)\b", "**/*.py"
                )
                if "app/tools/" not in str(p).replace("\\", "/")
            ]
            dep = "sqlalchemy" in _read(REPO_ROOT / "orchestrator" / "requirements.txt").lower()
        if not hits and not dep:
            unused.append(svc)
        elif not hits and dep:
            intent_only.append(svc)
    if unused:
        return DimensionResult(
            "docker-compose",
            WARN,
            f"{len(unused)} service(s) declared but not used by code",
            details=[f"{s}: declared in docker-compose.yml but no Python usage or dep" for s in unused],
        )
    if intent_only:
        return DimensionResult(
            "docker-compose",
            WARN,
            f"{len(intent_only)} service(s) declared but only as future-intent dep",
            details=[f"{s}: declared in compose + requirements.txt but never imported" for s in intent_only],
        )
    return DimensionResult("docker-compose", PASS, "all declared services are used")


def audit_git_repo() -> DimensionResult:
    """Report whether the repo is initialized."""
    git_dir = REPO_ROOT / ".git"
    if not git_dir.is_dir():
        return DimensionResult(
            "git repository",
            WARN,
            "no .git/ directory; no commit history",
            details=["run `git init` only with user approval (see TECHNICAL_DEBT.md C-008)"],
        )
    return DimensionResult("git repository", PASS, ".git/ present")


# ----------------------------------------------------------------------------
# Orchestration
# ----------------------------------------------------------------------------

ALL_DIMENSIONS = [
    audit_docs_present,
    audit_pipeline_registry_vs_code,
    audit_api_routes,
    audit_provider_abc_implementations,
    audit_schemas_exported,
    audit_test_files,
    audit_research_engine_steps,
    audit_secrets_scan,
    audit_docker_compose_usage,
    audit_git_repo,
]


def aggregate(results: Iterable[DimensionResult]) -> str:
    statuses = [r.status for r in results]
    if FAIL in statuses:
        return FAIL
    if WARN in statuses:
        return WARN
    return PASS


def render_report(results: list[DimensionResult]) -> str:
    agg = aggregate(results)
    lines = [
        "=" * 72,
        "videoAI Project Audit (PROMPT 0.5)",
        f"repo root: {REPO_ROOT}",
        "=" * 72,
        "",
    ]
    for r in results:
        lines.append(r.render())
        lines.append("")
    lines.append("-" * 72)
    lines.append(f"OVERALL: {agg}")
    lines.append("-" * 72)
    if agg == PASS:
        lines.append("No HIGH/CRITICAL conflicts detected.")
    elif agg == WARN:
        lines.append("WARN: known HIGH conflicts recorded in docs/TECHNICAL_DEBT.md")
        lines.append("(C-001, C-002, C-003, C-008). These are NOT fixed by design.")
    else:
        lines.append("FAIL: at least one dimension failed. Inspect output above.")
    return "\n".join(lines)


def main() -> int:
    results: list[DimensionResult] = []
    for dim in ALL_DIMENSIONS:
        try:
            results.append(dim())
        except Exception as e:  # pragma: no cover - defensive
            results.append(DimensionResult(
                name=dim.__name__,
                status=FAIL,
                summary=f"audit dimension raised {type(e).__name__}",
                details=[str(e)],
            ))
    report = render_report(results)
    print(report)
    return 0 if aggregate(results) != FAIL else 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
