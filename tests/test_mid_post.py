"""验证中后期路由可加载且不会按类型扩大上下文。"""

import json

import pytest
from conftest import ROOT, load_module

router = load_module(
    "mid_post_router", ROOT / "skills/rondel-main/scripts/routing.py"
)
MODES = [
    "mid.issue",
    "mid.retrieve",
    "mid.design",
    "mid.implement",
    "mid.preflight",
    "mid.execute",
    "mid.inspect",
    "mid.analyze",
    "post.converge",
    "post.mechanisms",
    "post.claims",
    "post.visualize",
    "post.write",
    "post.submission",
    "post.closeout",
]


def ref(api, path):
    return "record:" + api.read_note(path)[0]["id"]


@pytest.mark.parametrize("mode", MODES)
def test_mid_post_mode_routes_without_unrelated_bodies(api, project, mode):
    other = api.create_record(
        project, "discussion", "其他任务", "UNRELATED_MID_POST_BODY" * 200
    )
    before = {p: p.read_bytes() for p in project.rglob("*") if p.is_file()}
    value = router.packet(project, mode)
    assert value["route"]["mode"] == mode
    assert (
        value["route"]["instruction"]
        == "references/" + mode.replace(".", "-") + ".md"
    )
    assert "UNRELATED_MID_POST_BODY" not in json.dumps(value)
    assert (
        other.relative_to(project).as_posix()
        not in api.context_paths(project, mode)["files"]
    )
    assert before == {
        p: p.read_bytes() for p in project.rglob("*") if p.is_file()
    }


def test_new_modes_enter_small_seed_as_canonical_names():
    seed = router.intent_seed("依据有效结果核对主张与局限。")
    assert len(seed["allowed_modes"]) == 29
    assert set(MODES) <= set(seed["allowed_modes"])
    assert not any(
        m.startswith("main.mid.") or m.startswith("main.post.")
        for m in seed["allowed_modes"]
    )


def test_inspection_scoped_to_experiment_not_shared_dataset(
    api, project, monkeypatch
):
    data = api.create_record(
        project, "resource", "共享数据", "数据", fields={"purpose": "dataset"}
    )
    exp = api.create_record(
        project, "experiment", "本轮方案", "方案", refs=[ref(api, data)]
    )
    other = api.create_record(
        project, "experiment", "其他方案", "方案", refs=[ref(api, data)]
    )
    run_a = api.create_record(
        project, "run", "本轮产物", "本轮原文", refs=[ref(api, exp)]
    )
    run_b = api.create_record(
        project, "run", "无关产物", "PRIVATE_OTHER_RUN", refs=[ref(api, other)]
    )
    init = project / "init.md"
    api.configure(
        project,
        {
            "next_step": {
                "experiment_ref": ref(api, exp),
                "label": "只核对本轮产物",
            }
        },
        api.digest(init),
        "assistant",
        "定位已指定任务",
    )
    calls = []
    original = router.records.read_note

    def observe(path):
        calls.append(path)
        return original(path)

    monkeypatch.setattr(router.records, "read_note", observe)
    value = router.packet(project, "mid.inspect")
    identifiers = {c["id"] for c in value["cards"]}
    assert api.read_note(run_a)[0]["id"] in identifiers
    assert (
        api.read_note(run_b)[0]["id"] not in identifiers and run_b not in calls
    )
    assert "PRIVATE_OTHER_RUN" not in json.dumps(value)


def test_analysis_follows_run_to_report_without_other_branch(api, project):
    exp = api.create_record(project, "experiment", "当前方案", "方案")
    run = api.create_record(
        project,
        "run",
        "当前运行",
        "运行",
        fields={"experiment_ref": ref(api, exp)},
    )
    report = api.create_record(
        project,
        "discussion",
        "当前分析",
        "分析",
        refs=["project:" + run.relative_to(project).as_posix()],
        fields={"purpose": "experiment_analysis"},
    )
    unrelated = api.create_record(
        project,
        "discussion",
        "其他分析",
        "其他证据",
        fields={"purpose": "experiment_analysis"},
    )
    value = router.packet(project, "mid.analyze", [ref(api, exp)])
    identifiers = {c["id"] for c in value["cards"]}
    assert api.read_note(report)[0]["id"] in identifiers
    assert api.read_note(unrelated)[0]["id"] not in identifiers


def test_without_task_anchor_runs_are_not_loaded_globally(api, project):
    api.create_record(project, "run", "过去运行", "旧日志")
    api.create_record(project, "claim", "其他认识", "其他主张")
    api.create_record(
        project,
        "discussion",
        "其他分析",
        "PRIVATE_ANALYSIS",
        fields={"purpose": "experiment_analysis"},
    )
    value = router.packet(project, "mid.execute")
    assert value["cards"] == []
    assert any("Select a task" in warning for warning in value["alerts"])
    assert router.packet(project, "mid.analyze")["cards"] == []


def test_explicit_target_overrides_previous_task_anchor(api, project):
    old = api.create_record(project, "experiment", "上次方案", "旧任务")
    old_run = api.create_record(
        project, "run", "上次运行", "旧产物", refs=[ref(api, old)]
    )
    selected = api.create_record(
        project, "experiment", "本次指定方案", "当前任务"
    )
    selected_run = api.create_record(
        project, "run", "本次运行", "当前产物", refs=[ref(api, selected)]
    )
    init = project / "init.md"
    api.configure(
        project,
        {"next_step": {"experiment_ref": ref(api, old)}},
        api.digest(init),
        "assistant",
        "旧任务位置",
    )
    value = router.packet(project, "mid.inspect", [ref(api, selected)])
    identifiers = {c["id"] for c in value["cards"]}
    assert api.read_note(selected_run)[0]["id"] in identifiers
    assert api.read_note(old)[0]["id"] not in identifiers
    assert api.read_note(old_run)[0]["id"] not in identifiers


def test_manuscript_scope_selects_linked_claims_only(api, project):
    claim = api.create_record(project, "claim", "中心认识", "候选认识")
    unrelated = api.create_record(project, "claim", "其他方向", "无关认识")
    manuscript = api.create_record(
        project,
        "discussion",
        "当前稿件",
        "稿件",
        refs=[ref(api, claim)],
        fields={"purpose": "manuscript"},
    )
    identifiers = {
        c["id"]
        for c in router.packet(project, "post.write", [ref(api, manuscript)])[
            "cards"
        ]
    }
    assert api.read_note(claim)[0]["id"] in identifiers
    assert api.read_note(unrelated)[0]["id"] not in identifiers
