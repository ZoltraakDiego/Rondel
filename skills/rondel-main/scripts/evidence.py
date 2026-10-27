"""只读核对有限实验清单与冻结设置；不提交任务或评判科研结论。"""

from __future__ import annotations

import argparse
import importlib.util
import json
from collections import Counter
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "rondel_evidence_records", Path(__file__).with_name("records.py")
)
records = importlib.util.module_from_spec(spec)
spec.loader.exec_module(records)


def _pins(value: list[dict]) -> set[tuple]:
    return {(p["ref"], p["version"], p["definition_sha256"]) for p in value}


def preflight(workspace: Path, experiment_ref: str) -> dict:
    root = records.archive_root(workspace)
    rows = records._records(root)
    by_ref = {"record:" + r["id"]: r for r in rows}
    experiment_ref = (
        experiment_ref
        if experiment_ref.startswith("record:")
        else "record:" + experiment_ref
    )
    plan = by_ref.get(experiment_ref)
    if not plan or plan["type"] != "experiment":
        raise ValueError("Select a current experiment record in this project.")
    issues = []
    if plan["status"] not in {"approved", "preparing", "ready", "executing"}:
        issues.append("experiment_not_in_executable_state")
    approval = plan.get("approval", {})
    try:
        records.human_source(approval.get("source"))
    except ValueError:
        issues.append("actual_approval_source_missing")
    scope = plan.get("scope", {})
    if not isinstance(scope, dict):
        scope = {}
    if approval.get("scope") != scope:
        issues.append("scope_differs_from_approved_version")
    keys = scope.get("run_keys", [])
    if (
        not isinstance(keys, list)
        or not keys
        or any(not isinstance(k, str) or not k.strip() for k in keys)
        or len(set(keys)) != len(keys)
    ):
        issues.append("finite_unique_run_keys_required")
        keys = []
    per_run = scope.get("max_attempts_per_run", 1)
    total = scope.get("max_total_attempts", len(keys))
    if (
        type(per_run) is not int
        or per_run < 1
        or type(total) is not int
        or total < 1
    ):
        issues.append("positive_attempt_budgets_required")
        per_run = total = 0
    purposes = scope.get(
        "required_setting_purposes",
        ["dataset", "protocol", "baseline", "environment"],
    )
    if not isinstance(purposes, list) or any(
        p not in records.SETTING_PURPOSES for p in purposes
    ):
        issues.append("unknown_required_setting_purpose")
        purposes = []
    pins = plan.get("setting_refs", [])
    try:
        records._validate_setting_refs(root, plan)
    except ValueError:
        issues.append("setting_pin_missing_draft_or_changed")
    used = set()
    for pin in pins:
        setting = by_ref.get(pin["ref"], {})
        used.add(setting.get("purpose"))
        if setting.get("status") != "checked":
            issues.append("pinned_setting_needs_actual_recheck:" + pin["ref"])
        newer = [
            r
            for r in rows
            if setting.get("setting_key")
            and r.get("setting_key") == setting["setting_key"]
            and r.get("setting_state") == "frozen"
            and r["setting_version"] > pin["version"]
        ]
        if newer:
            current = max(newer, key=lambda r: r["setting_version"])
            review = (
                current.get("impact_review", {})
                .get("results", {})
                .get(experiment_ref, {})
            )
            if review.get("action") != "keep" or not review.get("reason"):
                issues.append("setting_revision_needs_review:" + pin["ref"])
    for purpose in purposes:
        if purpose not in used:
            issues.append("required_setting_missing:" + purpose)
    runs = [
        r
        for r in rows
        if r["type"] == "run"
        and (
            r.get("experiment_ref") == experiment_ref
            or not r.get("experiment_ref")
            and experiment_ref in r.get("refs", [])
        )
    ]

    def failed_attempt(run):
        return run["status"] in {"failed", "cancelled"} or (
            run["status"] == "completed"
            and run.get("check_status") == "invalid"
            and any(
                by_ref.get(ref, {}).get("purpose") == "run_inspection"
                for ref in run.get("refs", [])
            )
        )

    counts = Counter()
    seen = set()
    for run in runs:
        key, attempt = run.get("run_key"), run.get("attempt", 1)
        if key not in keys:
            issues.append("run_key_not_in_scope:" + run["id"])
            continue
        counts[key] += 1
        if type(attempt) is not int or attempt < 1 or attempt > per_run:
            issues.append("attempt_outside_scope:" + run["id"])
        else:
            pair = (key, attempt)
            if pair in seen:
                issues.append("duplicate_run_attempt:" + key)
            seen.add(pair)
            if attempt > 1:
                prior = [
                    r
                    for r in runs
                    if r.get("run_key") == key
                    and r.get("attempt", 1) == attempt - 1
                ]
                if len(prior) != 1 or not failed_attempt(prior[0]):
                    issues.append("retry_before_previous_failure:" + run["id"])
        if _pins(run.get("setting_refs", [])) != _pins(pins):
            issues.append("run_setting_pins_differ:" + run["id"])
    if len(runs) > total or any(count > per_run for count in counts.values()):
        issues.append("registered_attempts_exceed_budget")
    new_keys = [
        key
        for key in keys
        if counts[key] < per_run
        and all(failed_attempt(r) for r in runs if r.get("run_key") == key)
    ]
    remaining = max(0, total - len(runs))
    return {
        "experiment_ref": experiment_ref,
        "status": plan["status"],
        "structural_ready": not issues,
        "issues": list(dict.fromkeys(issues)),
        "run_keys": keys,
        "registered_attempts": len(runs),
        "max_total_attempts": total,
        "remaining_registration_budget": remaining,
        "new_attempt_run_keys": new_keys[:remaining] if not issues else [],
        "pending_run_refs": [
            "record:" + r["id"]
            for r in runs
            if r["status"] in {"planned", "preparing", "ready"}
        ],
        "active_run_refs": [
            "record:" + r["id"]
            for r in runs
            if r["status"] in {"queued", "running"}
        ],
        "completed_run_refs": [
            "record:" + r["id"] for r in runs if r["status"] == "completed"
        ],
        "live_checks_required": [
            "actual_code_and_config",
            "data_and_evaluation_entry",
            "host_resources_and_existing_jobs",
        ],
        "execution_authorized": False,
    }


def save_report(workspace: Path, relative: str, value: dict) -> Path:
    root = records.archive_root(workspace)
    target = records.within(root, relative)
    if (
        not target.is_relative_to(root / ".state/evidence")
        or target.suffix != ".json"
    ):
        raise ValueError("Use a JSON report inside .state/evidence.")
    records.atomic_write(
        target, json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    )
    return target


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Finite experiment structural checks"
    )
    parser.add_argument("--root", required=True, type=Path)
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("preflight")
    check.add_argument("--experiment", required=True)
    check.add_argument("--out")
    args = parser.parse_args()
    try:
        result = preflight(args.root, args.experiment)
        if args.out:
            print("Evidence report:", save_report(args.root, args.out, result))
        print("Structural readiness:", result["structural_ready"])
        print("Registered attempts:", result["registered_attempts"])
        print(
            "Remaining registration budget:",
            result["remaining_registration_budget"],
        )
        for issue in result["issues"][:20]:
            print("Review:", issue)
        if len(result["issues"]) > 20:
            print(
                "Additional issues in full report:", len(result["issues"]) - 20
            )
        print(
            "Actual code, data, resources and user scope still require corresponding evidence."
        )
        return 0 if result["structural_ready"] else 1
    except (OSError, ValueError, TypeError, KeyError) as error:
        print("Error:", error)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
