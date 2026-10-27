"""验证前期跟踪、冻结定义、依赖影响和可恢复变更。"""

import json

import pytest
from conftest import ROOT, load_module

prep = load_module(
    "preparation_test", ROOT / "skills/rondel-main/scripts/preparation.py"
)


def ref(api, path):
    return "record:" + api.read_note(path)[0]["id"]


def checked_setting(
    api, project, source, purpose="dataset", key="primary-data"
):
    path = prep.create_setting(
        project,
        key,
        purpose,
        key,
        {"version": "synthetic-v1"},
        "测试设置定义。",
    )
    api.transition(
        project,
        path.relative_to(project).as_posix(),
        "checked",
        api.digest(path),
        "check",
        "已核对测试材料",
    )
    prep.freeze(
        project,
        path.relative_to(project).as_posix(),
        api.digest(path),
        source,
        "确认测试设置",
    )
    return path


def complete_task(api, project, key, evidence, source=None, state="done"):
    board = prep.initialize(
        project,
        source
        or {
            "kind": "user_message",
            "reference": "fixture/board",
            "quote": "初始化测试准备总表。",
        },
    )
    prep.set_task(
        project,
        key,
        state,
        evidence,
        "已经核对对应测试证据。",
        api.digest(board),
        source,
    )


def add_focus(api, project, source):
    init = project / "init.md"
    api.configure(
        project,
        {"research_anchor": {"search_summary": "少样本时序动作分割（TAS）"}},
        api.digest(init),
        "human",
        "确认检索摘要",
        source,
    )
    board = prep.initialize(project, source)
    pain = api.create_record(
        project,
        "question",
        "示范标注成本",
        "测试领域痛点。",
        fields={"purpose": "field_pain", "priority": "high", "source": source},
    )
    question = api.create_record(
        project,
        "question",
        "少量示范怎样建立可靠预测",
        "测试核心问题。",
        refs=[ref(api, pain)],
        fields={"purpose": "core_question", "pain_refs": [ref(api, pain)]},
    )
    relative = question.relative_to(project).as_posix()
    api.transition(
        project,
        relative,
        "clarified",
        api.digest(question),
        "assistant",
        "明确问题",
    )
    api.transition(
        project,
        relative,
        "active",
        api.digest(question),
        "human",
        "选择当前问题",
        source,
    )
    api.update_record(
        project,
        board.relative_to(project).as_posix(),
        {
            "focus": {
                "pain_refs": [ref(api, pain)],
                "question_refs": [ref(api, question)],
                "primary_question_ref": ref(api, question),
            },
            "refs": [ref(api, pain), ref(api, question)],
        },
        api.digest(board),
        "human",
        "维护当前痛点与问题",
        source,
    )
    return board, pain, question


def completed_run(api, project, pins, refs=None):
    path = api.create_record(
        project,
        "run",
        "测试复现运行",
        "测试证据，不是真实实验。",
        refs=refs,
        fields={"setting_refs": pins},
    )
    relative = path.relative_to(project).as_posix()
    for state in ("preparing", "ready", "running", "completed"):
        api.transition(
            project, relative, state, api.digest(path), "check", "测试生命周期"
        )
    api.update_record(
        project,
        relative,
        {"check_status": "valid", "refs": refs or ["project:init.md"]},
        api.digest(path),
        "check",
        "测试产物核验",
    )
    return path


def test_board_initialization_is_idempotent_and_context_recovers_it(
    api, project, source
):
    board = prep.initialize(project.parent, source)
    before = board.read_bytes()
    assert prep.initialize(project, source) == board
    assert board.read_bytes() == before
    status = prep.status(project)
    assert not status["checklist_complete"]
    assert len(status["tasks"]) == 10
    assert {p.name for p in project.parent.iterdir()} == {".rondel"}
    for mode in ("open", "status", "pre.baseline", "pre.protocol"):
        assert (
            board.relative_to(project).as_posix()
            in api.context_paths(project, mode)["files"]
        )
    assert (
        api.context_paths(project, "pre.benchmarks")["mode"] == "pre.baseline"
    )


def test_focus_is_explicit_and_current_question_links_to_field_pain(
    api, project, source
):
    _, pain, question = add_focus(api, project, source)
    value = prep.status(project)
    assert value["issues"] == []
    assert value["focus"]["primary_question_ref"] == ref(api, question)
    assert api.read_note(question)[0]["pain_refs"] == [ref(api, pain)]
    assert not value["checklist_complete"]


def test_setting_requires_check_then_freeze_and_preserves_definition(
    api, project, source
):
    path = prep.create_setting(
        project,
        "eval",
        "protocol",
        "评价协议",
        {"split": "train/val/test"},
        "协议正文。",
    )
    relative = path.relative_to(project).as_posix()
    with pytest.raises(ValueError, match="checked"):
        prep.freeze(project, relative, api.digest(path), source, "过早冻结")
    api.transition(
        project, relative, "checked", api.digest(path), "check", "核对完成"
    )
    prep.freeze(project, relative, api.digest(path), source, "确认协议")
    original_pin = prep.pin(project, relative)
    for actor in ("human", "assistant"):
        with pytest.raises(ValueError, match="Frozen"):
            api.update_record(
                project,
                relative,
                {"spec": {"split": "other"}},
                api.digest(path),
                actor,
                "尝试覆盖",
                source,
            )
    with pytest.raises(ValueError, match="Frozen"):
        api.update_record(
            project,
            relative,
            {},
            api.digest(path),
            "human",
            "改正文",
            source,
            body="另一协议",
        )
    api.update_record(
        project,
        relative,
        {"observation": {"at": "synthetic"}},
        api.digest(path),
        "check",
        "更新观测",
    )
    assert prep.pin(project, relative) == original_pin
    assert api.validate(project) == []


def test_revision_tracks_transitive_results_without_rewriting_history(
    api, project, source
):
    prep.initialize(project, source)
    old = checked_setting(api, project, source)
    experiment = api.create_record(
        project,
        "experiment",
        "原设置方案",
        "测试方案",
        fields={
            "setting_refs": [
                prep.pin(project, old.relative_to(project).as_posix())
            ]
        },
    )
    run = completed_run(
        api,
        project,
        [],
        refs=["project:" + experiment.relative_to(project).as_posix()],
    )
    analysis = api.create_record(
        project, "discussion", "原结果分析", "测试分析", refs=[ref(api, run)]
    )
    unknown = api.create_record(
        project, "run", "未绑定旧运行", "未知依赖", refs=["project:init.md"]
    )
    unrelated = api.create_record(project, "discussion", "无关笔记", "无关联")
    before = {
        p: p.read_bytes()
        for p in [old, experiment, run, analysis, unknown, unrelated]
    }
    new = prep.revise(
        project,
        old.relative_to(project).as_posix(),
        api.digest(old),
        {"version": "synthetic-v2"},
        source,
        "修正数据版本",
        {"summary": "先复核旧数据相关结果。"},
    )
    assert all(p.read_bytes() == content for p, content in before.items())
    assert api.read_note(new)[0]["setting_state"] == "draft"
    event = prep.changelog(project)[-1]
    affected = {r["ref"] for r in event["preparation_change"]["affected"]}
    assert {ref(api, experiment), ref(api, run), ref(api, analysis)} <= affected
    assert ref(api, unrelated) not in affected
    assert ref(api, unknown) in event["preparation_change"]["untracked_results"]
    assert event["preparation_change"]["changed_spec_fields"] == ["version"]
    assert event["source"] == source
    assert prep.status(project)["settings"]["primary-data"]["ref"] == ref(
        api, old
    )
    with pytest.raises(ValueError, match="newer"):
        prep.revise(
            project,
            old.relative_to(project).as_posix(),
            api.digest(old),
            {},
            source,
            "重复",
            {"summary": "重复"},
        )


def test_new_setting_reopens_tasks_but_old_results_keep_original_pins(
    api, project, source
):
    prep.initialize(project, source)
    old = checked_setting(api, project, source)
    pin = prep.pin(project, old.relative_to(project).as_posix())
    run = completed_run(api, project, [pin])
    complete_task(api, project, "datasets", [ref(api, old)])
    complete_task(api, project, "reproduction", [ref(api, run)])
    assert (
        prep.status(project)["tasks"]["reproduction"]["effective_state"]
        == "done"
    )
    new = prep.revise(
        project,
        old.relative_to(project).as_posix(),
        api.digest(old),
        {"version": "v2"},
        source,
        "修正标注版本",
        {"summary": "标注差异需要重新核对。"},
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
        "采用新版",
    )
    value = prep.status(project)
    assert value["tasks"]["datasets"]["effective_state"] == "needs_review"
    assert value["tasks"]["reproduction"]["effective_state"] == "needs_review"
    assert api.read_note(run)[0]["setting_refs"] == [pin]
    assert api.read_note(run)[0]["check_status"] == "valid"
    assert api.validate(project) == []
    with pytest.raises(ValueError, match="frozen"):
        api.update_record(
            project,
            run.relative_to(project).as_posix(),
            {"setting_refs": []},
            api.digest(run),
            "check",
            "改归属",
        )


def test_review_can_keep_old_result_with_explicit_reason(api, project, source):
    prep.initialize(project, source)
    old = checked_setting(api, project, source)
    run = completed_run(
        api, project, [prep.pin(project, old.relative_to(project).as_posix())]
    )
    complete_task(api, project, "reproduction", [ref(api, run)])
    new = prep.revise(
        project,
        old.relative_to(project).as_posix(),
        api.digest(old),
        {"version": "v1", "storage": "new"},
        source,
        "迁移存储，核对内容相同",
        {
            "summary": "只改变位置，已核对内容摘要。",
            "results": {
                ref(api, run): {
                    "action": "keep",
                    "reason": "测试示例：数据内容未变。",
                }
            },
        },
    )
    api.transition(
        project,
        new.relative_to(project).as_posix(),
        "checked",
        api.digest(new),
        "check",
        "内容核验",
    )
    prep.freeze(
        project,
        new.relative_to(project).as_posix(),
        api.digest(new),
        source,
        "采用新位置",
    )
    assert (
        prep.status(project)["tasks"]["reproduction"]["effective_state"]
        == "done"
    )


def test_task_completion_requires_real_records_and_waiver_source(
    api, project, source
):
    board = prep.initialize(project, source)
    with pytest.raises(ValueError, match="evidence"):
        prep.set_task(
            project, "datasets", "done", [], "完成", api.digest(board)
        )
    with pytest.raises(ValueError, match="source"):
        prep.set_task(
            project, "datasets", "waived", [], "不适用", api.digest(board)
        )
    other = api.create_record(project, "discussion", "普通笔记", "不能替代协议")
    complete_task(api, project, "protocols", [ref(api, other)])
    assert (
        prep.status(project)["tasks"]["protocols"]["effective_state"]
        == "needs_review"
    )


def test_complete_checklist_uses_focus_reading_settings_and_valid_run(
    api, project, source
):
    _, pain, question = add_focus(api, project, source)
    complete_task(api, project, "field_pains", [ref(api, pain)])
    complete_task(api, project, "core_questions", [ref(api, question)])
    for key, purpose in (
        ("literature", "literature_map"),
        ("core_reading", "core_paper"),
    ):
        note = api.create_record(
            project,
            "discussion",
            key,
            "人工审阅的测试依据。",
            fields={"purpose": purpose},
        )
        complete_task(api, project, key, [ref(api, note)])
    pins = []
    for task, purpose in prep.TASK_PURPOSES.items():
        setting = checked_setting(api, project, source, purpose, task)
        complete_task(api, project, task, [ref(api, setting)])
        pins.append(prep.pin(project, setting.relative_to(project).as_posix()))
    run = completed_run(api, project, pins)
    complete_task(api, project, "reproduction", [ref(api, run)])
    value = prep.status(project)
    assert value["pre_review_tasks_complete"]
    assert not value["checklist_complete"]
    review = api.create_record(
        project,
        "discussion",
        "前期退出评审",
        "结构核对与人工判断分别记录。",
        fields={"purpose": "phase_review", "review_type": "pre_exit"},
    )
    complete_task(api, project, "phase_review", [ref(api, review)])
    assert prep.status(project)["checklist_complete"]
    assert api.read_note(project / "init.md")[0]["phase"] == "init"


def test_phase_review_alone_does_not_complete_preparation(api, project, source):
    prep.initialize(project, source)
    review = api.create_record(
        project,
        "discussion",
        "前期评审草稿",
        "存在评审不代表准备条件具备。",
        fields={"purpose": "phase_review", "review_type": "pre_exit"},
    )
    complete_task(api, project, "phase_review", [ref(api, review)])
    before = {p: p.read_bytes() for p in project.rglob("*") if p.is_file()}
    value = prep.status(project)
    assert not value["pre_review_tasks_complete"]
    assert not value["checklist_complete"]
    assert before == {
        p: p.read_bytes() for p in project.rglob("*") if p.is_file()
    }
    assert api.read_note(project / "init.md")[0]["phase"] == "init"


def test_status_is_read_only_and_reports_are_explicit_rebuilds(
    api, project, source
):
    prep.initialize(project, source)
    checked_setting(api, project, source)
    before = {p: p.read_bytes() for p in project.rglob("*") if p.is_file()}
    prep.status(project)
    prep.changelog(project)
    assert before == {
        p: p.read_bytes() for p in project.rglob("*") if p.is_file()
    }
    reports = prep.write_reports(project)
    assert {p.relative_to(project).as_posix() for p in reports} == {
        "setup/preparation-todo.md",
        "history/preparation-changelog.md",
    }
    assert "+08:00" in reports[1].read_text(encoding="utf-8")
    assert all(p.read_bytes() == data for p, data in before.items())


def test_manual_frozen_definition_change_is_detected(api, project, source):
    path = checked_setting(api, project, source)
    path.write_text(
        path.read_text(encoding="utf-8") + "人工改了定义。\n", encoding="utf-8"
    )
    assert any("Frozen setting" in issue for issue in api.validate(project))
    with pytest.raises(ValueError, match="Frozen setting"):
        prep.pin(project, path.relative_to(project).as_posix())


def test_draft_and_incorrect_pins_are_rejected_before_creating_results(
    api, project, source
):
    path = prep.create_setting(
        project, "draft", "dataset", "待核对", {}, "草案"
    )
    with pytest.raises(ValueError, match="frozen"):
        prep.pin(project, path.relative_to(project).as_posix())
    with pytest.raises(ValueError, match="reference"):
        api.create_record(
            project,
            "run",
            "不能用草案跑",
            "测试",
            fields={
                "setting_refs": [
                    {
                        "ref": ref(api, path),
                        "version": 1,
                        "definition_sha256": "wrong",
                    }
                ]
            },
        )


def test_revision_recovery_keeps_change_impact_in_journal(
    api, project, source, monkeypatch
):
    old = checked_setting(api, project, source)
    with monkeypatch.context() as patch:
        patch.setattr(
            prep.records,
            "_event",
            lambda *_: (_ for _ in ()).throw(OSError("simulated interruption")),
        )
        with pytest.raises(OSError, match="interruption"):
            prep.revise(
                project,
                old.relative_to(project).as_posix(),
                api.digest(old),
                {"version": "v2"},
                source,
                "测试保存中断",
                {"summary": "恢复后继续审阅影响。"},
            )
    pending = json.loads(
        (project / ".state/pending.json").read_text(encoding="utf-8")
    )
    api.recover(project)
    assert (project / pending["path"]).is_file()
    events = [
        e
        for e in prep.changelog(project)
        if e["event_id"] == pending["event"]["event_id"]
    ]
    assert len(events) == 1
    assert events[0]["preparation_change"]["version"] == 2
    assert api.validate(project) == []


def test_search_summary_is_synced_with_profile_and_keeps_other_preferences(
    api, project, source
):
    path = project / "init.md"
    api.configure(
        project,
        {
            "collaboration": {
                "profile": {
                    "expression": {"summary": "完整段落", "source": source}
                }
            }
        },
        api.digest(path),
        "human",
        "保存表达偏好",
        source,
    )
    summary = "少样本细粒度的视觉异常检测（VAD/IAD）"
    api.configure(
        project,
        {"research_anchor": {"search_summary": summary}},
        api.digest(path),
        "human",
        "凝练检索摘要",
        source,
    )
    meta, _ = api.read_note(path)
    assert meta["research_anchor"]["search_summary"] == summary
    assert meta["collaboration"]["profile"]["research_domain"] == {
        "summary": summary,
        "source": source,
    }
    assert (
        meta["collaboration"]["profile"]["expression"]["summary"] == "完整段落"
    )
    assert (
        api.context_paths(project, "status")["research_anchor"][
            "search_summary"
        ]
        == summary
    )


def test_profile_domain_updates_anchor_without_removing_other_preferences(
    api, project, source
):
    path = project / "init.md"
    api.configure(
        project,
        {
            "collaboration": {
                "profile": {
                    "expression": {"summary": "完整段落", "source": source}
                }
            }
        },
        api.digest(path),
        "human",
        "设置表达",
        source,
    )
    api.configure(
        project,
        {
            "collaboration": {
                "profile": {
                    "research_domain": {
                        "summary": "少样本时序动作分割（TAS）",
                        "source": source,
                    }
                }
            }
        },
        api.digest(path),
        "human",
        "从画像修订领域",
        source,
    )
    meta, _ = api.read_note(path)
    assert (
        meta["research_anchor"]["search_summary"] == "少样本时序动作分割（TAS）"
    )
    assert (
        meta["collaboration"]["profile"]["expression"]["summary"] == "完整段落"
    )


def test_conflicting_search_summaries_do_not_change_the_archive(
    api, project, source
):
    path = project / "init.md"
    before = path.read_bytes()
    with pytest.raises(ValueError, match="agree"):
        api.configure(
            project,
            {
                "research_anchor": {"search_summary": "一个方向"},
                "collaboration": {
                    "profile": {
                        "research_domain": {
                            "summary": "另一个方向",
                            "source": source,
                        }
                    }
                },
            },
            api.digest(path),
            "human",
            "不一致输入",
            source,
        )
    assert path.read_bytes() == before


def test_setting_key_version_cannot_be_initialized_twice(api, project, source):
    prep.create_setting(project, "data", "dataset", "数据", {}, "草案")
    with pytest.raises(ValueError, match="already exists"):
        prep.create_setting(
            project, "data", "dataset", "另一份数据", {}, "另一个草案"
        )
