"""验证用户文字、来源和并发修改得到保留。"""

import pytest


def test_intake_preserves_uncertainty_and_selected_location(api, project):
    meta, body = api.read_note(project / "init.md")
    assert meta["status"] == "listening"
    assert meta["research_anchor"]["problem"] == ""
    assert meta["research_anchor"]["direction_status"] == "exploring"
    assert meta["bindings"] == {}
    assert meta["collaboration"]["execution"] == "discussion"
    assert "用户关切" in body
    assert not (project / "experiments").exists()


def test_repeated_init_cannot_overwrite_user_record(api, project, source):
    path = project / "init.md"
    before = path.read_bytes()
    with pytest.raises(api.RecordError, match="already exists"):
        api.initialize(project, "new", "new", source)
    assert path.read_bytes() == before


def test_workspace_records_stay_inside_hidden_archive(api, tmp_path, source):
    workspace = tmp_path / "existing workspace"
    workspace.mkdir()
    user_file = workspace / "research.py"
    user_file.write_text("user content", encoding="utf-8")
    path = api.initialize(workspace, "研究", "先澄清问题", source)
    assert path == workspace / ".rondal/init.md"
    record = api.create_record(workspace, "discussion", "当前计划", "计划建议")
    assert record.is_relative_to(workspace / ".rondal")
    assert {p.name for p in workspace.iterdir()} == {"research.py", ".rondal"}
    assert user_file.read_text(encoding="utf-8") == "user content"
    assert api.archive_root(workspace / ".rondal") == workspace / ".rondal"
    assert api.validate(workspace) == []


@pytest.mark.parametrize("preexisting_archive", [False, True])
def test_legacy_archive_needs_migration_before_new_writes(
    api, tmp_path, project, source, preexisting_archive
):
    legacy = tmp_path / "legacy"
    legacy.mkdir()
    (legacy / "init.md").write_bytes((project / "init.md").read_bytes())
    if preexisting_archive:
        (legacy / ".rondal").mkdir()
    before = (legacy / "init.md").read_bytes()
    with pytest.raises(api.RecordError, match="migrate"):
        api.initialize(legacy, "new", "new", source)
    assert (legacy / "init.md").read_bytes() == before
    assert not (legacy / ".rondal/init.md").exists()
    if preexisting_archive:
        assert not any((legacy / ".rondal").iterdir())
    else:
        assert not (legacy / ".rondal").exists()


def test_configure_saves_synthesis_with_previous_body_in_history(
    api, project, source
):
    path = project / "init.md"
    before = path.read_bytes()
    body = "完整的用户理解段落。\n\n推荐计划与阶段排期。\n"
    api.configure(
        project,
        {"status": "reviewable"},
        api.digest(path),
        "human",
        "保存可共同修订的理解与计划",
        source,
        body=body,
    )
    meta, saved_body = api.read_note(path)
    assert saved_body == body
    assert meta["revision"] == 2
    assert any(
        p.read_bytes() == before for p in (project / "history").rglob("*.md")
    )
    assert api.validate(project) == []


def test_configure_preserves_body_and_archives_previous_version(
    api, project, source
):
    path = project / "init.md"
    with path.open("a", encoding="utf-8") as stream:
        stream.write("\n导师与我共同写下的说明。\n")
    before = path.read_bytes()
    api.configure(
        project,
        {"bindings": {"papers": "existing-library"}},
        api.digest(path),
        "human",
        "用户指定论文库",
        source,
    )
    assert "导师与我共同写下的说明" in path.read_text(encoding="utf-8")
    archived = list((project / "history").rglob("*.md"))
    assert any(p.read_bytes() == before for p in archived)
    assert api.read_note(path)[0]["revision"] == 2


def test_stale_write_rejected_without_overwriting_manual_edit(
    api, project, source
):
    path = project / "init.md"
    expected = api.digest(path)
    with path.open("a", encoding="utf-8") as stream:
        stream.write("\n用户刚刚补充的材料。\n")
    before = path.read_bytes()
    with pytest.raises(api.RecordError, match="reread"):
        api.configure(
            project,
            {"display_name": "updated"},
            expected,
            "human",
            "用户修正",
            source,
        )
    assert path.read_bytes() == before


def test_index_preserves_human_sections(api, project):
    path = project / "index.md"
    with path.open("a", encoding="utf-8") as stream:
        stream.write("\n## 我自己的入口\n这段文字需要保留。\n")
    api.create_record(project, "discussion", "分类错误的可能解释", "具体观察。")
    api.reindex(project)
    text = path.read_text(encoding="utf-8")
    assert "这段文字需要保留" in text
    assert "分类错误的可能解释" in text
    assert text.count("<!-- rondel:index:start -->") == 1


def test_candidate_does_not_change_confirmed_mainline(api, project):
    before = (project / "init.md").read_bytes()
    api.create_record(project, "direction", "另一种候选解释", "暂时的建议。")
    assert (project / "init.md").read_bytes() == before


@pytest.mark.parametrize("relative", ["../outside.md", "../../init.md"])
def test_path_escape_rejected(api, project, relative):
    with pytest.raises(api.RecordError, match="leaves"):
        api.within(project, relative)


def test_absolute_path_outside_root_rejected(api, project, tmp_path):
    with pytest.raises(api.RecordError, match="leaves"):
        api.within(project, str(tmp_path / "outside.md"))


def test_duplicate_yaml_key_rejected(api, tmp_path):
    path = tmp_path / "bad.md"
    path.write_text(
        "---\nstatus: draft\nstatus: approved\n---\nbody", encoding="utf-8"
    )
    with pytest.raises(api.RecordError, match="Duplicate"):
        api.read_note(path)


def test_only_explicit_human_source_can_record_a_decision(api, project):
    with pytest.raises(api.RecordError, match="current user"):
        api.decide(
            project,
            "决定",
            "内容",
            {"kind": "heartbeat", "reference": "old", "quote": "继续"},
        )


def test_decision_keeps_actual_source(api, project, source):
    path = api.decide(project, "先了解错误行为", "用户选择先做分析。", source)
    meta, _ = api.read_note(path)
    assert meta["source"] == source
    assert meta["status"] == "recorded"
    assert api.validate(project) == []


def test_internal_reference_is_validated(api, project):
    api.create_record(
        project, "discussion", "缺少引用", "正文", ["record:missing"]
    )
    assert any("Missing record" in x for x in api.validate(project))


def test_foreign_project_record_rejected(api, project):
    path = api.create_record(project, "question", "某个问题", "正文")
    meta, body = api.read_note(path)
    meta["project_id"] = "another-project"
    path.write_text(api.render(meta, body), encoding="utf-8")
    assert any("different project" in x for x in api.validate(project))


def test_existing_lock_does_not_get_deleted(api, project):
    lock = project / ".state/write.lock"
    lock.write_text("existing writer", encoding="utf-8")
    with pytest.raises(api.RecordError, match="locked"):
        api.create_record(project, "discussion", "记录", "正文")
    assert lock.read_text(encoding="utf-8") == "existing writer"
