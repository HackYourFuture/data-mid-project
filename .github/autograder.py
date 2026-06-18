#!/usr/bin/env python3
"""
Week 7 autograder for the HackYourFuture data-mid-project.

Called by .github/workflows/autograder.yml after pytest has already run.
Reads PYTEST_EXIT_CODE from the environment to know whether tests passed.

Output:
  - ✅/❌ per check printed to stdout
  - Markdown summary written to $GITHUB_STEP_SUMMARY (if set)
  - Exit 1 when any *critical* check fails; exit 0 otherwise
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple

# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

class Result:
    def __init__(self, label: str, passed: bool, critical: bool, detail: str = ""):
        self.label = label
        self.passed = passed
        self.critical = critical
        self.detail = detail

    @property
    def icon(self) -> str:
        return "✅" if self.passed else "❌"

    def __str__(self) -> str:
        suffix = f"  ({self.detail})" if self.detail else ""
        crit_tag = " [CRITICAL]" if not self.passed and self.critical else ""
        return f"{self.icon} {self.label}{crit_tag}{suffix}"


Results = List[Result]


def ok(label: str, critical: bool = False, detail: str = "") -> Result:
    return Result(label, True, critical, detail)


def fail(label: str, critical: bool = False, detail: str = "") -> Result:
    return Result(label, False, critical, detail)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ROOT = Path(".")


def file_exists(path: str) -> bool:
    return (ROOT / path).exists()


def grep_src(pattern: str, *, invert: bool = False) -> Optional[Tuple[str, ...]]:
    """
    Search src/ for *pattern*.
    Returns a tuple of matching lines, or None if the directory is missing.
    When invert=True, returns lines that do NOT match (grep -v style).
    """
    src_dir = ROOT / "src"
    if not src_dir.is_dir():
        return None
    matches = []
    regex = re.compile(pattern)
    for py_file in src_dir.rglob("*.py"):
        for line in py_file.read_text(errors="replace").splitlines():
            hit = bool(regex.search(line))
            if (hit and not invert) or (not hit and invert):
                matches.append(line)
    return tuple(matches)


def count_test_functions() -> int:
    """Count `def test_` definitions across all test files."""
    count = 0
    tests_dir = ROOT / "tests"
    if not tests_dir.is_dir():
        return 0
    for py_file in tests_dir.rglob("test_*.py"):
        for line in py_file.read_text(errors="replace").splitlines():
            if re.match(r"\s*def test_", line):
                count += 1
    return count


def readme_is_filled_in() -> bool:
    """Return True if README.md has more than 5 non-heading lines."""
    readme = ROOT / "README.md"
    if not readme.exists():
        return False
    non_heading = [
        line for line in readme.read_text(errors="replace").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    return len(non_heading) > 5


def ai_assist_is_filled_in() -> bool:
    """
    Return True if AI_ASSIST.md contains at least one 'What I asked:' entry
    beyond the default stub placeholder.
    """
    ai_file = ROOT / "AI_ASSIST.md"
    if not ai_file.exists():
        return False
    content = ai_file.read_text(errors="replace")
    # The stub contains a single placeholder like "What I asked: <your question here>"
    # A real entry would be "What I asked: " followed by actual text (not angle-bracket placeholder)
    entries = re.findall(r"What I asked:\s*(.+)", content)
    real_entries = [e for e in entries if not e.strip().startswith("<")]
    return len(real_entries) >= 1


def readme_has_architecture_overview() -> bool:
    """
    Return True if README.md contains an architecture overview or data-flow description.
    Accepts: a mermaid code block, an ASCII diagram (arrows/boxes), or a paragraph
    containing 'architecture', 'data flow', or 'pipeline' followed by directional words.
    """
    readme = ROOT / "README.md"
    if not readme.exists():
        return False
    content = readme.read_text(errors="replace")
    # mermaid block
    if "```mermaid" in content:
        return True
    # ASCII diagram indicators (arrows between words)
    if re.search(r"[→←↓↑]|->|-->|\|.*\|", content):
        return True
    # Explicit architecture/flow section heading or paragraph
    if re.search(r"(?i)(##\s*(architecture|data.?flow|pipeline.?flow)|architecture\s*overview)", content):
        return True
    return False


def env_file_not_committed() -> bool:
    """Return True if .env is NOT present in the working tree (not committed)."""
    return not (ROOT / ".env").exists()


def env_example_has_empty_secrets() -> bool:
    """
    .env.example lines for POSTGRES_URL and AZURE_STORAGE_CONNECTION_STRING
    must have empty (or absent) values.
    """
    env_example = ROOT / ".env.example"
    if not env_example.exists():
        return True  # checked separately
    for line in env_example.read_text(errors="replace").splitlines():
        for key in ("POSTGRES_URL", "AZURE_STORAGE_CONNECTION_STRING"):
            if line.startswith(f"{key}="):
                value = line[len(f"{key}="):].strip()
                # Strip surrounding quotes
                value = value.strip("\"'")
                if value:
                    return False
    return True


def no_hardcoded_secrets() -> Tuple[bool, str]:
    """
    Scan src/ for patterns that look like hardcoded credentials.
    Returns (clean, detail_string).
    """
    patterns = [
        r"postgres://\w+:\w+@",           # postgres DSN with credentials
        r"DefaultEndpointsProtocol=https;AccountKey=",  # Azure storage conn string
        r"AccountKey=[A-Za-z0-9+/]{40,}",  # raw account key
    ]
    hits = []
    src_dir = ROOT / "src"
    if not src_dir.is_dir():
        return True, ""
    for py_file in src_dir.rglob("*.py"):
        text = py_file.read_text(errors="replace")
        for pat in patterns:
            if re.search(pat, text):
                hits.append(f"{py_file}: matched '{pat}'")
    if hits:
        return False, "; ".join(hits[:3])
    return True, ""


def no_bare_print_in_src() -> bool:
    """
    Return True if src/ contains no bare `print(` calls.
    We allow `print` in tests but not in src/.
    """
    src_dir = ROOT / "src"
    if not src_dir.is_dir():
        return True
    for py_file in src_dir.rglob("*.py"):
        for line in py_file.read_text(errors="replace").splitlines():
            stripped = line.lstrip()
            # Allow commented lines and logging.info style
            if stripped.startswith("#"):
                continue
            if re.search(r"\bprint\s*\(", line):
                return False
    return True


def merge_commit_count() -> int:
    """Count merge commits on main using git log."""
    try:
        result = subprocess.run(
            ["git", "log", "--merges", "main", "--oneline"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        lines = [l for l in result.stdout.splitlines() if l.strip()]
        return len(lines)
    except Exception:
        return 0


def has_non_autograder_workflow() -> bool:
    """Return True if .github/workflows/ has at least one yml that isn't autograder.yml."""
    wf_dir = ROOT / ".github" / "workflows"
    if not wf_dir.is_dir():
        return False
    ymls = [
        f for f in wf_dir.glob("*.yml")
        if f.name != "autograder.yml"
    ]
    return len(ymls) > 0


# ---------------------------------------------------------------------------
# Check runners
# ---------------------------------------------------------------------------

def check_file_structure() -> Results:
    results = []

    required_files = [
        ("Dockerfile", True),
        ("pyproject.toml", True),
        ("uv.lock", False),
        (".env.example", False),
        (".gitignore", False),
        ("README.md", False),
        ("AI_ASSIST.md", False),
        ("conftest.py", False),
        ("src/pipeline.py", False),
        ("src/models.py", False),
        ("src/storage.py", False),
    ]

    for path, critical in required_files:
        label = f"File exists: {path}"
        if file_exists(path):
            results.append(ok(label, critical))
        else:
            results.append(fail(label, critical))

    # tests/ has at least one test_*.py
    tests_dir = ROOT / "tests"
    has_test_file = tests_dir.is_dir() and bool(list(tests_dir.rglob("test_*.py")))
    if has_test_file:
        results.append(ok("tests/ has at least one test_*.py"))
    else:
        results.append(fail("tests/ has at least one test_*.py"))

    # README filled in
    if readme_is_filled_in():
        results.append(ok("README.md has been filled in (>5 non-heading lines)"))
    else:
        results.append(fail("README.md has been filled in (>5 non-heading lines)"))

    # AI_ASSIST filled in
    if ai_assist_is_filled_in():
        results.append(ok("AI_ASSIST.md has at least one real 'What I asked:' entry"))
    else:
        results.append(fail("AI_ASSIST.md has at least one real 'What I asked:' entry"))

    # Architecture overview in README (diagram, data-flow description, or mermaid block)
    if readme_has_architecture_overview():
        results.append(ok("README.md contains an architecture overview or data-flow description"))
    else:
        results.append(fail("README.md contains an architecture overview or data-flow description",
                            detail="add a diagram (mermaid/ASCII) or a short description of the data flow"))

    return results


def check_code_patterns() -> Results:
    results = []

    # HTTP library: proxy for "uses a live external API"
    http_lines = grep_src(r"import requests|from requests|import httpx|from httpx|import aiohttp|from aiohttp")
    if http_lines is None:
        results.append(fail("src/ exists", critical=True))
    elif http_lines:
        results.append(ok("HTTP library imported in src/ (requests / httpx / aiohttp)", critical=True))
    else:
        results.append(fail("HTTP library imported in src/ (requests / httpx / aiohttp)", critical=True,
                            detail="no requests/httpx/aiohttp found; pipeline must use a live external API"))

    # pandas import
    pandas_lines = grep_src(r"import pandas|from pandas")
    if pandas_lines:
        results.append(ok("pandas imported in src/", critical=True))
    else:
        results.append(fail("pandas imported in src/", critical=True))

    # pandas real transform work (beyond a bare DataFrame constructor)
    transform_lines = grep_src(
        r"pd\.to_datetime|\.dt\.|\.groupby\(|\.agg\(|\.merge\(|\.assign\(|\.rename\(|\.fillna\(|\.dropna\("
    )
    if transform_lines:
        results.append(ok("pandas transform operations present (groupby/agg/to_datetime/etc.)", critical=True))
    else:
        results.append(fail(
            "pandas transform operations present (groupby/agg/to_datetime/etc.)",
            critical=True,
            detail="wrapping records in pd.DataFrame() without transforming doesn't count",
        ))

    # pydantic / BaseModel
    pydantic_lines = grep_src(r"BaseModel|import pydantic|from pydantic")
    if pydantic_lines:
        results.append(ok("Pydantic / BaseModel used in src/", critical=True))
    else:
        results.append(fail("Pydantic / BaseModel used in src/", critical=True))

    # sys.exit (fail-fast on missing env vars)
    sys_exit_lines = grep_src(r"\bsys\.exit\b")
    if sys_exit_lines:
        results.append(ok("sys.exit present in src/ (fail-fast pattern)"))
    else:
        results.append(fail("sys.exit present in src/ (fail-fast pattern)"))

    # no bare print() in src/
    if no_bare_print_in_src():
        results.append(ok("No bare print() in src/ (logging used instead)"))
    else:
        results.append(fail("No bare print() in src/ (logging used instead)"))

    return results


def check_security() -> Results:
    results = []

    # .env not committed
    if env_file_not_committed():
        results.append(ok(".env not committed to the repo", critical=True))
    else:
        results.append(fail(".env not committed to the repo", critical=True,
                            detail=".env file found in working tree"))

    # .env.example has empty secret values
    if env_example_has_empty_secrets():
        results.append(ok(".env.example has empty values for secret keys"))
    else:
        results.append(fail(".env.example has empty values for secret keys",
                            detail="POSTGRES_URL or AZURE_STORAGE_CONNECTION_STRING appear to have values"))

    # no hardcoded secrets in src/
    clean, detail = no_hardcoded_secrets()
    if clean:
        results.append(ok("No hardcoded secrets in src/", critical=True))
    else:
        results.append(fail("No hardcoded secrets in src/", critical=True, detail=detail))

    return results


def check_tests(pytest_exit_code: int) -> Results:
    results = []

    fn_count = count_test_functions()
    if fn_count >= 2:
        results.append(ok(f"At least 2 test functions found ({fn_count} total)"))
    else:
        results.append(fail(f"At least 2 test functions found ({fn_count} found)"))

    if pytest_exit_code == 0:
        results.append(ok("pytest passes", critical=True))
    else:
        results.append(fail("pytest passes", critical=True,
                            detail=f"pytest exited with code {pytest_exit_code}"))

    return results


def check_cicd() -> Results:
    results = []

    if has_non_autograder_workflow():
        results.append(ok(".github/workflows/ has a student-authored workflow"))
    else:
        results.append(fail(".github/workflows/ has a student-authored workflow"))

    return results


def check_git_workflow() -> Results:
    results = []

    merge_count = merge_commit_count()
    if merge_count >= 3:
        results.append(ok(f"At least 3 merge commits on main ({merge_count} found)"))
    else:
        results.append(fail(f"At least 3 merge commits on main ({merge_count} found)",
                            detail="expected pull-request-based workflow with feature branches"))

    return results


# ---------------------------------------------------------------------------
# Manual checklist (printed but never fails the grade)
# ---------------------------------------------------------------------------

MANUAL_CHECKS = [
    "Docker image builds and runs locally",
    "Azure Container Registry image exists with a tagged version",
    "Container App Job created in the shared environment",
    "Job ran successfully (execution history shows Succeeded)",
    "Job output verifiable (rows in Postgres or blobs in storage)",
    "Job uses --registry-server, --replica-timeout 300, --env-vars",
    "Container App Job deleted after evaluation",
]


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def print_section(title: str, results: Results) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")
    for r in results:
        print(r)


def build_markdown_summary(all_results: Results, score: int, total: int) -> str:
    lines = [
        "# Week 7 Autograder Results",
        "",
        f"**Score: {score}/{total} automated checks passed**",
        "",
    ]

    sections = {
        "File structure": [],
        "Code patterns": [],
        "Security": [],
        "Tests": [],
        "CI/CD": [],
        "Git workflow": [],
    }

    # We re-use the grouped results passed in by the caller via all_results.
    # Since we don't have section metadata here, we print a flat table.
    lines.append("| # | Check | Result |")
    lines.append("|---|-------|--------|")
    for i, r in enumerate(all_results, 1):
        status = "✅ Pass" if r.passed else "❌ Fail"
        crit = " *(critical)*" if r.critical and not r.passed else ""
        detail = f"<br><sub>{r.detail}</sub>" if r.detail else ""
        lines.append(f"| {i} | {r.label}{crit} | {status}{detail} |")

    lines += [
        "",
        "## Manual checks (teacher review required)",
        "",
    ]
    for check in MANUAL_CHECKS:
        lines.append(f"- [ ] {check}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def is_template_stub() -> bool:
    """Return True when running inside the unmodified starter template.

    The template's src/pipeline.py contains a placeholder comment that
    students are expected to replace. If it's still there, this is the
    template repo, not a student submission. Skip grading.
    """
    pipeline = ROOT / "src" / "pipeline.py"
    if not pipeline.exists():
        return False
    return "# TODO: Replace with your API call" in pipeline.read_text(errors="replace")


def main() -> int:
    pytest_exit_code_str = os.environ.get("PYTEST_EXIT_CODE", "1")
    try:
        pytest_exit_code = int(pytest_exit_code_str)
    except ValueError:
        pytest_exit_code = 1

    print("=" * 60)
    print("  HackYourFuture: Week 7 Autograder")
    print("=" * 60)

    if is_template_stub():
        print("\n  Template repo detected: skipping grading.")
        print("  Replace the stubs in src/ before the autograder runs.")
        print("=" * 60)
        return 0

    grouped: List[Tuple[str, Results]] = [
        ("File structure", check_file_structure()),
        ("Code patterns", check_code_patterns()),
        ("Security", check_security()),
        ("Tests", check_tests(pytest_exit_code)),
        ("CI/CD", check_cicd()),
        ("Git workflow", check_git_workflow()),
    ]

    all_results: Results = []
    for section_name, results in grouped:
        print_section(section_name, results)
        all_results.extend(results)

    passed = sum(1 for r in all_results if r.passed)
    total = len(all_results)
    critical_failures = [r for r in all_results if not r.passed and r.critical]

    print(f"\n{'=' * 60}")
    print(f"  Score: {passed}/{total} automated checks passed")
    if critical_failures:
        print(f"\n  Critical failures ({len(critical_failures)}):")
        for r in critical_failures:
            print(f"    {r.icon} {r.label}")
    print(f"{'=' * 60}")

    # Manual checklist
    print("\n📋 Manual checks (teacher review required):")
    for check in MANUAL_CHECKS:
        print(f"  ☐  {check}")

    # Write GitHub Step Summary
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        try:
            with open(summary_path, "w") as fh:
                fh.write(build_markdown_summary(all_results, passed, total))
        except OSError as exc:
            print(f"\nWarning: could not write step summary: {exc}", file=sys.stderr)

    # Exit 1 only when critical checks fail
    if critical_failures:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
