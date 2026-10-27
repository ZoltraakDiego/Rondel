"""验证记录可修改，研究决定与原批准范围得到保留。"""

import pytest


def test_record_update_preserves_body_and_references(api, project):
    path = api.create_record(
        project, "discussion", "当前讨论", "用户原有说明。"
    )
    api.update_record(
        project,
        path.relative_to(project).as_posix(),
        {"refs": ["project:init.md"]},
        api.digest(path),
        "assistant",
        "补充来源",
    )
    meta, body = api.read_note(path)
    assert meta["refs"] == ["project:init.md"]
    assert "用户原有说明" in body
    assert meta["revision"] == 2


def test_update_cannot_smuggle_a_state_transition(api, project):
    path = api.create_record(project, "claim", "候选认识", "原文")
    with pytest.raises(api.RecordError, match="explicit transition"):
        api.update_record(
            project,
            path.relative_to(project).as_posix(),
            {"status": "adopted"},
            api.digest(path),
            "assistant",
            "自动采纳",
        )


def test_approved_scope_cannot_be_extended_in_place(api, project, source):
    path = api.create_record(
        project,
        "experiment",
        "有限方案",
        "正文",
        fields={
            "hypothesis": "假设",
            "expected_result": "预期",
            "falsification": "判定",
            "scope": {"runs": 2},
        },
    )
    for state, actor in (("reviewable", "assistant"), ("approved", "human")):
        api.transition(
            project,
            path.relative_to(project).as_posix(),
            state,
            api.digest(path),
            actor,
            "方案状态",
            source if actor == "human" else None,
        )
    before = path.read_bytes()
    with pytest.raises(api.RecordError, match="frozen"):
        api.update_record(
            project,
            path.relative_to(project).as_posix(),
            {"scope": {"runs": 20}},
            api.digest(path),
            "human",
            "扩大范围",
            source,
        )
    assert path.read_bytes() == before


def test_artifact_check_requires_a_referenced_report(api, project):
    path = api.create_record(project, "run", "已登记的运行", "运行内容")
    for state in ("preparing", "ready", "running", "completed"):
        api.transition(
            project,
            path.relative_to(project).as_posix(),
            state,
            api.digest(path),
            "check",
            "登记模拟运行状态",
        )
    with pytest.raises(api.RecordError, match="evidence"):
        api.update_record(
            project,
            path.relative_to(project).as_posix(),
            {"check_status": "valid"},
            api.digest(path),
            "check",
            "检查产物",
        )
    api.update_record(
        project,
        path.relative_to(project).as_posix(),
        {"check_status": "valid", "refs": ["project:init.md"]},
        api.digest(path),
        "check",
        "登记检查引用",
    )
    assert api.read_note(path)[0]["check_status"] == "valid"


def test_historical_records_are_immutable(api, project):
    path = api.create_record(project, "question", "问题", "原有观察")
    api.update_record(
        project,
        path.relative_to(project).as_posix(),
        {"refs": ["project:init.md"]},
        api.digest(path),
        "assistant",
        "补充来源",
    )
    archive = next((project / "history/records").rglob("*.md"))
    before = archive.read_bytes()
    with pytest.raises(api.RecordError, match="read-only"):
        api.transition(
            project,
            archive.relative_to(project).as_posix(),
            "clarified",
            api.digest(archive),
            "assistant",
            "修改历史",
        )
    with pytest.raises(api.RecordError, match="read-only"):
        api.update_record(
            project,
            archive.relative_to(project).as_posix(),
            {},
            api.digest(archive),
            "assistant",
            "改历史",
            body="新文",
        )
    assert archive.read_bytes() == before


def test_unexecuted_run_cannot_be_marked_valid(api, project):
    path = api.create_record(project, "run", "未运行的任务", "只有登记")
    with pytest.raises(api.RecordError, match="completed"):
        api.update_record(
            project,
            path.relative_to(project).as_posix(),
            {"check_status": "valid", "refs": ["project:init.md"]},
            api.digest(path),
            "check",
            "过早验证",
        )
