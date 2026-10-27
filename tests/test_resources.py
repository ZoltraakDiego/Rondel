"""机器汇总只使用有来源的观测，不执行远程命令。"""

import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest
from conftest import ROOT, load_module

resources = load_module(
    "resource_inventory", ROOT / "skills/rondel-main/scripts/resources.py"
)
NOW = datetime(2026, 10, 25, 12, tzinfo=UTC)


def machine(api, project, host, *, age=0, checked=True, devices=None):
    path = api.create_record(
        project,
        "resource",
        host,
        "Synthetic machine observation.",
        fields={
            "purpose": "machine",
            "host_id": host,
            "transport": "ssh",
            "connection_ref": "existing-lab-alias",
            "system": "linux",
            "locations": {"code": "/srv/project", "data": "/data/videos"},
            "observation": {
                "at": (NOW - timedelta(seconds=age)).isoformat(),
                "availability": "available",
                "source": "synthetic/device-observation",
                "gpus": devices
                or [{"id": "0", "available": True, "free_memory_gb": 24}],
            },
        },
    )
    if checked:
        api.transition(
            project,
            path.relative_to(project).as_posix(),
            "checked",
            api.digest(path),
            "assistant",
            "Synthetic resource check",
        )
    return path


@pytest.mark.parametrize("native_timestamp", [False, True])
def test_remote_paths_and_read_only_inventory(api, project, native_timestamp):
    path = machine(api, project, "lab-a")
    if native_timestamp:
        meta, _ = api.read_note(path)
        observed = dict(meta["observation"], at=NOW)
        api.update_record(
            project,
            path.relative_to(project).as_posix(),
            {"observation": observed},
            api.digest(path),
            "assistant",
            "Synthetic native YAML timestamp",
        )
    before = {str(p): p.read_bytes() for p in project.rglob("*") if p.is_file()}
    result = resources.inventory(
        project.parent, gpu_count=1, gpu_memory_gb=20, now=NOW
    )
    assert result["candidate_hosts"] == ["lab-a"]
    assert result["machines"][0]["locations"]["data"] == "/data/videos"
    assert result["machines"][0]["requires_preflight"] is True
    assert result["reservation_created"] is False
    assert json.loads(json.dumps(result))["candidate_hosts"] == ["lab-a"]
    assert before == {
        str(p): p.read_bytes() for p in project.rglob("*") if p.is_file()
    }


@pytest.mark.parametrize("age,checked", [(3601, True), (-1, True), (0, False)])
def test_stale_future_or_unchecked_machines_are_not_candidates(
    api, project, age, checked
):
    machine(api, project, "lab-a", age=age, checked=checked)
    assert resources.inventory(project, now=NOW)["candidate_hosts"] == []


def test_memory_requirement_is_per_device_not_summed(api, project):
    machine(
        api,
        project,
        "mixed-gpus",
        devices=[
            {"id": "0", "available": True, "free_memory_gb": 24},
            {"id": "1", "available": True, "free_memory_gb": 12},
        ],
    )
    result = resources.inventory(
        project, gpu_count=2, gpu_memory_gb=20, now=NOW
    )
    assert result["candidate_hosts"] == []
    single = resources.inventory(project, gpu_memory_gb=20, now=NOW)
    assert single["requirements"]["gpu_count"] == 1
    assert single["machines"][0]["candidate_gpu_ids"] == ["0"]


def test_missing_source_or_duplicate_gpu_cannot_inflate_capacity(api, project):
    path = machine(api, project, "lab-a")
    meta, _ = api.read_note(path)
    observed = deepcopy(meta["observation"])
    observed.pop("source")
    observed["gpus"] *= 2
    api.update_record(
        project,
        path.relative_to(project).as_posix(),
        {"observation": observed},
        api.digest(path),
        "assistant",
        "Synthetic invalid observation",
    )
    result = resources.inventory(project, gpu_count=2, now=NOW)
    assert result["candidate_hosts"] == []
    reasons = result["machines"][0]["reasons"]
    assert "observation_source_missing" in reasons
    assert "gpu_identifiers_missing_or_duplicated" in reasons


def test_duplicate_host_id_requires_reconciliation(api, project):
    machine(api, project, "lab-a")
    machine(api, project, "lab-a")
    with pytest.raises(ValueError, match="duplicated"):
        resources.inventory(project, now=NOW)


def test_resource_reports_cannot_replace_canonical_records(api, project):
    before = (project / "init.md").read_bytes()
    result = resources.inventory(project, now=NOW)
    for relative in ["init.md", ".state/pending.json"]:
        with pytest.raises(ValueError, match="report directory"):
            resources.save_summary(project, relative, result)
    assert (project / "init.md").read_bytes() == before
    assert not (project / ".state/pending.json").exists()
    path = resources.save_summary(
        project.parent, ".state/resources/inventory.json", result
    )
    assert json.loads(path.read_text(encoding="utf-8"))["machines"] == []
