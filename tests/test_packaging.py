"""验证发布状态、独立安装与共享资源同步。"""

import hashlib
import json
import zipfile
from collections import Counter

import yaml
from conftest import load_module


def test_catalog_exposes_all_28_workflows(build_api):
    catalog = yaml.safe_load(
        (build_api.ROOT / "shared/tool-catalog.yaml").read_text(
            encoding="utf-8"
        )
    )
    tools = catalog["tools"]
    assert len(tools) == 28
    assert Counter(t["collection"] for t in tools) == {
        "main": 7,
        "pre": 6,
        "mid": 8,
        "post": 7,
    }
    assert all(
        t["status"] == "available" and t["entrypoint"] == "rondel-main"
        for t in tools
    )
    assert build_api.check_catalog() == []


def test_shared_sources_and_skill_links_are_complete(build_api):
    assert build_api.sync(check=True) == []
    assert build_api.check_links() == []


def test_install_archive_excludes_private_material_and_is_verifiable(
    build_api, tmp_path
):
    path = build_api.package(tmp_path)
    first_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        assert "rondel-main/SKILL.md" in names
        assert "rondel-main/LICENSE" in names
        assert "rondel-main/scripts/records.py" in names
        assert "rondel-main/assets/templates/init.md" in names
        assert not any(".private" in n or "__pycache__" in n for n in names)
        manifest = json.loads(
            (tmp_path / "rondel-main-0.1.0.manifest.json").read_text(
                encoding="utf-8"
            )
        )
        assert {r["path"] for r in manifest} == set(names)
        assert all(
            hashlib.sha256(archive.read(r["path"])).hexdigest() == r["sha256"]
            for r in manifest
        )
    build_api.package(tmp_path)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == first_hash


def test_installed_helper_can_initialize_without_repository_resources(
    build_api, tmp_path
):
    archive = build_api.package(tmp_path / "release")
    installed = tmp_path / "installed"
    with zipfile.ZipFile(archive) as stream:
        stream.extractall(installed)
    api = load_module(
        "installed_records",
        installed / "rondel-main/scripts/records.py",
    )
    notes = tmp_path / "external-notes"
    api.initialize(
        notes,
        "独立安装示例",
        "先共同澄清问题",
        {
            "kind": "user_message",
            "reference": "synthetic-test/reply",
            "quote": "在这里创建示例笔记。",
        },
    )
    archive_root = notes / ".rondal"
    assert api.read_note(archive_root / "init.md")[0]["status"] == "listening"
    assert {p.name for p in notes.iterdir()} == {".rondal"}
    assert api.validate(notes) == []
    resource_api = load_module(
        "installed_resources", installed / "rondel-main/scripts/resources.py"
    )
    assert resource_api.inventory(notes)["candidate_hosts"] == []
    view_api = load_module(
        "installed_views", installed / "rondel-main/scripts/note_views.py"
    )
    view = view_api.export_note(notes, "init.md", tmp_path / "Vault/Project")
    assert view.is_file()
    prep_api = load_module(
        "installed_preparation",
        installed / "rondel-main/scripts/preparation.py",
    )
    board = prep_api.initialize(
        notes,
        {
            "kind": "user_message",
            "reference": "synthetic-test/preparation",
            "quote": "在隔离样例中初始化前期跟踪。",
        },
    )
    assert board.is_file()
    assert not prep_api.status(notes)["checklist_complete"]
    router_api = load_module(
        "installed_routing", installed / "rondel-main/scripts/routing.py"
    )
    packet = router_api.packet(notes, "main.status")
    assert (
        packet["project"]["id"]
        == api.read_note(archive_root / "init.md")[0]["project_id"]
    )
    assert packet["route"]["mode"] == "main.status"
    seed = router_api.intent_seed("核对协议", runtime="codex")
    assert seed["preferred_profile"]["model"] == "gpt-6-luna"
    assert (
        installed / "rondel-main/assets/agents/claude/rondel-router.md"
    ).is_file()
    checker = load_module(
        "installed_evidence", installed / "rondel-main/scripts/evidence.py"
    )
    assert callable(checker.preflight)
    delivery = load_module(
        "installed_closeout", installed / "rondel-main/scripts/closeout.py"
    )
    assert callable(delivery.build)
    assert (
        router_api.packet(notes, "post.write")["route"]["mode"] == "post.write"
    )
    assert (
        router_api.packet(notes, "post.closeout")["route"]["mode"]
        == "post.closeout"
    )
