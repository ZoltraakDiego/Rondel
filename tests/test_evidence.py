"""验证有限运行清单、尝试预算和冻结版本的只读检查。"""

import pytest
from conftest import ROOT, load_module

evidence = load_module(
    "experiment_evidence", ROOT / "skills/rondel-main/scripts/evidence.py"
)
prep = load_module(
    "experiment_preparation", ROOT / "skills/rondel-main/scripts/preparation.py"
)


def ref(api, path):
    return "record:" + api.read_note(path)[0]["id"]


def plan(api, project, source, approved=True, attempts=1):
    pins = []
    for purpose in ("dataset", "protocol", "baseline", "environment"):
        p = prep.create_setting(
            project,
            purpose,
            purpose,
            purpose,
            {"version": "synthetic-v1"},
            "合成条件。",
        )
        rel = p.relative_to(project).as_posix()
        api.transition(
            project, rel, "checked", api.digest(p), "check", "合成来源核对"
        )
        prep.freeze(project, rel, api.digest(p), source, "采纳合成设置")
        pins.append(prep.pin(project, rel))
    p = api.create_record(
        project,
        "experiment",
        "有限方案",
        "合成记录，不实际训练。",
        fields={
            "hypothesis": "测试假设",
            "expected_result": "测试预期",
            "falsification": "测试反例",
            "scope": {
                "run_keys": ["base-s42", "adapter-s42"],
                "max_attempts_per_run": attempts,
                "max_total_attempts": 2 * attempts,
            },
            "setting_refs": pins,
        },
    )
    if approved:
        for state, actor in (
            ("reviewable", "assistant"),
            ("approved", "human"),
        ):
            api.transition(
                project,
                p.relative_to(project).as_posix(),
                state,
                api.digest(p),
                actor,
                "合成状态",
                source if actor == "human" else None,
            )
    return p, pins


def run(api, project, exp, pins, key="base-s42", attempt=1, terminal=None):
    p = api.create_record(
        project,
        "run",
        f"测试 {key}/{attempt}",
        "仅合成状态。",
        refs=[ref(api, exp)],
        fields={
            "experiment_ref": ref(api, exp),
            "run_key": key,
            "attempt": attempt,
            "setting_refs": pins,
        },
    )
    if terminal:
        for state in ("preparing", "ready", "running", terminal):
            api.transition(
                project,
                p.relative_to(project).as_posix(),
                state,
                api.digest(p),
                "check",
                "合成生命周期",
            )
    return p


def test_preflight_is_read_only_and_does_not_grant_execution(
    api, project, source
):
    exp, _ = plan(api, project, source)
    before = {p: p.read_bytes() for p in project.rglob("*") if p.is_file()}
    value = evidence.preflight(project, ref(api, exp))
    assert value["structural_ready"] and value["new_attempt_run_keys"] == [
        "base-s42",
        "adapter-s42",
    ]
    assert (
        value["execution_authorized"] is False and value["live_checks_required"]
    )
    assert before == {
        p: p.read_bytes() for p in project.rglob("*") if p.is_file()
    }


def test_unapproved_plan_is_not_ready(api, project, source):
    exp, _ = plan(api, project, source, approved=False)
    value = evidence.preflight(project, ref(api, exp))
    assert (
        not value["structural_ready"]
        and "actual_approval_source_missing" in value["issues"]
    )


def test_registered_pending_and_completed_runs_are_not_recreated(
    api, project, source
):
    exp, pins = plan(api, project, source)
    pending = run(api, project, exp, pins)
    done = run(api, project, exp, pins, key="adapter-s42", terminal="completed")
    value = evidence.preflight(project, ref(api, exp))
    assert value["structural_ready"] and value["new_attempt_run_keys"] == []
    assert value["remaining_registration_budget"] == 0
    assert value["pending_run_refs"] == [ref(api, pending)] and value[
        "completed_run_refs"
    ] == [ref(api, done)]


@pytest.mark.parametrize(
    "key,attempt,issue",
    [
        ("unapproved-arm", 1, "run_key_not_in_scope"),
        ("base-s42", 2, "attempt_outside_scope"),
    ],
)
def test_attempts_stay_in_approved_manifest(
    api, project, source, key, attempt, issue
):
    exp, pins = plan(api, project, source)
    run(api, project, exp, pins, key, attempt)
    value = evidence.preflight(project, ref(api, exp))
    assert not value["structural_ready"] and any(
        v.startswith(issue) for v in value["issues"]
    )


def test_duplicate_attempt_and_wrong_pins_are_reported(api, project, source):
    exp, pins = plan(api, project, source)
    run(api, project, exp, pins)
    run(api, project, exp, [])
    value = evidence.preflight(project, ref(api, exp))
    assert not value["structural_ready"]
    assert any(v.startswith("duplicate_run_attempt") for v in value["issues"])
    assert any(v.startswith("run_setting_pins_differ") for v in value["issues"])


def test_retry_requires_budget_and_failed_predecessor(api, project, source):
    exp, pins = plan(api, project, source, attempts=2)
    first = run(api, project, exp, pins, terminal="failed")
    assert (
        "base-s42"
        in evidence.preflight(project, ref(api, exp))["new_attempt_run_keys"]
    )
    second = run(api, project, exp, pins, attempt=2)
    value = evidence.preflight(project, ref(api, exp))
    assert (
        value["structural_ready"]
        and ref(api, second) in value["pending_run_refs"]
    )
    assert api.read_note(first)[0]["status"] == "failed"


def test_completed_invalid_attempt_needs_inspection_before_retry(
    api, project, source
):
    exp, pins = plan(api, project, source, attempts=2)
    first = run(api, project, exp, pins, terminal="completed")
    rel = first.relative_to(project).as_posix()
    api.update_record(
        project,
        rel,
        {"check_status": "invalid"},
        api.digest(first),
        "check",
        "合成无效产物",
    )
    assert (
        "base-s42"
        not in evidence.preflight(project, ref(api, exp))[
            "new_attempt_run_keys"
        ]
    )
    report = api.create_record(
        project,
        "discussion",
        "产物核验",
        "合成依据。",
        fields={"purpose": "run_inspection"},
    )
    api.update_record(
        project,
        rel,
        {"refs": [ref(api, exp), ref(api, report)]},
        api.digest(first),
        "check",
        "关联检查",
    )
    assert (
        "base-s42"
        in evidence.preflight(project, ref(api, exp))["new_attempt_run_keys"]
    )


@pytest.mark.parametrize("status", ["running", "completed"])
def test_extra_budget_does_not_retry_active_or_completed_run(
    api, project, source, status
):
    exp, pins = plan(api, project, source, attempts=2)
    first = run(api, project, exp, pins)
    states = ["preparing", "ready", "running"]
    if status == "completed":
        states.append("completed")
    for state in states:
        api.transition(
            project,
            first.relative_to(project).as_posix(),
            state,
            api.digest(first),
            "check",
            "合成生命周期",
        )
    value = evidence.preflight(project, ref(api, exp))
    assert value["structural_ready"]
    assert "base-s42" not in value["new_attempt_run_keys"]
    run(api, project, exp, pins, attempt=2)
    value = evidence.preflight(project, ref(api, exp))
    assert not value["structural_ready"]
    assert any(
        v.startswith("retry_before_previous_failure") for v in value["issues"]
    )


def test_new_settings_need_impact_review_and_old_plan_is_unchanged(
    api, project, source
):
    exp, pins = plan(api, project, source)
    rows = {"record:" + r["id"]: r for r in api._records(project)}
    old = project / rows[pins[0]["ref"]]["path"]
    before = exp.read_bytes()
    new = prep.revise(
        project,
        old.relative_to(project).as_posix(),
        api.digest(old),
        {"version": "v2"},
        source,
        "合成变更",
        {"summary": "需要复核原比较"},
    )
    api.transition(
        project,
        new.relative_to(project).as_posix(),
        "checked",
        api.digest(new),
        "check",
        "核对新版本",
    )
    prep.freeze(
        project,
        new.relative_to(project).as_posix(),
        api.digest(new),
        source,
        "采纳新版",
    )
    value = evidence.preflight(project, ref(api, exp))
    assert not value["structural_ready"] and any(
        v.startswith("setting_revision_needs_review") for v in value["issues"]
    )
    assert exp.read_bytes() == before


def test_reports_cannot_overwrite_state(api, project, source):
    exp, _ = plan(api, project, source)
    value = evidence.preflight(project, ref(api, exp))
    with pytest.raises(ValueError, match=".state/evidence"):
        evidence.save_report(project, ".state/pending.json", value)
    assert not (project / ".state/pending.json").exists()
    assert evidence.save_report(
        project, ".state/evidence/preflight.json", value
    ).is_file()
