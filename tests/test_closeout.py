"""验证研究交付只复制显式文件，保留来源与真实验证边界。"""

import json

import pytest
from conftest import ROOT, load_module

closeout = load_module(
    "closeout_test", ROOT / "skills/rondel-main/scripts/closeout.py"
)
router = load_module(
    "closeout_router", ROOT / "skills/rondel-main/scripts/routing.py"
)


def request(project):
    source = project / "paper"
    source.mkdir()
    (source / "reproduction.md").write_text(
        "样例命令尚未运行。", encoding="utf-8"
    )
    (source / "materials.md").write_text("问题与资料入口。", encoding="utf-8")
    (source / "private.env").write_text("PRIVATE_UNLISTED", encoding="utf-8")
    return {
        "release_id": "synthetic-v1",
        "items": [
            {
                "package": "reproduction",
                "source": "paper/reproduction.md",
                "target": "README.md",
            },
            {
                "package": "materials",
                "source": "paper/materials.md",
                "target": "README.md",
            },
        ],
        "references": [
            {
                "package": "reproduction",
                "location": "host-a:/weights/model.pt",
                "description": "仅记录实际外部入口",
            }
        ],
    }


def test_plan_is_read_only_and_export_does_not_change_project(api, project):
    selected = request(project)
    before = {p: p.read_bytes() for p in project.rglob("*") if p.is_file()}
    assert len(closeout.plan(project, selected)["files"]) == 2
    assert before == {
        p: p.read_bytes() for p in project.rglob("*") if p.is_file()
    }
    destination = closeout.build(project, selected)
    for path, value in before.items():
        assert path.read_bytes() == value
    assert destination.parent == project / "deliverables"
    assert not any(p.name == "private.env" for p in destination.rglob("*"))
    value = closeout.verify(project, selected["release_id"])
    assert value == {
        "file_integrity_ok": True,
        "issues": [],
        "reproduction_verified": False,
        "references_fetched": False,
    }
    manifest = json.loads(
        (destination / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["references"] == selected["references"]
    assert str(project) not in json.dumps(manifest)
    assert api.read_note(project / "init.md")[0]["phase"] == "init"
    assert api.validate(project) == []


def test_existing_release_is_never_overwritten(project):
    selected = request(project)
    destination = closeout.build(project, selected)
    edited = destination / "materials/README.md"
    edited.write_text("研究者的后续修改", encoding="utf-8")
    with pytest.raises(FileExistsError):
        closeout.build(project, selected)
    assert edited.read_text(encoding="utf-8") == "研究者的后续修改"
    assert closeout.verify(project, selected["release_id"])["issues"] == [
        "materials/README.md"
    ]


@pytest.mark.parametrize(
    "target", ["../escape.md", "/absolute.md", "C:/escape.md", "a\\b.md"]
)
def test_invalid_destinations_do_not_create_delivery(project, target):
    selected = request(project)
    selected["items"][0]["target"] = target
    with pytest.raises(ValueError, match="safe relative"):
        closeout.build(project, selected)
    assert not (project / "deliverables").exists()


def test_missing_file_or_entry_point_is_reported_before_writing(project):
    selected = request(project)
    selected["items"][0]["source"] = "paper/missing.py"
    with pytest.raises(ValueError, match="existing regular"):
        closeout.build(project, selected)
    selected["items"] = selected["items"][1:]
    with pytest.raises(ValueError, match="README"):
        closeout.build(project, selected)
    assert not (project / "deliverables").exists()


def test_case_collisions_and_directory_sources_are_rejected(project):
    selected = request(project)
    selected["items"].append({**selected["items"][0], "target": "readme.md"})
    with pytest.raises(ValueError, match="conflicting"):
        closeout.plan(project, selected)
    selected["items"] = selected["items"][:2]
    selected["items"][0]["source"] = "paper"
    with pytest.raises(ValueError, match="existing regular"):
        closeout.plan(project, selected)


@pytest.mark.parametrize(
    "phase", ["init", "prepare", "investigate", "converge", "write", "submit"]
)
def test_any_phase_can_close_with_actual_user_choice(
    api, project, source, phase
):
    init = project / "init.md"
    source = {
        **source,
        "reference": "synthetic/closeout",
        "quote": "结束本轮研究，保留未解项并归档。",
    }
    if phase != "init":
        api.configure(
            project,
            {
                "phase": phase,
                "status": "ready",
                "ready_for": "exploration",
                "research_anchor": {"open_question": "合成问题"},
                "next_step": {"label": "合成任务"},
            },
            api.digest(init),
            "human",
            "接入已有材料",
            source,
        )
    before = init.read_bytes()
    with pytest.raises(api.RecordError, match="human"):
        api.configure(
            project,
            {"phase": "archived"},
            api.digest(init),
            "assistant",
            "AI 推测应该结束",
        )
    assert init.read_bytes() == before
    api.configure(
        project,
        {"phase": "archived"},
        api.digest(init),
        "human",
        "用户选择结束合成项目",
        source,
    )
    assert api.read_note(init)[0]["phase"] == "archived"


def test_delivery_context_does_not_pull_other_project_tasks(api, project):
    current = api.create_record(
        project,
        "discussion",
        "当前收尾",
        "当前材料",
        fields={"purpose": "project_closeout"},
    )
    api.create_record(
        project,
        "discussion",
        "其他交付",
        "PRIVATE_OTHER",
        fields={"purpose": "materials_package"},
    )
    ref = "record:" + api.read_note(current)[0]["id"]
    value = router.packet(project, "post.closeout", [ref])
    assert value["route"]["mode"] == "post.closeout"
    assert {c["id"] for c in value["cards"]} == {
        api.read_note(current)[0]["id"]
    }
    assert "PRIVATE_OTHER" not in json.dumps(value)
