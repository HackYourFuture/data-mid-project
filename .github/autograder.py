#!/usr/bin/env python3
"""
Week 7 autograder for the HackYourFuture data-mid-project.

Called by .github/workflows/autograder.yml after pytest has already run.
Reads PYTEST_EXIT_CODE from the environment to know whether tests passed.

Output:
  - checkmark per check printed to stdout
  - Markdown summary written to $GITHUB_STEP_SUMMARY (if set)
  - Exit 1 when any *critical* check fails; exit 0 otherwise
"""

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
    def __init__(self, label, passed, critical, detail=""):
        self.label = label
        self.passed = passed
        self.critical = critical
        self.detail = detail

    @property
    def icon(self):
        return "✅" if self.passed else "❌"

    def __str__(self):
        suffix = f"  ({self.detail})" if self.detail else ""
        crit_tag = " [CRITICAL]" if not self.passed and self.critical else ""
        return f"  {self.icon} {self.label}{crit_tag}{suffix}"


def ok(label, critical=False, detail=""):
    return Result(label, True, critical, detail)


def fail(label, critical=False, detail=""):
    return Result(label, False, critical, detail)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ROOT = Path(".")


def file_exists(path):
    return (ROOT / path).exists()


def grep_src(pattern):
    """Search src/ for pattern. Returns list of matching lines, or None if src/ missing."""
    src_dir = ROOT / "src"
    if not src_dir.is_dir():
        return None
    matches = []
    regex = re.compile(pattern)
    for py_file in src_dir.rglob("*.py"):
        for line in py_file.read_text(errors="replace").splitlines():
            if regex.search(line):
                matches.append(line)
    return matches


def count_test_functions():
    count = 0
    tests_dir = ROOT / "tests"
    if not tests_dir.is_dir():
        return 0
    for py_file in tests_dir.rglob("test_*.py"):
        for line in py_file.read_text(errors="replace").splitlines():
            if re.match(r"\s*def test_", line):
                count += 1
    return count


def readme_is_filled_in():
    readme = ROOT / "README.md"
    if not readme.exists():
        return False
    non_heading = [
        line for line in readme.read_text(errors="replace").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    return len(non_heading) > 5


def ai_assist_is_filled_in():
    """Return True if AI_ASSIST.md has at least one real 'What I asked:' entry."""
    ai_file = ROOT / "AI_ASSIST.md"
    if not ai_file.exists():
        return False
    content = ai_file.read_text(errors="replace")
    entries = re.findall(r"What I asked:\*\*\s*(.+)", content)
    # Also match unbolded variant
    entries += re.findall(r"What I asked:\s*(.+)", content)
    real_entries = [e for e in entries if e.strip() and not e.strip().startswith("<")]
    return len(real_entries) >= 1


def env_example_has_empty_secrets():
    env_example = ROOT / ".env.example"
    if not env_example.exists():
        return True
    for line in env_example.read_text(errors="replace").splitlines():
        for key in ("POSTGRES_URL", "AZURE_STORAGE_CONNECTION_STRING"):
            if line.startswith(f"{key}="):
                value = line[len(f"{key}="):].strip().strip("\"'")
                if value:
                    return False
    return True


def no_hardcoded_secrets():
    """Return (clean, detail). clean=True means no secrets found."""
    patterns = [
        r"postgres://\w+:\w+@",
        r"DefaultEndpointsProtocol=https;AccountKey=",
        r"AccountKey=[A-Za-z0-9+/]{40,}",
    ]
    hits = []
    src_dir = ROOT / "src"
    if not src_dir.is_dir():
        return True, ""
    for py_file in src_dir.rglob("*.py"):
        text = py_file.read_text(errors="replace")
        for pat in patterns:
            if re.search(pat, text):
                hits.append(f"{py_file.name}: matched pattern")
    if hits:
        return False, "; ".join(hits[:3])
    return True, ""


def no_bare_print_in_src():
    src_dir = ROOT / "src"
    if not src_dir.is_dir():
        return True
    for py_file in src_dir.rglob("*.py"):
        for line in py_file.read_text(errors="replace").splitlines():
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            if re.search(r"\bprint\s*\(", line):
                return False
    return True


def merge_commit_count():
    try:
        result = subprocess.run(
            ["git", "log", "--merges", "main", "--oneline"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return len([l for l in result.stdout.splitlines() if l.strip()])
    except Exception:
        return 0


def has_non_autograder_workflow():
    wf_dir = ROOT / ".github" / "workflows"
    if not wf_dir.is_dir():
        return False
    return bool([f for f in wf_dir.glob("*.yml") if f.name != "autograder.yml"])


# ---------------------------------------------------------------------------
# Check groups
# ---------------------------------------------------------------------------

def check_file_structure():
    results = []

    for path, critical in [
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
    ]:
        label = f"File exists: {path}"
        results.append(ok(label, critical) if file_exists(path) else fail(label, critical))

    tests_dir = ROOT / "tests"
    has_test_file = tests_dir.is_dir() and bool(list(tests_dir.rglob("test_*.py")))
    results.append(
        ok("tests/ has at least one test_*.py") if has_test_file
        else fail("tests/ has at least one test_*.py")
    )

    results.append(
        ok("README.md has been filled in") if readme_is_filled_in()
        else fail("README.md has been filled in")
    )

    results.append(
        ok("AI_ASSIST.md has been filled in") if ai_assist_is_filled_in()
        else fail("AI_ASSIST.md has been filled in")
    )

    return results


def check_code_patterns():
    results = []

    pandas_lines = grep_src(r"import pandas|from pandas")
    if pandas_lines is None:
        results.append(fail("src/ directory exists", critical=True))
    elif pandas_lines:
        results.append(ok("pandas imported in src/", critical=True))
    else:
        results.append(fail("pandas imported in src/", critical=True))

    pydantic_lines = grep_src(r"BaseModel|import pydantic|from pydantic")
    results.append(
        ok("Pydantic BaseModel used in src/", critical=True) if pydantic_lines
        else fail("Pydantic BaseModel used in src/", critical=True)
    )

    sys_exit_lines = grep_src(r"\bsys\.exit\b")
    results.append(
        ok("sys.exit present in src/ (fail-fast on missing env vars)") if sys_exit_lines
        else fail("sys.exit present in src/ (fail-fast on missing env vars)")
    )

    results.append(
        ok("No bare print() in src/ (logging used instead)") if no_bare_print_in_src()
        else fail("No bare print() in src/ (logging used instead)")
    )

    return results


def check_security():
    results = []

    results.append(
        ok(".env not committed", critical=True) if not (ROOT / ".env").exists()
        else fail(".env not committed", critical=True, detail=".env found in working tree")
    )

    results.append(
        ok(".env.example has empty values for secret keys") if env_example_has_empty_secrets()
        else fail(".env.example has empty values for secret keys")
    )

    clean, detail = no_hardcoded_secrets()
    results.append(
        ok("No hardcoded secrets in src/", critical=True) if clean
        else fail("No hardcoded secrets in src/", critical=True, detail=detail)
    )

    return results


def check_tests(pytest_exit_code):
    results = []

    fn_count = count_test_functions()
    results.append(
        ok(f"At least 2 test functions found ({fn_count} total)") if fn_count >= 2
        else fail(f"At least 2 test functions found (only {fn_count} found)")
    )

    results.append(
        ok("pytest passes", critical=True) if pytest_exit_code == 0
        else fail("pytest passes", critical=True, detail=f"exit code {pytest_exit_code}")
    )

    return results


def check_cicd():
    results = []
    results.append(
        ok("CI workflow exists (.github/workflows/)") if has_non_autograder_workflow()
        else fail("CI workflow exists (.github/workflows/)")
    )
    return results


def check_git_workflow():
    results = []
    merge_count = merge_commit_count()
    results.append(
        ok(f"At least 3 PRs merged ({merge_count} merge commits on main)") if merge_count >= 3
        else fail(f"At least 3 PRs merged ({merge_count} merge commits found)")
    )
    return results


# ---------------------------------------------------------------------------
# Manual checklist
# ---------------------------------------------------------------------------

MANUAL_CHECKS = [
    "Docker image builds and runs locally (`docker run --env-file .env`)",
    "Transform does real work: pipeline.py calls at least one of parse_dates / dropna / fillna / rename / assign / a new derived column (not just pd.DataFrame(records) → storage)",
    "Azure ACR: image exists with a tagged version",
    "Azure: Container App Job created with --trigger-type Schedule --cron-expression",
    "Azure: job ran successfully (execution history shows Succeeded)",
    "Azure: job output verifiable (rows in Postgres AND blobs in Blob Storage)",
    "Azure: job uses --registry-server, --replica-timeout 300, --env-vars",
    "Cleanup: Container App Job deleted after evaluation",
]


# ---------------------------------------------------------------------------
# Markdown summary
# ---------------------------------------------------------------------------

def build_markdown(all_results, score, total):
    lines = [
        "# Week 7 Autograder Results",
        "",
        f"**Automated checks: {score}/{total} passed**",
        "",
        "| # | Check | Result |",
        "|---|-------|--------|",
    ]
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
    for c in MANUAL_CHECKS:
        lines.append(f"- [ ] {c}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    try:
        pytest_exit_code = int(os.environ.get("PYTEST_EXIT_CODE", "1"))
    except ValueError:
        pytest_exit_code = 1

    print("=" * 60)
    print("  HackYourFuture — Week 7 Autograder")
    print("=" * 60)

    grouped = [
        ("File structure", check_file_structure()),
        ("Code patterns", check_code_patterns()),
        ("Security", check_security()),
        ("Tests", check_tests(pytest_exit_code)),
        ("CI/CD", check_cicd()),
        ("Git workflow", check_git_workflow()),
    ]

    all_results = []
    for section_name, results in grouped:
        print(f"\n{'─' * 60}")
        print(f"  {section_name}")
        print(f"{'─' * 60}")
        for r in results:
            print(r)
        all_results.extend(results)

    passed = sum(1 for r in all_results if r.passed)
    total = len(all_results)
    critical_failures = [r for r in all_results if not r.passed and r.critical]

    print(f"\n{'=' * 60}")
    print(f"  Automated checks: {passed}/{total} passed")
    if critical_failures:
        print(f"\n  Critical failures:")
        for r in critical_failures:
            print(f"    {r.icon} {r.label}")
    print(f"{'=' * 60}")

    print("\n  Manual checks (teacher review required):")
    for c in MANUAL_CHECKS:
        print(f"    [ ] {c}")

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        try:
            with open(summary_path, "w") as fh:
                fh.write(build_markdown(all_results, passed, total))
        except OSError as exc:
            print(f"\nWarning: could not write step summary: {exc}", file=sys.stderr)

    return 1 if critical_failures else 0


if __name__ == "__main__":
    sys.exit(main())
