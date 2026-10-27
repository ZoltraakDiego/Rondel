"""验证来源绑定和中断恢复保持可追溯。"""

import json

import pytest
import yaml


def test_source_manifest_is_immutable_and_tracks_bytes(api, project, tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("原始配置", encoding="utf-8")
    path = api.snapshot(
        project, "experiments/example/snapshot.yaml", [str(source)]
    )
    before = path.read_bytes()
    meta = yaml.safe_load(before)
    assert meta["sources"][0]["sha256"] == api.digest(source)
    assert meta["init_revision"] == 1
    source.write_text("后续修改", encoding="utf-8")
    assert path.read_bytes() == before
    with pytest.raises(api.RecordError, match="already exists"):
        api.snapshot(
            project, "experiments/example/snapshot.yaml", [str(source)]
        )


def test_snapshot_destination_cannot_escape(api, project, tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("source", encoding="utf-8")
    with pytest.raises(api.RecordError, match="leaves"):
        api.snapshot(project, "../outside.yaml", [str(source)])


def test_interrupted_event_append_is_recoverable(
    api, project, source, monkeypatch
):
    original = api._event

    def fail(*args):
        raise OSError("simulated interruption")

    monkeypatch.setattr(api, "_event", fail)
    with pytest.raises(OSError, match="interruption"):
        api.configure(
            project,
            {"display_name": "用户修正的项目名"},
            api.digest(project / "init.md"),
            "human",
            "修正名字",
            source,
        )
    assert (project / ".state/pending.json").exists()
    assert any("Interrupted" in x for x in api.validate(project))
    monkeypatch.setattr(api, "_event", original)
    api.recover(project)
    assert not (project / ".state/pending.json").exists()
    assert api.validate(project) == []
    events = [
        json.loads(line)
        for line in (project / "history/events.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert len({e["event_id"] for e in events}) == len(events)


def test_recovery_preserves_later_manual_changes(
    api, project, source, monkeypatch
):
    original = api._event
    monkeypatch.setattr(
        api, "_event", lambda *args: (_ for _ in ()).throw(OSError("stop"))
    )
    with pytest.raises(OSError):
        api.configure(
            project,
            {"display_name": "修改"},
            api.digest(project / "init.md"),
            "human",
            "修正",
            source,
        )
    path = project / "init.md"
    with path.open("a", encoding="utf-8") as stream:
        stream.write("\n后续人工修改。\n")
    before = path.read_bytes()
    monkeypatch.setattr(api, "_event", original)
    with pytest.raises(api.RecordError, match="Manual changes"):
        api.recover(project)
    assert path.read_bytes() == before
