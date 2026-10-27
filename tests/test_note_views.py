"""验证视图保留研究者编辑，并将反馈与正式状态分开。"""

import json

import pytest
from conftest import ROOT, load_module

views = load_module(
    "note_views", ROOT / "skills/rondel-main/scripts/note_views.py"
)


def note(api, project, *, refs=None):
    return api.create_record(
        project,
        "discussion",
        "论文理解：时序与语义",
        "# 当前理解\n\n研究者自己的说明。\n\n$$\na_t=b_t+c_t\n$$\n",
        refs=refs,
    )


def feedback_source():
    return {
        "kind": "user_note",
        "reference": "synthetic/obsidian-feedback",
        "quote": "请审阅我在这份笔记中写下的批注。",
    }


def test_obsidian_view_has_flat_properties_and_preserves_math(
    api, project, tmp_path
):
    path = note(api, project)
    before = path.read_bytes()
    view = views.export_note(
        project.parent,
        path.relative_to(project).as_posix(),
        tmp_path / "Vault/Project",
    )
    properties, body = api.read_note(view)
    assert properties["rondel_id"] == api.read_note(path)[0]["id"]
    assert properties["aliases"] == ["论文理解：时序与语义"]
    assert all(not isinstance(value, dict) for value in properties.values())
    assert "$$\na_t=b_t+c_t\n$$" in body
    assert path.read_bytes() == before
    assert not (tmp_path / "Vault/.obsidian").exists()
    again = views.export_note(
        project, path.relative_to(project).as_posix(), view.parent
    )
    assert again == view


def test_related_exported_notes_have_native_links(api, project, tmp_path):
    first = note(api, project)
    first_id = api.read_note(first)[0]["id"]
    destination = tmp_path / "Vault/Project"
    first_view = views.export_note(
        project, first.relative_to(project).as_posix(), destination
    )
    second = note(api, project, refs=["record:" + first_id])
    second_view = views.export_note(
        project, second.relative_to(project).as_posix(), destination
    )
    assert f"[[{first_view.stem}|" in second_view.read_text(encoding="utf-8")


def test_view_filenames_handle_windows_and_wikilink_delimiters(
    api, project, tmp_path
):
    title = "方法 [A] #1 | 对照：新设定"
    path = api.create_record(project, "discussion", title, "当前问题。")
    view = views.export_note(
        project,
        path.relative_to(project).as_posix(),
        tmp_path / "Vault/Project",
    )
    assert not any(character in view.name for character in '<>:"/\\|?*#[]^')
    assert api.read_note(view)[0]["aliases"] == [title]


def test_edited_view_is_preserved_and_captured_once(api, project, tmp_path):
    path = note(api, project)
    original = path.read_bytes()
    view = views.export_note(
        project,
        path.relative_to(project).as_posix(),
        tmp_path / "Vault/Project",
    )
    with view.open("a", encoding="utf-8") as stream:
        stream.write("\n我希望进一步核对这项对照。\n")
    edited = view.read_bytes()
    with pytest.raises(ValueError, match="edited"):
        views.export_note(
            project, path.relative_to(project).as_posix(), view.parent
        )
    captured = views.capture_feedback(project, view, feedback_source())
    meta, body = api.read_note(captured)
    assert meta["purpose"] == "note_feedback"
    assert meta["resolution"] == "pending_review"
    assert "我希望进一步核对这项对照" in body
    assert views.capture_feedback(project, view, feedback_source()) == captured
    assert view.read_bytes() == edited
    assert path.read_bytes() == original
    assert api.validate(project) == []


def test_view_feedback_never_rewrites_approved_experiment(
    api, project, source, tmp_path
):
    path = api.create_record(
        project,
        "experiment",
        "冻结的方案",
        "方案正文。",
        fields={
            "hypothesis": "候选假设",
            "expected_result": "预期行为",
            "falsification": "削弱解释的行为",
            "scope": {"runs": 1},
        },
    )
    for state, actor, origin in [
        ("reviewable", "assistant", None),
        ("approved", "human", source),
    ]:
        api.transition(
            project,
            path.relative_to(project).as_posix(),
            state,
            api.digest(path),
            actor,
            "Synthetic plan state",
            origin,
        )
    before = path.read_bytes()
    view = views.export_note(
        project,
        path.relative_to(project).as_posix(),
        tmp_path / "Vault/Project",
    )
    view.write_text(
        view.read_text(encoding="utf-8") + "\n建议增加十次运行。",
        encoding="utf-8",
    )
    views.capture_feedback(project, view, feedback_source())
    assert path.read_bytes() == before
    assert api.read_note(path)[0]["approval"]["scope"] == {"runs": 1}


def test_feedback_notes_source_revision_drift(api, project, tmp_path):
    path = note(api, project)
    view = views.export_note(
        project,
        path.relative_to(project).as_posix(),
        tmp_path / "Vault/Project",
    )
    api.update_record(
        project,
        path.relative_to(project).as_posix(),
        {},
        api.digest(path),
        "assistant",
        "Synthetic current-note update",
        body="较新的研究说明。",
    )
    view.write_text(
        view.read_text(encoding="utf-8") + "\n旧视图上的批注。",
        encoding="utf-8",
    )
    captured = views.capture_feedback(project, view, feedback_source())
    assert api.read_note(captured)[0]["source_has_advanced"] is True
    assert api.read_note(path)[1] == "较新的研究说明。\n"


def test_unowned_view_collision_is_not_overwritten(api, project, tmp_path):
    path = note(api, project)
    view = views.export_note(
        project,
        path.relative_to(project).as_posix(),
        tmp_path / "Vault/Project",
    )
    original = view.read_bytes()
    manifest = project / ".state/note-views.json"
    manifest.write_text(
        json.dumps({"schema_version": 1, "exports": {}, "captures": {}}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unowned"):
        views.export_note(
            project, path.relative_to(project).as_posix(), view.parent
        )
    assert view.read_bytes() == original


def test_canonical_hidden_directory_cannot_be_view_destination(api, project):
    path = note(api, project)
    with pytest.raises(ValueError, match="outside"):
        views.export_note(
            project, path.relative_to(project).as_posix(), project / "views"
        )


def test_workspace_root_is_not_used_for_note_views(api, project):
    path = note(api, project)
    with pytest.raises(ValueError, match="workspace root"):
        views.export_note(
            project, path.relative_to(project).as_posix(), project.parent
        )


def test_markdown_adapter_and_unchanged_feedback(api, project, tmp_path):
    path = note(api, project)
    view = views.export_note(
        project,
        path.relative_to(project).as_posix(),
        tmp_path / "Notes",
        "markdown",
    )
    assert api.read_note(view)[0]["rondel_format"] == "markdown"
    assert views.capture_feedback(project, view, feedback_source()) is None


def test_view_status_is_read_only_and_detects_user_edits(
    api, project, tmp_path
):
    path = note(api, project)
    view = views.export_note(
        project,
        path.relative_to(project).as_posix(),
        tmp_path / "Vault/Project",
    )
    view.write_text(
        view.read_text(encoding="utf-8") + "\n新的理解。", encoding="utf-8"
    )
    before = {str(p): p.read_bytes() for p in project.rglob("*") if p.is_file()}
    status = views.view_status(project.parent)
    assert status[0]["edited"] is True
    assert status[0]["source_has_advanced"] is False
    assert before == {
        str(p): p.read_bytes() for p in project.rglob("*") if p.is_file()
    }
