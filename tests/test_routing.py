"""验证路由按需读取、预算、历史检索和阶段摘要保真。"""

import json

import pytest
from conftest import ROOT, load_module

routing = load_module(
    "routing_test", ROOT / "skills/rondel-main/scripts/routing.py"
)
prep = load_module(
    "routing_preparation_test",
    ROOT / "skills/rondel-main/scripts/preparation.py",
)


def ref(api, path):
    return "record:" + api.read_note(path)[0]["id"]


def tree_bytes(root):
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in root.rglob("*")
        if p.is_file()
    }


def set_phase(api, project, source, phase):
    init = project / "init.md"
    api.configure(
        project,
        {
            "phase": phase,
            "status": "ready",
            "ready_for": "exploration",
            "research_anchor": {
                "search_summary": "少样本时序动作分割（TAS）",
                "open_question": "当前需要核对的问题",
            },
            "next_step": {"label": "核对当前问题"},
        },
        api.digest(init),
        "human",
        "测试阶段接入",
        source,
    )


def summary(api, project, source, publish=True, destination="prepare"):
    evidence = api.create_record(
        project,
        "discussion",
        "核心证据",
        "FULL_EVIDENCE_NOT_INLINE",
        fields={"purpose": "core_paper"},
    )
    brief = {
        "question": "示例核心问题",
        "findings": [
            {
                "statement": "特定条件下的观察",
                "conditions": "虚构的匹配条件",
                "evidence_refs": [ref(api, evidence)],
                "status": "observation",
            }
        ],
        "decisions": [],
        "open_questions": ["还有哪个解释未检验"],
        "carryovers": [
            {"task": "补充阅读", "owner": "researcher", "trigger": "下一次评审"}
        ],
        "next_step": {"label": "先审阅有限方案"},
    }
    path = routing.create_summary(
        project,
        "前期阶段沉淀",
        "prepare",
        destination,
        brief,
        [ref(api, evidence)],
        "完整阶段文档正文。",
    )
    if publish:
        routing.publish_summary(
            project,
            path.relative_to(project).as_posix(),
            api.digest(path),
            source,
        )
    return path, evidence


def test_discovery_stays_inside_boundary_and_detects_ambiguity(
    api, project, source
):
    child = project.parent / "code/subfolder"
    child.mkdir(parents=True)
    value = routing.discover(child, project.parent)
    assert value["resolution"] == "found"
    assert value["candidates"][0]["archive"] == str(project)
    assert routing.discover(child)["boundary"] == str(ROOT)
    assert routing.discover(child, child)["resolution"] == "not_found"
    api.initialize(
        project.parent / "code", "嵌套测试项目", "另一个项目", source
    )
    assert routing.discover(child, project.parent)["resolution"] == "ambiguous"
    assert routing.discover(project)["resolution"] == "found"
    with pytest.raises(ValueError, match="boundary"):
        routing.discover(project.parent, child)


def test_general_request_does_not_read_project_notes(project, monkeypatch):
    def unexpected(*_):
        raise AssertionError("General questions must not load a project")

    monkeypatch.setattr(routing.records, "read_note", unexpected)
    assert routing.packet(project, "general")["project_loaded"] is False


def test_mode_is_independent_of_project_phase(api, project, source):
    set_phase(api, project, source, "write")
    card = api.create_record(
        project,
        "discussion",
        "要读的核心论文",
        "原文细节",
        fields={"purpose": "core_paper"},
    )
    value = routing.packet(project, "pre.library")
    assert value["route"]["mode"] == "pre.library"
    assert value["route"]["instruction"] == "references/pre-papers.md"
    assert value["project"]["phase"] == "write"
    assert any(c["id"] == api.read_note(card)[0]["id"] for c in value["cards"])
    with pytest.raises(ValueError, match="available"):
        routing.packet(project, "future.execute")


def test_packet_does_not_read_or_inline_unrelated_notes(
    api, project, monkeypatch
):
    unrelated = api.create_record(
        project, "discussion", "无关方向", "UNRELATED_SECRET_BODY" * 1000
    )
    dataset = api.create_record(
        project,
        "resource",
        "当前数据",
        "DATA_DETAILS_NOT_INLINE",
        fields={"purpose": "dataset"},
    )
    calls = []
    original = routing.records.read_note

    def observed(path):
        calls.append(path)
        return original(path)

    monkeypatch.setattr(routing.records, "read_note", observed)
    before = tree_bytes(project)
    value = routing.packet(project, "pre.data")
    serialized = json.dumps(value, ensure_ascii=False)
    assert unrelated not in calls
    assert dataset in calls
    assert "UNRELATED_SECRET_BODY" not in serialized
    assert "DATA_DETAILS_NOT_INLINE" not in serialized
    assert tree_bytes(project) == before


def test_visibility_changes_navigation_without_changing_original_records(
    api, project
):
    old = api.create_record(project, "direction", "旧方向", "原来的认识")
    transient = api.create_record(project, "discussion", "临时草稿", "临时内容")
    before = {p: p.read_bytes() for p in (old, transient)}
    routing.set_visibility(
        project, [ref(api, old)], "archive", "当前阶段不再默认展开"
    )
    routing.set_visibility(
        project, [ref(api, transient)], "temporary", "留作工作草稿"
    )
    assert all(p.read_bytes() == value for p, value in before.items())
    assert "旧方向" not in (project / "index.md").read_text(encoding="utf-8")
    assert routing.lookup(project, "旧方向") == []
    hits = routing.lookup(project, "旧方向", include_archive=True)
    assert hits[0]["visibility"] == "archive"
    value = routing.packet(project, "main.review", targets=[ref(api, old)])
    assert value["cards"][0]["id"] == api.read_note(old)[0]["id"]
    assert value["deferred_counts"] == {"archive": 1, "temporary": 1}
    assert (
        next(n for n in value["navigation"] if n.get("ref") == ref(api, old))[
            "visibility"
        ]
        == "archive"
    )
    routing.set_visibility(project, [ref(api, old)], "active", "重新讨论")
    assert routing.lookup(project, "旧方向")
    assert api.validate(project) == []


def test_phase_brief_is_reviewed_scoped_and_does_not_inline_sources(
    api, project, source
):
    set_phase(api, project, source, "prepare")
    draft, evidence = summary(api, project, source, publish=False)
    assert "phase_brief" not in routing.packet(project, "main.open")["context"]
    routing.set_visibility(
        project, [ref(api, evidence)], "archive", "已经进入阶段沉淀"
    )
    routing.publish_summary(
        project,
        draft.relative_to(project).as_posix(),
        api.digest(draft),
        source,
    )
    value = routing.packet(project, "main.open")
    assert value["context"]["phase_brief"]["question"] == "示例核心问题"
    assert "FULL_EVIDENCE_NOT_INLINE" not in json.dumps(value)
    narrowed = routing.packet(project, "pre.protocol")
    assert set(narrowed["context"]["phase_brief"]) == {"question", "next_step"}
    assert api.read_note(project / "init.md")[0]["phase"] == "prepare"


def test_next_phase_summary_does_not_advance_project(api, project, source):
    set_phase(api, project, source, "prepare")
    summary(api, project, source, destination="investigate")
    value = routing.packet(project, "main.status")
    assert value["project"]["phase"] == "prepare"
    assert "phase_brief" not in value["context"]


def test_changed_summary_sources_are_flagged_and_old_claims_not_inlined(
    api, project, source
):
    set_phase(api, project, source, "prepare")
    _, evidence = summary(api, project, source)
    api.update_record(
        project,
        evidence.relative_to(project).as_posix(),
        {},
        api.digest(evidence),
        "assistant",
        "新证据改变认识",
        body="新的实际依据",
    )
    value = routing.packet(project, "main.review")
    assert "phase_brief" not in value["context"]
    assert any("sources changed" in alert for alert in value["alerts"])
    assert any(
        n["reason"] == "reviewed summary for current phase"
        for n in value["navigation"]
    )


def test_sealed_summary_requires_new_draft_and_cannot_be_reopened(
    api, project, source
):
    path, _ = summary(api, project, source)
    relative = path.relative_to(project).as_posix()
    before = path.read_bytes()
    with pytest.raises(ValueError, match="sealed"):
        api.update_record(
            project,
            relative,
            {},
            api.digest(path),
            "human",
            "覆盖旧阶段认识",
            source,
            body="新内容",
        )
    with pytest.raises(ValueError, match="routing.py"):
        api.transition(
            project, relative, "open", api.digest(path), "human", "重开", source
        )
    assert path.read_bytes() == before


def test_noop_cannot_make_an_old_phase_summary_look_newer(api, project, source):
    path, _ = summary(api, project, source)
    before = path.read_bytes()
    with pytest.raises(ValueError, match="sealed"):
        api.update_record(
            project,
            path.relative_to(project).as_posix(),
            {},
            api.digest(path),
            "assistant",
            "刷新旧摘要",
        )
    assert path.read_bytes() == before


def test_recorded_discussion_cannot_be_retagged_as_reviewed_phase_summary(
    api, project
):
    path = api.create_record(
        project, "discussion", "普通讨论", "没有实际阶段审阅"
    )
    relative = path.relative_to(project).as_posix()
    api.transition(
        project, relative, "recorded", api.digest(path), "assistant", "记录讨论"
    )
    before = path.read_bytes()
    with pytest.raises(ValueError, match="source"):
        api.update_record(
            project,
            relative,
            {"purpose": "phase_summary"},
            api.digest(path),
            "assistant",
            "伪造阶段审阅",
        )
    assert path.read_bytes() == before


def test_unreviewed_summary_cannot_be_published_through_generic_transition(
    api, project, source
):
    path, _ = summary(api, project, source, publish=False)
    with pytest.raises(ValueError, match="routing.py"):
        api.transition(
            project,
            path.relative_to(project).as_posix(),
            "recorded",
            api.digest(path),
            "assistant",
            "伪造已审阅",
        )


def test_draft_with_stale_sources_needs_revision_before_publish(
    api, project, source
):
    path, evidence = summary(api, project, source, publish=False)
    api.update_record(
        project,
        evidence.relative_to(project).as_posix(),
        {},
        api.digest(evidence),
        "assistant",
        "更新来源",
        body="改变了的来源",
    )
    with pytest.raises(ValueError, match="sources changed"):
        routing.publish_summary(
            project,
            path.relative_to(project).as_posix(),
            api.digest(path),
            source,
        )


def test_summary_rejects_untraceable_findings_and_non_decisions(api, project):
    evidence = api.create_record(project, "discussion", "来源", "来源正文")
    brief = {
        "question": "一个问题",
        "next_step": {"label": "下一项"},
        "findings": [{"statement": "没有条件和证据的结论"}],
    }
    with pytest.raises(ValueError, match="finding"):
        routing.create_summary(
            project,
            "摘要",
            "prepare",
            "investigate",
            brief,
            [ref(api, evidence)],
            "正文",
        )
    brief.pop("findings")
    brief["decisions"] = [ref(api, evidence)]
    with pytest.raises(ValueError, match="decisions"):
        routing.create_summary(
            project,
            "摘要",
            "prepare",
            "investigate",
            brief,
            [ref(api, evidence)],
            "正文",
        )


def test_large_fields_are_deferred_whole_with_source_navigation(
    api, project, source
):
    init = project / "init.md"
    api.configure(
        project,
        {"research_anchor": {"open_question": "TOO_LONG_TO_INLINE" * 2000}},
        api.digest(init),
        "human",
        "测试长材料",
        source,
    )
    value = routing.packet(project, "main.status", max_chars=2200)
    assert len(json.dumps(value, ensure_ascii=False)) <= 2200
    assert "question" not in value["context"]
    assert any(
        n["path"] == "init.md#research_anchor" for n in value["navigation"]
    )
    assert "TOO_LONG_TO_INLINE" not in json.dumps(value)


def test_missing_archive_does_not_force_init_or_create_directories(tmp_path):
    workspace = tmp_path / "no-archive"
    workspace.mkdir()
    before = list(workspace.iterdir())
    value = routing.packet(workspace, "pre.library")
    assert value["project"] is None
    assert value["route"]["mode"] == "pre.library"
    assert list(workspace.iterdir()) == before


def test_phase_summary_invalidates_when_pinned_settings_are_superseded(
    api, project, source
):
    set_phase(api, project, source, "prepare")
    setting = prep.create_setting(
        project, "data", "dataset", "数据设置", {"version": 1}, "测试定义"
    )
    relative = setting.relative_to(project).as_posix()
    api.transition(
        project, relative, "checked", api.digest(setting), "check", "测试核对"
    )
    prep.freeze(project, relative, api.digest(setting), source, "采用设置")
    pin = prep.pin(project, relative)
    brief = {"question": "当前问题", "next_step": {"label": "先做分析"}}
    path = routing.create_summary(
        project,
        "设置对应的阶段摘要",
        "prepare",
        "prepare",
        brief,
        [ref(api, setting)],
        "正文",
        setting_refs=[pin],
    )
    routing.publish_summary(
        project, path.relative_to(project).as_posix(), api.digest(path), source
    )
    newer = prep.revise(
        project,
        relative,
        api.digest(setting),
        {"version": 2},
        source,
        "修订数据",
        {"summary": "待核对新条件"},
    )
    api.transition(
        project,
        newer.relative_to(project).as_posix(),
        "checked",
        api.digest(newer),
        "check",
        "新条件核对",
    )
    prep.freeze(
        project,
        newer.relative_to(project).as_posix(),
        api.digest(newer),
        source,
        "采用新版",
    )
    value = routing.packet(project, "main.review")
    assert "phase_brief" not in value["context"]
    assert any("sources changed" in a for a in value["alerts"])


def test_changed_index_is_flagged_while_selected_record_is_read_fresh(
    api, project
):
    path = api.create_record(
        project, "resource", "数据", "数据正文", fields={"purpose": "dataset"}
    )
    meta, body = api.read_note(path)
    meta["display_name"] = "人工修订的数据名称"
    path.write_text(api.render(meta, body), encoding="utf-8")
    value = routing.packet(project, "pre.data")
    assert value["cards"][0]["display_name"] == "人工修订的数据名称"
    assert any("Reread changed" in a for a in value["alerts"])
