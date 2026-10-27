"""验证新项目首先落盘、旧档案迁移和无第三方环境的安装入口。"""

import json
import os
import subprocess
import sys
import zipfile

import pytest
from conftest import ROOT, load_module

routing = load_module(
    "entry_routing", ROOT / "skills/rondel-main/scripts/routing.py"
)


def tree(root):
    return {
        str(p.relative_to(root)): p.read_bytes()
        for p in root.rglob("*")
        if p.is_file()
    }


def test_new_entry_saves_listening_intake_before_routing(api, tmp_path, source):
    workspace = tmp_path / "项目 with spaces"
    workspace.mkdir()
    (workspace / "existing.md").write_text("已有材料", encoding="utf-8")
    value = routing.enter(
        workspace, "带我开始吧", source, initialize_missing=True
    )
    assert value["initialized"] and value["persistence_verified"]
    assert value["next_action"] == "init" and "intent_seed" not in value
    init = workspace / ".rondel/init.md"
    meta, _ = api.read_note(init)
    assert meta["status"] == "listening" and meta["phase"] == "init"
    assert meta["research_anchor"]["user_statement"] == "带我开始吧"
    assert {p.name for p in workspace.iterdir()} == {"existing.md", ".rondel"}
    assert (workspace / "existing.md").read_text(encoding="utf-8") == "已有材料"
    assert api.validate(workspace) == []


def test_probe_and_read_only_entry_do_not_initialize(tmp_path):
    value = routing.enter(tmp_path, "只看已有进展", read_only=True)
    assert value["next_action"] == "init" and not list(tmp_path.iterdir())
    with pytest.raises(ValueError, match="Read-only"):
        routing.enter(tmp_path, "查看", initialize_missing=True, read_only=True)


def test_initialization_requires_actual_source_before_writing(tmp_path):
    with pytest.raises(ValueError, match="source"):
        routing.enter(tmp_path, "带我开始", initialize_missing=True)
    assert not list(tmp_path.iterdir())


def test_existing_entry_only_builds_small_seed(api, project, source):
    init = project / "init.md"
    api.configure(
        project,
        {"next_step": {"label": "阅读一张方法图"}},
        api.digest(init),
        "assistant",
        "定位下一步",
        body="PRIVATE_FULL_INTAKE" * 200,
    )
    api.create_record(
        project, "discussion", "不相关材料", "PRIVATE_RESEARCH_BODY" * 200
    )
    before = tree(project)
    value = routing.enter(project.parent, "继续核对数据协议", read_only=True)
    assert value["next_action"] == "route" and not value["initialized"]
    seed = value["intent_seed"]
    assert (
        seed["context_hint"]["project_id"]
        == api.read_note(init)[0]["project_id"]
    )
    assert seed["context_hint"]["task_label"] == "阅读一张方法图"
    assert "PRIVATE_" not in json.dumps(value)
    assert tree(project) == before


def test_legacy_spelling_is_renamed_without_changing_records(
    api, project, source
):
    before = tree(project)
    legacy = project.parent / ".rondal"
    project.rename(legacy)
    assert routing.discover(legacy.parent)["candidates"][0]["archive"] == str(
        legacy
    )
    value = routing.enter(legacy.parent, "修复旧目录并继续", source)
    assert value["repairs"] and value["next_action"] == "route"
    assert not legacy.exists() and tree(project) == before
    assert api.validate(project.parent) == []


def test_read_only_entry_keeps_legacy_archive(api, project):
    legacy = project.parent / ".rondal"
    project.rename(legacy)
    before = tree(legacy)
    value = routing.enter(legacy.parent, "只查看", read_only=True)
    assert value["next_action"] == "repair_legacy_archive"
    assert tree(legacy) == before and not project.exists()


def test_two_archives_are_reported_without_merging(api, project, source):
    legacy = project.parent / ".rondal"
    legacy.mkdir()
    (legacy / "init.md").write_bytes((project / "init.md").read_bytes())
    before = tree(project.parent)
    value = routing.enter(
        project.parent, "继续", source, initialize_missing=True
    )
    assert value["next_action"] == "resolve_archive_conflict"
    assert tree(project.parent) == before


def test_active_legacy_archive_is_not_moved(api, project, source):
    legacy = project.parent / ".rondal"
    project.rename(legacy)
    lock = legacy / ".state/write.lock"
    lock.write_text("active writer", encoding="utf-8")
    with pytest.raises(ValueError, match="active write"):
        routing.enter(legacy.parent, "继续", source)
    assert lock.exists() and not project.exists()


def test_explicit_workspace_does_not_reuse_parent_project(api, project, source):
    selected = project.parent / "另一个明确指定的项目"
    selected.mkdir()
    value = routing.enter(
        selected, "在这里开始", source, initialize_missing=True
    )
    assert value["archive"] == str(selected / ".rondel")
    assert (
        value["project"]["id"]
        != api.read_note(project / "init.md")[0]["project_id"]
    )


def test_installed_entry_runs_without_site_packages(
    build_api, tmp_path, source
):
    archive = build_api.package(tmp_path / "release")
    installed = tmp_path / "installed"
    with zipfile.ZipFile(archive) as stream:
        stream.extractall(installed)
    workspace = tmp_path / "新工作区 with spaces"
    workspace.mkdir()
    request = tmp_path / "entry.json"
    request.write_text(
        json.dumps(
            {
                "request": "带我开始",
                "source": source,
                "initialize_missing": True,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    env.pop("PYTHONPATH", None)
    args = [
        sys.executable,
        "-S",
        str(installed / "rondel-main/scripts/routing.py"),
        "enter",
        "--root",
        str(workspace),
        "--request",
        str(request),
    ]
    first = subprocess.run(
        args,
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    assert json.loads(first.stdout)["persistence_verified"]
    second = subprocess.run(
        args,
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    assert json.loads(second.stdout)["next_action"] == "route"
    assert (workspace / ".rondel/init.md").exists()
