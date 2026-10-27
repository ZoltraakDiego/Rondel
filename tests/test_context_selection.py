"""验证普通任务不预读无关研究材料。"""

import hashlib

import pytest


def tree_hash(root):
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob("*")
        if p.is_file()
    }


def test_context_and_validation_are_read_only(api, project):
    before = tree_hash(project)
    result = api.context_paths(project, "status")
    assert result["files"] == ["init.md", "index.md"]
    assert api.validate(project) == []
    assert tree_hash(project) == before


def test_only_requested_target_is_loaded(api, project):
    first = api.create_record(project, "discussion", "当前融合问题", "相关证据")
    other = api.create_record(project, "discussion", "另一分支", "无关材料")
    identifier = api.read_note(first)[0]["id"]
    result = api.context_paths(project, "review", [identifier])
    assert first.relative_to(project).as_posix() in result["files"]
    assert other.relative_to(project).as_posix() not in result["files"]
    assert result["instruction"] == "references/drift-check.md"


def test_latest_handoff_selected_without_loading_every_handoff(api, project):
    first = api.create_record(project, "handoff", "旧交接", "旧内容")
    second = api.create_record(project, "handoff", "新交接", "新内容")
    # 时间以秒记录，明确区分两份记录的实际更新时间。
    meta, body = api.read_note(second)
    meta["updated_at"] = "2099-01-01T00:00:00+00:00"
    second.write_text(api.render(meta, body), encoding="utf-8")
    api.reindex(project)
    result = api.context_paths(project, "open")
    assert second.relative_to(project).as_posix() in result["files"]
    assert first.relative_to(project).as_posix() not in result["files"]


def test_manual_edit_is_read_fresh_without_reindexing(api, project):
    path = api.create_record(project, "question", "问题", "原正文")
    meta, body = api.read_note(path)
    identifier = meta["id"]
    meta["status"] = "parked"
    path.write_text(api.render(meta, body + "\n人工补充。"), encoding="utf-8")
    before = tree_hash(project)
    result = api.context_paths(project, "review", [identifier])
    assert result["targets"][0]["status"] == "parked"
    assert result["targets"][0]["stale_index"] is True
    assert tree_hash(project) == before


def test_unknown_target_requests_explicit_lookup(api, project):
    with pytest.raises(api.RecordError, match="not found"):
        api.context_paths(project, "review", ["nonexistent"])


def test_unavailable_collection_not_exposed_as_main_mode(api, project):
    with pytest.raises(api.RecordError, match="Unknown research"):
        api.context_paths(project, "future.execute")


@pytest.mark.parametrize(
    "mode,reference",
    [
        ("pre.framing", "pre-framing.md"),
        ("pre.library", "pre-papers.md"),
        ("pre.data", "pre-datasets.md"),
        ("pre.protocol", "pre-protocol.md"),
        ("pre.baseline", "pre-baselines.md"),
        ("pre.environment", "pre-environment.md"),
    ],
)
def test_preparation_context_routes_without_reading_unrelated_notes(
    api, project, mode, reference
):
    api.create_record(project, "discussion", "其他分支", "不相关材料")
    before = tree_hash(project)
    context = api.context_paths(project.parent, mode)
    assert context["files"] == ["init.md", "index.md"]
    assert context["instruction"] == "references/" + reference
    assert tree_hash(project) == before


def test_main_resumes_selected_plan_from_workspace(api, project):
    selection = {
        "kind": "user_message",
        "reference": "fixture/plan-choice",
        "quote": "这个计划可以，先核对指定材料。",
    }
    plan = api.create_record(
        project.parent,
        "discussion",
        "阶段计划与排期",
        "第一阶段核对材料，之后共同复盘。",
        fields={"purpose": "research_plan"},
    )
    plan_id = api.read_note(plan)[0]["id"]
    decision = api.decide(
        project.parent,
        "采纳第一步",
        "先核对指定材料。",
        selection,
        refs=[f"record:{plan_id}"],
    )
    decision_id = api.read_note(decision)[0]["id"]
    path = project / "init.md"
    api.configure(
        project.parent,
        {
            "research_anchor": {
                "open_question": "输入变化与预测变化怎样对应？"
            },
            "status": "ready",
            "ready_for": "exploration",
            "phase": "prepare",
            "next_step": {
                "label": "核对指定材料",
                "plan_ref": f"record:{plan_id}",
                "decision_ref": f"record:{decision_id}",
            },
            "refs": [f"record:{plan_id}", f"record:{decision_id}"],
        },
        api.digest(path),
        "human",
        "认可理解与计划并选择当前一步",
        selection,
        body="完整的理解段落。\n\n阶段计划摘要与当前任务。\n",
    )
    context = api.context_paths(project.parent, "open", [plan_id])
    assert plan.relative_to(project).as_posix() in context["files"]
    assert context["instruction"] == "references/main-cycle.md"
    assert (
        api.read_note(path)[0]["next_step"]["plan_ref"] == f"record:{plan_id}"
    )
    assert api.validate(project.parent) == []
