"""验证科学取舍与运行事实的状态边界。"""

import pytest


def move(api, project, path, state, actor="assistant", source=None):
    api.transition(
        project,
        path.relative_to(project).as_posix(),
        state,
        api.digest(path),
        actor,
        "测试真实状态变化",
        source,
    )


def test_assistant_cannot_confirm_research_direction(api, project):
    with pytest.raises(api.RecordError, match="human"):
        api.configure(
            project,
            {"research_anchor": {"problem": "AI 选定的问题"}},
            api.digest(project / "init.md"),
            "assistant",
            "建议",
        )


def test_exploration_ready_without_fabricated_experiment_settings(
    api, project, source
):
    api.configure(
        project,
        {
            "research_anchor": {"open_question": "共同理解具体错误"},
            "next_step": {"label": "阅读已有错误案例"},
            "ready_for": "exploration",
            "status": "ready",
        },
        api.digest(project / "init.md"),
        "human",
        "用户选择探索",
        source,
    )
    meta, _ = api.read_note(project / "init.md")
    assert meta["bindings"] == {}
    assert meta["status"] == "ready"


def test_execution_readiness_requires_plan_and_resources(api, project, source):
    with pytest.raises(api.RecordError, match="Execution readiness"):
        api.configure(
            project,
            {
                "research_anchor": {"open_question": "理解错误"},
                "next_step": {"label": "执行方案"},
                "ready_for": "execution",
                "status": "ready",
            },
            api.digest(project / "init.md"),
            "human",
            "用户选择",
            source,
        )


def test_ready_requires_explicit_next_step(api, project, source):
    with pytest.raises(api.RecordError, match="next step"):
        api.configure(
            project,
            {
                "research_anchor": {"open_question": "理解错误"},
                "ready_for": "exploration",
                "status": "ready",
            },
            api.digest(project / "init.md"),
            "human",
            "用户选择",
            source,
        )


def test_phase_jump_requires_confirmed_intake(api, project, source):
    with pytest.raises(api.RecordError, match="Confirm intake"):
        api.configure(
            project,
            {"phase": "write"},
            api.digest(project / "init.md"),
            "human",
            "进入写作",
            source,
        )


def test_human_direction_keeps_confirmation_source(api, project, source):
    api.configure(
        project,
        {
            "research_anchor": {
                "problem": "时间信息怎样支持连续判断",
                "direction_status": "confirmed",
            }
        },
        api.digest(project / "init.md"),
        "human",
        "用户明确主线",
        source,
    )
    meta, _ = api.read_note(project / "init.md")
    assert meta["research_anchor"]["confirmed_by"] == source


def test_question_activation_needs_user_but_clarification_can_proceed(
    api, project, source
):
    path = api.create_record(project, "question", "当前问题", "具体观察")
    move(api, project, path, "clarified")
    with pytest.raises(api.RecordError, match="human"):
        move(api, project, path, "active")
    move(api, project, path, "active", "human", source)
    assert api.read_note(path)[0]["status"] == "active"


def test_experiment_approval_requires_three_line_design_and_scope(
    api, project, source
):
    path = api.create_record(project, "experiment", "同预算对照", "草稿")
    move(api, project, path, "reviewable")
    with pytest.raises(api.RecordError, match="hypothesis"):
        move(api, project, path, "approved", "human", source)


def test_approved_plan_retains_exact_scope(api, project, source):
    scope = {
        "arms": ["直接利用特征", "通过记忆利用特征"],
        "seeds": [1],
        "runs": 2,
    }
    path = api.create_record(
        project,
        "experiment",
        "匹配对照",
        "方案",
        fields={
            "hypothesis": "显式匹配提供额外信息",
            "expected_result": "预登记条件",
            "falsification": "未达到预登记条件",
            "scope": scope,
        },
    )
    move(api, project, path, "reviewable")
    with pytest.raises(api.RecordError, match="human"):
        move(api, project, path, "approved")
    move(api, project, path, "approved", "human", source)
    assert api.read_note(path)[0]["approval"]["scope"] == scope


def test_runtime_error_does_not_modify_hypothesis_assessment(api, project):
    hypothesis = api.create_record(
        project,
        "hypothesis",
        "某个解释",
        "正文",
        fields={"assessment": "unassessed"},
    )
    run = api.create_record(project, "run", "计算尝试", "正文")
    move(api, project, run, "preparing")
    move(api, project, run, "failed")
    assert api.read_note(hypothesis)[0]["assessment"] == "unassessed"
    with pytest.raises(api.RecordError, match="Unsupported"):
        move(api, project, run, "running")


def test_claim_requires_evidence_and_human_adoption(api, project, source):
    path = api.create_record(project, "claim", "候选论点", "正文")
    with pytest.raises(api.RecordError, match="Evidence"):
        move(api, project, path, "evidence_linked")
    evidence = api.create_record(project, "discussion", "证据讨论", "具体来源")
    path = api.create_record(
        project,
        "claim",
        "有关联的论点",
        "正文",
        ["record:" + api.read_note(evidence)[0]["id"]],
    )
    move(api, project, path, "evidence_linked")
    move(api, project, path, "reviewed")
    with pytest.raises(api.RecordError, match="human"):
        move(api, project, path, "adopted")
    move(api, project, path, "adopted", "human", source)
    move(api, project, path, "needs_review")
    assert api.read_note(path)[0]["status"] == "needs_review"
