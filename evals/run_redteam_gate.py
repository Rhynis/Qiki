#!/usr/bin/env python3
"""CI gate for the promptfoo red-team scan (issue #348).

`promptfoo redteam run` itself does not exit non-zero specifically for
CRITICAL-severity findings — its process exit code reflects the eval step's
own pass/fail count across ALL severities. The issue's scope asks for a gate
that fails CI "on any CRITICAL finding" specifically (a jailbreak that
triggers a write tool, a PII leak, a confirm-gate bypass), so this script:

1. Runs `promptfoo redteam run -c <config>` as a subprocess and captures the
   eval id promptfoo prints on completion (``Red team complete (ID: ...)``).
2. Reads that eval's results directly from promptfoo's own local SQLite
   store (``~/.promptfoo/promptfoo.db``, verified empirically against a real
   local run while building this PR — there is no documented `redteam run
   -o results.json` for the EVALUATION results, only for the generated
   attack probes, so the SQLite store is the reliable source).
3. Exits 1 if any result has ``metadata.severity == "critical"`` AND
   ``success == 0`` (promptfoo's own grader marked it a failure); exits 0
   otherwise. Prints a plain-text summary either way.

Usage:
    python evals/run_redteam_gate.py --config evals/promptfooconfig.yaml

Requires: a `promptfoo` (or `npx promptfoo`) binary on PATH, Node >= 22
(promptfoo's own minimum -- this project's own dev machine had an older
pinned Node during development, worked around with a standalone Node 22
tarball; see the PR description for #348), and QIKI_AGENT_URL pointing at a
running `/api/v1/chat/agent/stream` endpoint (AGENT_ENABLED=true).
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

EVAL_ID_PATTERN = re.compile(r"Red team complete \(ID:\s*([\w:-]+)\)")
DEFAULT_DB_PATH = Path.home() / ".promptfoo" / "promptfoo.db"


def _resolve_promptfoo_command() -> list[str]:
    """Prefer a `promptfoo` binary already on PATH; fall back to `npx`."""
    direct = shutil.which("promptfoo")
    if direct:
        return [direct]
    return ["npx", "--yes", "promptfoo@latest"]


def run_redteam(config_path: Path, extra_args: list[str]) -> str:
    """Run `promptfoo redteam run`, return the completed eval's id."""
    command = [*_resolve_promptfoo_command(), "redteam", "run", "-c", str(config_path), *extra_args]
    print(f"+ {' '.join(command)}", flush=True)
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    print(result.stdout)
    print(result.stderr, file=sys.stderr)

    match = EVAL_ID_PATTERN.search(result.stdout) or EVAL_ID_PATTERN.search(result.stderr)
    if match is None:
        print(
            "run_redteam_gate: could not find a completed eval id in promptfoo's output "
            "(the 'Red team complete (ID: ...)' line) -- treating this as a failed run.",
            file=sys.stderr,
        )
        sys.exit(result.returncode or 1)
    return match.group(1)


def load_findings(db_path: Path, eval_id: str) -> list[dict[str, object]]:
    """Read one eval's results from promptfoo's local SQLite store."""
    if not db_path.exists():
        print(f"run_redteam_gate: no promptfoo database at {db_path}", file=sys.stderr)
        sys.exit(1)
    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.execute(
            "SELECT prompt, response, success, metadata, grading_result "
            "FROM eval_results WHERE eval_id = ?",
            (eval_id,),
        )
        rows = cursor.fetchall()
    finally:
        conn.close()

    findings: list[dict[str, object]] = []
    for prompt_raw, response_raw, success, metadata_raw, grading_raw in rows:
        metadata = json.loads(metadata_raw) if metadata_raw else {}
        grading = json.loads(grading_raw) if grading_raw else {}
        try:
            prompt_text = json.loads(prompt_raw).get("raw", prompt_raw)
        except (json.JSONDecodeError, TypeError):
            prompt_text = prompt_raw
        findings.append(
            {
                "prompt": prompt_text,
                "response": response_raw,
                "success": bool(success),
                "severity": metadata.get("severity", "unknown"),
                "plugin_id": metadata.get("pluginId", "unknown"),
                "reason": grading.get("reason", ""),
            }
        )
    return findings


def summarize_and_gate(findings: list[dict[str, object]]) -> int:
    """Print a summary; return the process exit code (1 iff a critical finding failed)."""
    if not findings:
        print("run_redteam_gate: no results found for this eval -- nothing to gate on.")
        return 0

    by_severity: dict[str, list[dict[str, object]]] = {}
    for finding in findings:
        by_severity.setdefault(str(finding["severity"]), []).append(finding)

    print("\n=== Red-team gate summary ===")
    for severity, items in sorted(by_severity.items()):
        failed = [item for item in items if not item["success"]]
        print(f"  {severity}: {len(items)} test(s), {len(failed)} failed")

    critical_failures = [
        finding
        for finding in findings
        if finding["severity"] == "critical" and not finding["success"]
    ]
    if not critical_failures:
        print("\nNo CRITICAL-severity findings failed. Gate PASSES.")
        return 0

    print(f"\n{len(critical_failures)} CRITICAL finding(s) FAILED:")
    for finding in critical_failures:
        print(f"  - plugin={finding['plugin_id']!r}")
        print(f"    prompt:   {finding['prompt']!r}")
        print(f"    reason:   {finding['reason']!r}")
    print("\nGate FAILS.")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("evals/promptfooconfig.yaml"))
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument(
        "--skip-run",
        metavar="EVAL_ID",
        default=None,
        help="Skip running promptfoo; gate on an already-completed eval id instead.",
    )
    args, extra_args = parser.parse_known_args()

    eval_id = args.skip_run or run_redteam(args.config, extra_args)
    print(f"\nGating on eval: {eval_id}")
    findings = load_findings(args.db_path, eval_id)
    return summarize_and_gate(findings)


if __name__ == "__main__":
    sys.exit(main())
