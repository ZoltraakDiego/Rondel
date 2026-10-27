"""保存 Rondel 项目共识、研究记录和可恢复的状态。

本模块只处理本地记录，不执行模型、远程命令或科研任务。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml

SCHEMA_VERSION = 1
ARCHIVE_NAMES = (".rondel", ".rondal")
PHASES = {
    "init": {
        "prepare",
        "investigate",
        "converge",
        "write",
        "submit",
        "archived",
    },
    "prepare": {"investigate", "archived"},
    "investigate": {"prepare", "converge", "archived"},
    "converge": {"investigate", "write", "archived"},
    "write": {"converge", "investigate", "submit", "archived"},
    "submit": {"write", "archived"},
    "archived": {"prepare", "investigate", "converge", "write", "submit"},
}
INIT_STATES = {"listening", "clarifying", "grounding", "reviewable", "ready"}
ACTIVITIES = {"working", "awaiting_user", "waiting_for_resource", "paused"}
STATES = {
    "discussion": {"open", "recorded", "closed"},
    "decision": {"recorded", "superseded"},
    "handoff": {"current", "superseded"},
    "question": {"observed", "clarified", "active", "resolved", "parked"},
    "direction": {"exploring", "provisional", "confirmed", "revisiting"},
    "hypothesis": {"proposed", "testable", "selected", "examined"},
    "claim": {
        "candidate",
        "evidence_linked",
        "reviewed",
        "adopted",
        "held",
        "withdrawn",
        "needs_review",
    },
    "experiment": {
        "draft",
        "reviewable",
        "approved",
        "preparing",
        "ready",
        "executing",
        "ready_for_analysis",
        "reviewable_result",
        "closed",
    },
    "run": {
        "planned",
        "preparing",
        "ready",
        "queued",
        "running",
        "completed",
        "failed",
        "cancelled",
    },
    "resource": {"recorded", "checked", "needs_recheck", "unavailable"},
}
EDGES = {
    "discussion": {
        "open": {"recorded", "closed"},
        "recorded": {"open", "closed"},
        "closed": {"open"},
    },
    "decision": {"recorded": {"superseded"}, "superseded": set()},
    "handoff": {"current": {"superseded"}, "superseded": set()},
    "resource": {
        "recorded": {"checked", "needs_recheck", "unavailable"},
        "checked": {"needs_recheck", "unavailable"},
        "needs_recheck": {"checked", "unavailable"},
        "unavailable": {"recorded", "needs_recheck", "checked"},
    },
    "question": {
        "observed": {"clarified", "parked"},
        "clarified": {"active", "parked"},
        "active": {"resolved", "parked"},
        "resolved": {"active"},
        "parked": {"clarified", "active"},
    },
    "direction": {
        "exploring": {"provisional"},
        "provisional": {"confirmed", "exploring"},
        "confirmed": {"revisiting"},
        "revisiting": {"provisional", "confirmed", "exploring"},
    },
    "hypothesis": {
        "proposed": {"testable"},
        "testable": {"selected", "proposed"},
        "selected": {"examined", "testable"},
        "examined": {"testable"},
    },
    "claim": {
        "candidate": {"evidence_linked", "held", "withdrawn"},
        "evidence_linked": {"reviewed", "held", "withdrawn"},
        "reviewed": {"adopted", "held", "withdrawn"},
        "adopted": {"needs_review", "withdrawn"},
        "held": {"candidate", "evidence_linked", "withdrawn"},
        "needs_review": {"evidence_linked", "held", "withdrawn"},
        "withdrawn": {"candidate"},
    },
    "experiment": {
        "draft": {"reviewable"},
        "reviewable": {"draft", "approved"},
        "approved": {"preparing"},
        "preparing": {"ready"},
        "ready": {"executing"},
        "executing": {"ready_for_analysis"},
        "ready_for_analysis": {"reviewable_result"},
        "reviewable_result": {"closed"},
        "closed": set(),
    },
    "run": {
        "planned": {"preparing", "cancelled"},
        "preparing": {"ready", "failed", "cancelled"},
        "ready": {"queued", "running", "cancelled"},
        "queued": {"running", "cancelled"},
        "running": {"completed", "failed", "cancelled"},
        "completed": set(),
        "failed": set(),
        "cancelled": set(),
    },
}
FOLDERS = {
    "discussion": "discussions",
    "decision": "decisions",
    "handoff": "handoffs",
    "question": "research/questions",
    "direction": "research/directions",
    "hypothesis": "research/hypotheses",
    "claim": "claims",
    "experiment": "experiments",
    "run": "runs",
    "resource": "setup/resources",
}
HUMAN_EDGES = {
    ("decision", "superseded"),
    ("question", "active"),
    ("question", "resolved"),
    ("direction", "confirmed"),
    ("direction", "revisiting"),
    ("hypothesis", "selected"),
    ("claim", "adopted"),
    ("claim", "withdrawn"),
    ("experiment", "approved"),
    ("experiment", "closed"),
}
SETTING_PURPOSES = {"dataset", "protocol", "baseline", "environment"}
MODE_REFERENCES = {
    "open": "main-cycle.md",
    "init": "init-dialogue.md",
    "status": "main-cycle.md",
    "review": "drift-check.md",
    "decide": "decisions.md",
    "configure": "configuration.md",
    "handoff": "handoff.md",
    "pre.framing": "pre-framing.md",
    "pre.library": "pre-papers.md",
    "pre.data": "pre-datasets.md",
    "pre.protocol": "pre-protocol.md",
    "pre.baseline": "pre-baselines.md",
    "pre.environment": "pre-environment.md",
    "mid.issue": "mid-issue.md",
    "mid.retrieve": "mid-retrieve.md",
    "mid.design": "mid-design.md",
    "mid.implement": "mid-implement.md",
    "mid.preflight": "mid-preflight.md",
    "mid.execute": "mid-execute.md",
    "mid.inspect": "mid-inspect.md",
    "mid.analyze": "mid-analyze.md",
    "post.converge": "post-converge.md",
    "post.mechanisms": "post-mechanisms.md",
    "post.claims": "post-claims.md",
    "post.visualize": "post-visualize.md",
    "post.write": "post-write.md",
    "post.submission": "post-submission.md",
    "post.closeout": "post-closeout.md",
}


class RecordError(ValueError):
    """记录、路径或状态不满足约定。"""


class UniqueLoader(yaml.SafeLoader):
    """拒绝重复字段，避免人工修改产生含混记录。"""


def _mapping(loader: UniqueLoader, node: yaml.MappingNode) -> dict:
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node)
        if key in result:
            raise RecordError(f"Duplicate YAML key: {key}")
        result[key] = loader.construct_object(value_node)
    return result


UniqueLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping
)
UniqueLoader.add_constructor(
    "tag:yaml.org,2002:timestamp",
    lambda loader, node: loader.construct_scalar(node),
)


def now() -> str:
    """返回带时区的 UTC 时间。"""
    return datetime.now(UTC).isoformat(timespec="microseconds")


def digest(path: Path) -> str:
    """计算文件实际字节的摘要。"""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def archive_root(root: Path) -> Path:
    """定位规范档案或只读兼容旧拼写；迁移由入口显式完成。"""
    root = root.resolve()
    if root.name.casefold() in ARCHIVE_NAMES:
        root = root.parent
    archive = root / ".rondel"
    if archive.resolve().parent != root:
        raise RecordError("Archive path leaves the selected workspace.")
    previous = root / ".rondal"
    if previous.resolve().parent != root:
        raise RecordError("Legacy archive path leaves the selected workspace.")
    if (archive / "init.md").exists() and (previous / "init.md").exists():
        raise RecordError(
            "Both .rondel and .rondal exist; select the actual archive before continuing."
        )
    if not archive.exists() and previous.exists():
        return previous
    legacy = root / "init.md"
    if not (archive / "init.md").exists() and legacy.is_file():
        try:
            meta, _ = read_note(legacy)
        except (OSError, ValueError, yaml.YAMLError):
            meta = {}
        if meta.get("type") == "project" and meta.get("schema_version") == 1:
            raise RecordError(
                "Legacy archive found: migrate its records into .rondel first."
            )
    return archive


def within(root: Path, relative: str) -> Path:
    """解析项目内路径，并拒绝越界和符号链接逃逸。"""
    root = root.resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or path == root:
        raise RecordError(f"Path leaves research root: {relative}")
    return path


def read_note(path: Path) -> tuple[dict[str, Any], str]:
    """读取 YAML 文件头，保留人工撰写的正文。"""
    text = path.read_text(encoding="utf-8-sig")
    parts = re.split(r"^---[ \t]*\r?$", text, maxsplit=2, flags=re.M)
    if len(parts) != 3 or parts[0].strip():
        raise RecordError(f"Missing YAML frontmatter: {path.name}")
    meta = yaml.load(parts[1], Loader=UniqueLoader)
    if not isinstance(meta, dict):
        raise RecordError(f"Frontmatter must be a mapping: {path.name}")
    return meta, parts[2].lstrip("\r\n")


def render(meta: dict, body: str) -> str:
    """序列化文件头与原有正文。"""
    head = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False)
    return f"---\n{head}---\n\n{body.rstrip()}\n"


def atomic_write(path: Path, text: str | bytes) -> None:
    """在目标目录内原子替换一个文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".rondel-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(
                text.encode("utf-8") if isinstance(text, str) else text
            )
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def locked(root: Path) -> Iterator[None]:
    """串行化项目写入；异常遗留的锁由用户核对后清理。"""
    path = within(root, ".state/write.lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as error:
        raise RecordError(
            "Project is locked; inspect the existing writer."
        ) from error
    os.close(fd)
    try:
        if within(root, ".state/pending.json").exists():
            raise RecordError("Interrupted write detected; use recover first.")
        yield
    finally:
        path.unlink(missing_ok=True)


def human_source(source: dict | None) -> None:
    """核对人的决定有可追溯的原话来源，不从笔记状态推断授权。"""
    if not isinstance(source, dict):
        raise RecordError("A human decision requires a source mapping.")
    if source.get("kind") not in {"user_message", "user_note"}:
        raise RecordError("Use a current user message or explicit user note.")
    if not all(
        isinstance(source.get(k), str) and source[k].strip()
        for k in ("reference", "quote")
    ):
        raise RecordError("Human source requires reference and quote.")


def check_meta(meta: dict) -> None:
    """验证状态字段和记录的基本结构。"""
    for key in ("id", "project_id", "type", "display_name", "status"):
        if not isinstance(meta.get(key), str) or not meta[key].strip():
            raise RecordError(f"Missing record field: {key}")
    if meta.get("schema_version") != SCHEMA_VERSION:
        raise RecordError("Unsupported schema_version.")
    if not isinstance(meta.get("revision"), int) or meta["revision"] < 1:
        raise RecordError("revision must be a positive integer.")
    if not isinstance(meta.get("refs", []), list):
        raise RecordError("refs must be a list.")
    kind = meta["type"]
    if kind == "project":
        for key in (
            "research_anchor",
            "bindings",
            "collaboration",
            "next_step",
        ):
            if not isinstance(meta.get(key), dict):
                raise RecordError(f"Project {key} must be a mapping.")
        anchor = meta["research_anchor"]
        if anchor.get("direction_status") not in {
            "exploring",
            "provisional",
            "confirmed",
            "revisiting",
        }:
            raise RecordError("Unknown research direction status.")
        if anchor["direction_status"] == "confirmed":
            human_source(anchor.get("confirmed_by"))
        if meta["collaboration"].get("guidance") not in {"guided", "concise"}:
            raise RecordError("Unknown guidance mode.")
        if meta["collaboration"].get("execution") not in {
            "discussion",
            "step",
            "approved_cycle",
            "approved_batch",
        }:
            raise RecordError("Unknown execution preference.")
        if meta.get("phase") not in PHASES:
            raise RecordError("Unknown project phase.")
        if meta.get("activity") not in ACTIVITIES:
            raise RecordError("Unknown collaboration activity.")
        if meta["status"] not in INIT_STATES:
            raise RecordError("Unknown Init status.")
        if meta["status"] == "ready":
            _ready(meta)
    elif kind not in STATES or meta["status"] not in STATES[kind]:
        raise RecordError(f"Unknown record type/status: {kind}.")
    if meta.get("purpose") == "phase_summary" and meta["status"] == "recorded":
        human_source(meta.get("reviewed_by"))
    if kind == "run" and meta.get("check_status", "unchecked") not in {
        "unchecked",
        "valid",
        "invalid",
    }:
        raise RecordError("Unknown artifact check status.")
    if "setting_refs" in meta:
        pins = meta["setting_refs"]
        if not isinstance(pins, list) or any(
            not isinstance(pin, dict)
            or not isinstance(pin.get("ref"), str)
            or not pin["ref"].startswith("record:")
            or type(pin.get("version")) is not int
            or pin["version"] < 1
            or not isinstance(pin.get("definition_sha256"), str)
            for pin in pins
        ):
            raise RecordError("Invalid versioned setting references.")
    if "setting_key" in meta:
        if kind != "resource" or meta.get("purpose") not in SETTING_PURPOSES:
            raise RecordError("Unsupported preparation setting purpose.")
        if (
            not isinstance(meta["setting_key"], str)
            or not meta["setting_key"].strip()
        ):
            raise RecordError("A preparation setting needs a stable key.")
        if not isinstance(meta.get("spec"), dict):
            raise RecordError("A preparation setting spec must be a mapping.")
        version = meta.get("setting_version")
        if type(version) is not int or version < 1:
            raise RecordError("A setting version must be a positive integer.")
        if meta.get("setting_state") not in {"draft", "frozen"}:
            raise RecordError("Unknown preparation setting state.")
        if meta["setting_state"] == "frozen":
            human_source(meta.get("frozen_by"))
            if not meta["spec"] or not meta.get("definition_sha256"):
                raise RecordError("Frozen settings need a definition and hash.")


def definition_digest(meta: dict, body: str) -> str:
    """仅摘要已冻结的设置定义；运行观测和核验状态可以单独更新。"""
    value = json.dumps(
        {"spec": meta["spec"], "body": body.rstrip()},
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(value.encode()).hexdigest()


def dependent_records(root: Path, identifier: str) -> list[dict]:
    """沿记录和设置引用找潜在影响；不自动宣判旧结果失效。"""
    remaining = _records(root)
    reached = {"record:" + identifier}
    reached.update(
        "project:" + r["path"] for r in remaining if r["id"] == identifier
    )
    affected = []
    while True:
        added = []
        for row in remaining:
            refs = set(row.get("refs", []))
            refs.update(p["ref"] for p in row.get("setting_refs", []))
            if row["id"] != identifier and refs.intersection(reached):
                added.append(row)
        if not added:
            break
        for row in added:
            reached.add("record:" + row["id"])
            reached.add("project:" + row["path"])
            affected.append(
                {
                    "ref": "record:" + row["id"],
                    "type": row["type"],
                    "name": row["display_name"],
                    "path": row["path"],
                    "review": "needs_review",
                }
            )
        added_ids = {r["id"] for r in added}
        remaining = [r for r in remaining if r["id"] not in added_ids]
    return affected


def _untracked_results(root: Path) -> list[str]:
    rows = _records(root)
    known = {
        alias
        for r in rows
        if "setting_key" in r
        for alias in ("record:" + r["id"], "project:" + r["path"])
    }
    while True:
        before = len(known)
        for row in rows:
            refs = set(row.get("refs", [])) | {
                p["ref"] for p in row.get("setting_refs", [])
            }
            if refs.intersection(known):
                known.update(("record:" + row["id"], "project:" + row["path"]))
        if len(known) == before:
            break
    return [
        "record:" + r["id"]
        for r in rows
        if r["type"] in {"experiment", "run", "claim"}
        and "record:" + r["id"] not in known
    ]


def _validate_setting_refs(root: Path, meta: dict) -> None:
    pins = meta.get("setting_refs", [])
    if not pins:
        return
    by_ref = {"record:" + r["id"]: r for r in _records(root)}
    for pin in pins:
        target = by_ref.get(pin["ref"], {})
        if (
            target.get("setting_state") != "frozen"
            or target.get("setting_version") != pin["version"]
            or target.get("definition_sha256") != pin["definition_sha256"]
        ):
            raise RecordError("Setting reference is missing, draft or changed.")


def _ready(meta: dict) -> None:
    anchor = meta.get("research_anchor", {})
    if not isinstance(anchor, dict) or not any(
        anchor.get(k) for k in ("problem", "open_question")
    ):
        raise RecordError("Ready Init needs a problem or an open question.")
    step = meta.get("next_step", {})
    if not isinstance(step, dict) or not step.get("label"):
        raise RecordError("Ready Init needs an explicit next step.")
    if meta.get("ready_for") not in {
        "exploration",
        "design",
        "execution",
        "writing",
    }:
        raise RecordError("Ready Init needs a readiness target.")
    if meta["ready_for"] == "execution":
        bindings = meta.get("bindings", {})
        if not all(
            bindings.get(k) for k in ("environment", "data", "protocol")
        ):
            raise RecordError(
                "Execution readiness needs environment/data/protocol."
            )
        if not meta.get("approved_plan_ref"):
            raise RecordError("Execution readiness needs a plan reference.")


def _event(root: Path, event: dict) -> None:
    journal = within(root, "history/events.jsonl")
    journal.parent.mkdir(parents=True, exist_ok=True)
    with journal.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(event, ensure_ascii=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def _commit(
    root: Path,
    path: Path,
    meta: dict,
    body: str,
    expected: str | None,
    actor: str,
    reason: str,
    source: dict | None,
) -> None:
    check_meta(meta)
    if (
        meta.get("setting_state") == "frozen"
        and definition_digest(meta, body) != meta["definition_sha256"]
    ):
        raise RecordError("Frozen setting definition changed; review the file.")
    _validate_setting_refs(root, meta)
    if actor not in {"human", "assistant", "check"}:
        raise RecordError("Unknown actor.")
    if not reason.strip():
        raise RecordError("Every update needs a reason.")
    if actor == "human":
        human_source(source)
    exists = path.exists()
    if exists and (not expected or digest(path) != expected):
        raise RecordError("Record changed; reread before updating.")
    if not exists and expected:
        raise RecordError("Expected record is missing.")
    previous = read_note(path)[0] if exists else None
    if previous:
        if (
            meta["id"] != previous["id"]
            or meta["project_id"] != previous["project_id"]
        ):
            raise RecordError("Record identity cannot change.")
        if meta["revision"] != previous["revision"] + 1:
            raise RecordError("Update must increment revision once.")
        folder = (
            "history/init"
            if meta["type"] == "project"
            else f"history/records/{meta['id']}"
        )
        archive = within(
            root, f"{folder}/{previous['revision']:04d}-{expected[:12]}.md"
        )
        if not archive.exists():
            atomic_write(archive, path.read_bytes())
    meta["updated_at"] = now()
    event = {
        "event_id": uuid4().hex,
        "timestamp": meta["updated_at"],
        "record_id": meta["id"],
        "path": path.relative_to(root).as_posix(),
        "revision": meta["revision"],
        "from_state": previous.get("status") if previous else None,
        "to_state": meta["status"],
        "actor": actor,
        "from_phase": previous.get("phase") if previous else None,
        "to_phase": meta.get("phase"),
        "reason": reason,
        "source": source,
    }
    if "setting_key" in meta:
        old_body = read_note(path)[1] if exists else ""
        changed = (
            previous is None
            or any(
                meta.get(k) != previous.get(k)
                for k in ("spec", "setting_state", "impact_review")
            )
            or old_body.rstrip() != body.rstrip()
        )
        if changed:
            parent = meta.get("supersedes", "record:" + meta["id"])
            affected = dependent_records(root, parent.removeprefix("record:"))
            base = previous or next(
                (r for r in _records(root) if "record:" + r["id"] == parent), {}
            )
            before_spec = base.get("spec", {})
            event["preparation_change"] = {
                "setting_key": meta["setting_key"],
                "purpose": meta["purpose"],
                "setting_ref": "record:" + meta["id"],
                "version": meta["setting_version"],
                "state": meta["setting_state"],
                "previous_ref": meta.get("supersedes"),
                "changed_spec_fields": sorted(
                    key
                    for key in set(before_spec) | set(meta["spec"])
                    if before_spec.get(key) != meta["spec"].get(key)
                ),
                "affected": [
                    r for r in affected if r["ref"] != "record:" + meta["id"]
                ],
                "impact_review": deepcopy(meta.get("impact_review", {})),
                "untracked_results": _untracked_results(root),
            }
    content = render(meta, body)
    pending = within(root, ".state/pending.json")
    intent = {
        "path": event["path"],
        "old_hash": expected,
        "new_hash": hashlib.sha256(content.encode()).hexdigest(),
        "content": content,
        "event": event,
    }
    atomic_write(pending, json.dumps(intent, ensure_ascii=False))
    atomic_write(path, content)
    _event(root, event)
    pending.unlink()


def initialize(
    root: Path, name: str, user_statement: str, source: dict
) -> Path:
    """在工作区的 .rondel 中创建最小档案，不代填科学方向或环境。"""
    human_source(source)
    root = archive_root(root)
    root.mkdir(parents=True, exist_ok=True)
    path = within(root, "init.md")
    with locked(root):
        if path.exists():
            raise RecordError("init.md already exists; open or configure it.")
        identifier = uuid4().hex
        meta = {
            "schema_version": 1,
            "id": f"project-{identifier}",
            "project_id": identifier,
            "type": "project",
            "display_name": name,
            "revision": 1,
            "status": "listening",
            "phase": "init",
            "activity": "working",
            "ready_for": None,
            "research_anchor": {
                "user_statement": user_statement,
                "search_summary": "",
                "problem": "",
                "open_question": "",
                "direction_status": "exploring",
                "confirmed_by": None,
            },
            "bindings": {},
            "next_step": {},
            "refs": [],
            "collaboration": {
                "guidance": "guided",
                "execution": "discussion",
            },
        }
        template = (
            Path(__file__).resolve().parents[1] / "assets/templates/init.md"
        )
        body = template.read_text(encoding="utf-8")
        _commit(
            root,
            path,
            meta,
            body,
            None,
            "human",
            "Start project intake",
            source,
        )
        _reindex(root)
    return path


def configure(
    root: Path,
    patch: dict,
    expected: str,
    actor: str,
    reason: str,
    source: dict | None = None,
    body: str | None = None,
) -> None:
    """保存项目约定与可选正文，保留旧版本和人的决定来源。"""
    root = archive_root(root)
    with locked(root):
        path = within(root, "init.md")
        meta, previous_body = read_note(path)
        protected = {
            "id",
            "project_id",
            "type",
            "schema_version",
            "revision",
            "updated_at",
        }
        if protected.intersection(patch):
            raise RecordError("Identity/version fields are managed by Rondel.")
        human_fields = {
            "research_anchor",
            "phase",
            "collaboration",
            "ready_for",
            "approved_plan_ref",
            "activity",
        }
        needs_human = (
            bool(human_fields.intersection(patch))
            or patch.get("status") == "ready"
        )
        if needs_human and actor != "human":
            raise RecordError(
                "Research commitments need a recorded human decision."
            )
        if "phase" in patch and patch["phase"] != meta["phase"]:
            if patch["phase"] not in PHASES[meta["phase"]]:
                raise RecordError("Unsupported project phase transition.")
            if (
                patch["phase"] != "archived"
                and meta["status"] != "ready"
                and patch.get("status") != "ready"
            ):
                raise RecordError(
                    "Confirm intake before changing project phase."
                )
        updated = deepcopy(meta)
        for key, value in patch.items():
            if isinstance(value, dict) and isinstance(updated.get(key), dict):
                updated[key].update(value)
            else:
                updated[key] = value
        profile_patch = patch.get("collaboration", {}).get("profile")
        if isinstance(profile_patch, dict):
            profile = deepcopy(meta["collaboration"].get("profile", {}))
            profile.update(profile_patch)
            updated["collaboration"]["profile"] = profile
        summary = patch.get("research_anchor", {}).get("search_summary")
        domain = (
            patch.get("collaboration", {})
            .get("profile", {})
            .get("research_domain")
        )
        if summary is not None or domain is not None:
            summary = summary if summary is not None else domain.get("summary")
            if not isinstance(summary, str) or not summary.strip():
                raise RecordError("Use a nonempty searchable research summary.")
            if domain is not None and domain.get("summary") != summary:
                raise RecordError(
                    "Profile and research anchor summaries must agree."
                )
            updated["research_anchor"]["search_summary"] = summary.strip()
            profile = updated["collaboration"].setdefault("profile", {})
            profile["research_domain"] = {
                "summary": summary.strip(),
                "source": source,
            }
        if (
            updated.get("research_anchor", {}).get("direction_status")
            == "confirmed"
        ):
            if actor == "human" and "research_anchor" in patch:
                updated["research_anchor"]["confirmed_by"] = source
            elif not updated["research_anchor"].get("confirmed_by"):
                raise RecordError("Confirmed direction needs its human source.")
        updated["revision"] += 1
        _commit(
            root,
            path,
            updated,
            previous_body if body is None else body,
            expected,
            actor,
            reason,
            source,
        )
        _reindex(root)


def create_record(
    root: Path,
    kind: str,
    name: str,
    body: str,
    refs: list[str] | None = None,
    fields: dict | None = None,
) -> Path:
    """保存讨论或候选对象，保持初始状态的事实边界。"""
    if kind not in STATES or kind == "decision":
        raise RecordError("Use decide for a human decision.")
    root = archive_root(root)
    with locked(root):
        project, _ = read_note(within(root, "init.md"))
        identifier = f"{kind}-{uuid4().hex}"
        initial = {
            "discussion": "open",
            "handoff": "current",
            "question": "observed",
            "direction": "exploring",
            "hypothesis": "proposed",
            "claim": "candidate",
            "experiment": "draft",
            "run": "planned",
            "resource": "recorded",
        }
        meta = {
            "schema_version": 1,
            "id": identifier,
            "project_id": project["project_id"],
            "type": kind,
            "display_name": name,
            "status": initial[kind],
            "revision": 1,
            "refs": refs or [],
        }
        fields = fields or {}
        if fields.get("purpose") == "phase_summary" and fields.get(
            "reviewed_by"
        ):
            raise RecordError("Review phase summaries through routing.py.")
        if set(fields).intersection(set(meta) | {"approval"}):
            raise RecordError("Extra fields cannot replace record metadata.")
        meta.update(fields)
        if "setting_key" in meta and any(
            r.get("setting_key") == meta["setting_key"]
            and r.get("setting_version") == meta["setting_version"]
            for r in _records(root)
        ):
            raise RecordError("Setting key/version already exists.")
        if meta.get("setting_state") == "frozen":
            raise RecordError(
                "Freeze a checked setting through preparation.py."
            )
        path = within(root, f"{FOLDERS[kind]}/{identifier}.md")
        _commit(
            root,
            path,
            meta,
            body,
            None,
            "assistant",
            "Record research step",
            None,
        )
        _reindex(root)
    return path


def decide(
    root: Path,
    name: str,
    body: str,
    source: dict,
    refs: list[str] | None = None,
) -> Path:
    """保存人的决定；决定本身不会执行其他操作。"""
    human_source(source)
    root = archive_root(root)
    with locked(root):
        project, _ = read_note(within(root, "init.md"))
        identifier = f"decision-{uuid4().hex}"
        meta = {
            "schema_version": 1,
            "id": identifier,
            "project_id": project["project_id"],
            "type": "decision",
            "display_name": name,
            "status": "recorded",
            "revision": 1,
            "refs": refs or [],
            "source": source,
        }
        path = within(root, f"decisions/{identifier}.md")
        _commit(
            root,
            path,
            meta,
            body,
            None,
            "human",
            "Record user decision",
            source,
        )
        _reindex(root)
    return path


def update_record(
    root: Path,
    relative: str,
    patch: dict,
    expected: str,
    actor: str,
    reason: str,
    source: dict | None = None,
    body: str | None = None,
) -> None:
    """补充记录内容；状态使用显式转换，批准方案保留原范围。"""
    root = archive_root(root)
    with locked(root):
        path = within(root, relative)
        meta, previous_body = read_note(path)
        if meta["type"] == "project":
            raise RecordError("Use configure for project commitments.")
        if path.parent != within(root, FOLDERS[meta["type"]]):
            raise RecordError("Historical and external records are read-only.")
        protected = {
            "id",
            "project_id",
            "type",
            "schema_version",
            "revision",
            "status",
            "updated_at",
            "approval",
            "source",
        }
        if protected.intersection(patch):
            raise RecordError("Use an explicit transition or a new decision.")
        if meta.get("purpose") == "phase_summary" and (
            meta.get("reviewed_by") or "reviewed_by" in patch
        ):
            raise RecordError(
                "Reviewed phase summary is sealed; create a new draft."
            )
        setting_fields = {
            "setting_key",
            "setting_version",
            "setting_state",
            "frozen_by",
            "definition_sha256",
            "supersedes",
        }
        if setting_fields.intersection(patch):
            raise RecordError(
                "Use preparation.py to initialize, freeze or revise settings."
            )
        if meta.get("setting_state") == "frozen" and (
            body is not None
            or set(patch).intersection({"spec", "purpose", "impact_review"})
        ):
            raise RecordError(
                "Frozen preparation setting; create a linked revision."
            )
        if "setting_refs" in patch and (
            meta.get("approval")
            or meta["type"] == "run"
            and meta["status"] not in {"planned", "preparing"}
        ):
            raise RecordError(
                "Executed or approved setting references are frozen."
            )
        if meta["type"] == "experiment" and meta.get("approval"):
            if body is not None:
                raise RecordError(
                    "Approved plan is frozen; create a linked plan."
                )
            if set(patch).intersection(
                {"hypothesis", "expected_result", "falsification", "scope"}
            ):
                raise RecordError(
                    "Approved plan is frozen; create a linked plan."
                )
        if meta["status"] in {"confirmed", "adopted", "recorded"} and meta[
            "type"
        ] in {"direction", "claim", "decision"}:
            if actor != "human":
                raise RecordError(
                    "Confirmed research text needs a human source."
                )
        meta.update(patch)
        if meta.get("check_status") == "valid" and not meta.get("refs"):
            raise RecordError("Artifact validation needs evidence references.")
        if (
            meta.get("check_status") == "valid"
            and meta["status"] != "completed"
        ):
            raise RecordError(
                "Validate completed run artifacts after execution."
            )
        meta["revision"] += 1
        _commit(
            root,
            path,
            meta,
            previous_body if body is None else body,
            expected,
            actor,
            reason,
            source,
        )
        _reindex(root)


def transition(
    root: Path,
    relative: str,
    state: str,
    expected: str,
    actor: str,
    reason: str,
    source: dict | None = None,
) -> None:
    """转换对象状态，保留旧记录并校验需要人的边。"""
    root = archive_root(root)
    with locked(root):
        path = within(root, relative)
        meta, body = read_note(path)
        kind = meta["type"]
        if meta.get("purpose") == "phase_summary" and (
            meta.get("reviewed_by") or state == "recorded"
        ):
            raise RecordError(
                "Review phase summaries through routing.py; reviewed summaries are sealed."
            )
        if kind not in FOLDERS or path.parent != within(root, FOLDERS[kind]):
            raise RecordError("Historical and external records are read-only.")
        if kind not in EDGES or state not in EDGES[kind].get(
            meta["status"], set()
        ):
            raise RecordError("Unsupported record transition.")
        if (kind, state) in HUMAN_EDGES and actor != "human":
            raise RecordError("This transition needs a human decision.")
        if state in {"evidence_linked", "reviewed", "adopted"} and not meta.get(
            "refs"
        ):
            raise RecordError(
                "Evidence references are required for this state."
            )
        if kind == "experiment" and state == "approved":
            for field in (
                "hypothesis",
                "expected_result",
                "falsification",
                "scope",
            ):
                if not meta.get(field):
                    raise RecordError(
                        f"Experiment needs {field} before approval."
                    )
            meta["approval"] = {
                "source": source,
                "scope": deepcopy(meta["scope"]),
            }
        meta["status"] = state
        meta["revision"] += 1
        _commit(root, path, meta, body, expected, actor, reason, source)
        _reindex(root)


def _records(root: Path) -> list[dict]:
    rows = []
    project, _ = read_note(within(root, "init.md"))
    for folder in FOLDERS.values():
        for path in within(root, folder).glob("*.md"):
            if not path.resolve().is_relative_to(root):
                raise RecordError("Record symlink leaves research root.")
            meta, body = read_note(path)
            check_meta(meta)
            if meta.get("setting_state") == "frozen" and (
                definition_digest(meta, body) != meta["definition_sha256"]
            ):
                raise RecordError(
                    "Frozen setting definition changed; review the file."
                )
            if meta["project_id"] != project["project_id"]:
                raise RecordError("Record belongs to a different project.")
            rows.append(
                {
                    **meta,
                    "path": path.relative_to(root).as_posix(),
                    "sha256": digest(path),
                }
            )
    return sorted(rows, key=lambda row: row["id"])


def _reindex(root: Path) -> None:
    rows = _records(root)
    cache = {"schema_version": 1, "records": rows}
    atomic_write(
        within(root, ".state/index.json"),
        json.dumps(cache, ensure_ascii=False, indent=2) + "\n",
    )
    visibility = {}
    for row in rows:
        if row.get("purpose") == "context_registry":
            visibility.update(row.get("entries", {}))
    active = [
        r
        for r in rows
        if r["status"]
        not in {"closed", "resolved", "withdrawn", "superseded", "cancelled"}
        and r.get("purpose") != "context_registry"
        and visibility.get("record:" + r["id"], {}).get("state", "active")
        == "active"
    ]
    lines = ["| 研究对象 | 当前状态 | 记录 |", "|---|---|---|"]
    for row in active:
        name = row["display_name"].replace("|", "／").replace("\n", " ")
        lines.append(f"| {name} | {row['status']} | [打开]({row['path']}) |")
    start, end = "<!-- rondel:index:start -->", "<!-- rondel:index:end -->"
    block = f"{start}\n" + "\n".join(lines) + f"\n{end}"
    path = within(root, "index.md")
    if path.exists():
        content = path.read_text(encoding="utf-8")
        if start in content and end in content:
            before, rest = content.split(start, 1)
            _, after = rest.split(end, 1)
            content = before + block + after
        else:
            content = content.rstrip() + "\n\n" + block + "\n"
    else:
        content = "# 当前研究索引\n\n" + block + "\n"
    atomic_write(path, content)


def reindex(root: Path) -> None:
    """显式重建索引，保留生成区之外的用户文字。"""
    root = archive_root(root)
    with locked(root):
        _reindex(root)


def context_paths(
    root: Path, mode: str, targets: list[str] | None = None
) -> dict:
    """只定位本次需要的上下文，不读取论文和实验原始产物。"""
    instructions = MODE_REFERENCES
    # 旧名称只用于已有调用兼容，公开目录统一使用 baseline。
    if mode == "pre.benchmarks":
        mode = "pre.baseline"
    if mode not in instructions:
        raise RecordError("Unknown research mode.")
    root = archive_root(root)
    project, _ = read_note(within(root, "init.md"))
    check_meta(project)
    files = ["init.md"]
    if within(root, "index.md").exists():
        files.append("index.md")
    cache_path = within(root, ".state/index.json")
    rows = (
        json.loads(cache_path.read_text(encoding="utf-8"))["records"]
        if cache_path.exists()
        else []
    )
    if mode.startswith("pre.") or mode in {
        "open",
        "review",
        "status",
        "handoff",
    }:
        for row in rows:
            if row.get("purpose") == "preparation":
                files.append(row["path"])
    selected = []
    for identifier in targets or []:
        matches = [r for r in rows if r["id"] == identifier]
        if len(matches) != 1:
            raise RecordError(f"Target not found in index: {identifier}")
        row = matches[0]
        path = within(root, row["path"])
        current, _ = read_note(path)
        check_meta(current)
        if (
            current["id"] != identifier
            or current["project_id"] != project["project_id"]
        ):
            raise RecordError(
                "Indexed record identity changed; review and reindex."
            )
        selected.append(
            {
                "id": identifier,
                "path": row["path"],
                "stale_index": digest(path) != row["sha256"],
                "status": current["status"],
            }
        )
        files.append(row["path"])
    if mode in {"open", "handoff"}:
        handoffs = [
            r
            for r in rows
            if r["type"] == "handoff" and r["status"] == "current"
        ]
        if handoffs:
            latest = max(handoffs, key=lambda r: r["updated_at"])
            files.append(latest["path"])
    return {
        "project_id": project["project_id"],
        "init_revision": project["revision"],
        "mode": mode,
        "files": list(dict.fromkeys(files)),
        "instruction": f"references/{instructions[mode]}",
        "targets": selected,
        "phase": project["phase"],
        "activity": project["activity"],
        "research_anchor": project["research_anchor"],
    }


def snapshot(root: Path, relative: str, sources: list[str]) -> Path:
    """保存相关来源的字节摘要，明确它是来源清单而非备份。"""
    root = archive_root(root)
    target = within(root, relative)
    rows = []
    for source in sources:
        path = Path(source).resolve()
        if not path.is_file():
            raise RecordError(f"Snapshot source missing: {source}")
        rows.append(
            {
                "path": str(path),
                "sha256": digest(path),
                "bytes": path.stat().st_size,
            }
        )
    with locked(root):
        if target.exists():
            raise RecordError("Snapshot already exists; create a new one.")
        project, _ = read_note(within(root, "init.md"))
        payload = {
            "schema_version": 1,
            "created_at": now(),
            "project_id": project["project_id"],
            "init_revision": project["revision"],
            "init_sha256": digest(within(root, "init.md")),
            "sources": rows,
        }
        atomic_write(
            target, yaml.safe_dump(payload, allow_unicode=True, sort_keys=False)
        )
    return target


def validate(root: Path) -> list[str]:
    """只读检查结构、项目身份、重复标识与内部引用。"""
    root = archive_root(root)
    problems = []
    try:
        project, _ = read_note(within(root, "init.md"))
        check_meta(project)
        rows = _records(root)
        ids = [project["id"]] + [r["id"] for r in rows]
        if len(ids) != len(set(ids)):
            problems.append("Duplicate record identifiers.")
        for row in rows:
            _validate_setting_refs(root, row)
            for ref in row.get("refs", []):
                if not isinstance(ref, str):
                    problems.append(f"Non-string reference in {row['id']}.")
                elif ref.startswith("record:") and ref[7:] not in ids:
                    problems.append(f"Missing record reference: {ref[7:]}.")
                elif (
                    ref.startswith("project:")
                    and not within(root, ref[8:]).exists()
                ):
                    problems.append(f"Missing project reference: {ref[8:]}.")
        if within(root, ".state/pending.json").exists():
            problems.append("Interrupted write requires recovery.")
        cache = within(root, ".state/index.json")
        if cache.exists():
            known = json.loads(cache.read_text(encoding="utf-8"))["records"]
            if {(r["path"], r["sha256"]) for r in rows} != {
                (r["path"], r["sha256"]) for r in known
            }:
                problems.append(
                    "Index is stale; explicitly reindex after review."
                )
    except (OSError, ValueError, yaml.YAMLError) as error:
        problems.append(str(error))
    return problems


def recover(root: Path) -> None:
    """显式完成中断的文件提交，不覆盖后续人工修改。"""
    root = archive_root(root)
    pending = within(root, ".state/pending.json")
    if not pending.exists():
        raise RecordError("No interrupted write to recover.")
    if within(root, ".state/write.lock").exists():
        raise RecordError("Inspect the existing writer before recovery.")
    # 持有与普通写入相同的排他锁，期间保留待恢复日志。
    lock = within(root, ".state/write.lock")
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    os.close(fd)
    try:
        intent = json.loads(pending.read_text(encoding="utf-8"))
        path = within(root, intent["path"])
        current = digest(path) if path.exists() else None
        if current not in {intent["old_hash"], intent["new_hash"]}:
            raise RecordError("Manual changes found; review the pending write.")
        if (
            hashlib.sha256(intent["content"].encode()).hexdigest()
            != intent["new_hash"]
        ):
            raise RecordError("Pending content hash is inconsistent.")
        atomic_write(path, intent["content"])
        journal = within(root, "history/events.jsonl")
        events = (
            [
                json.loads(line)
                for line in journal.read_text(encoding="utf-8").splitlines()
            ]
            if journal.exists()
            else []
        )
        if not any(
            e["event_id"] == intent["event"]["event_id"] for e in events
        ):
            _event(root, intent["event"])
        pending.unlink()
        _reindex(root)
    finally:
        lock.unlink(missing_ok=True)


def main() -> int:
    """提供英文终端摘要；结构化数据仅写入指定文件。"""
    parser = argparse.ArgumentParser(description="Rondel research records")
    parser.add_argument(
        "--root",
        required=True,
        type=Path,
        help="Workspace or its .rondel archive",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("init")
    p.add_argument("--name", required=True)
    p.add_argument("--statement", required=True)
    p.add_argument("--source", required=True, type=Path)
    for command in ("configure", "transition", "record", "decide", "update"):
        p = sub.add_parser(command)
        p.add_argument("--request", required=True, type=Path)
    p = sub.add_parser("context")
    p.add_argument("--mode", default="open")
    p.add_argument("--target", action="append", default=[])
    p.add_argument("--out", type=Path)
    p = sub.add_parser("snapshot")
    p.add_argument("--destination", required=True)
    p.add_argument("--source", action="append", required=True)
    for command in ("validate", "reindex", "recover"):
        sub.add_parser(command)
    args = parser.parse_args()
    try:
        if args.command == "init":
            source = yaml.safe_load(args.source.read_text(encoding="utf-8-sig"))
            print(
                "Created:",
                initialize(args.root, args.name, args.statement, source),
            )
        elif args.command in {
            "configure",
            "transition",
            "record",
            "decide",
            "update",
        }:
            request = yaml.safe_load(
                args.request.read_text(encoding="utf-8-sig")
            )
            if not isinstance(request, dict):
                raise RecordError("Request must be a mapping.")
            functions = {
                "configure": configure,
                "transition": transition,
                "record": create_record,
                "decide": decide,
                "update": update_record,
            }
            result = functions[args.command](args.root, **request)
            print("Saved:", result or archive_root(args.root) / "init.md")
        elif args.command == "context":
            plan = context_paths(args.root, args.mode, args.target)
            if args.out:
                # 输出文件也限定在用户指定的研究目录中。
                output = within(archive_root(args.root), str(args.out))
                atomic_write(
                    output, json.dumps(plan, ensure_ascii=False, indent=2)
                )
                print("Context manifest:", output)
            print("Read instruction:", plan["instruction"])
            for relative in plan["files"]:
                print("Read project file:", archive_root(args.root) / relative)
            if any(r["stale_index"] for r in plan["targets"]):
                print(
                    "Index changed: reread selected records before interpretation."
                )
        elif args.command == "snapshot":
            print("Saved:", snapshot(args.root, args.destination, args.source))
        elif args.command == "validate":
            problems = validate(args.root)
            for problem in problems:
                print("Issue:", problem)
            if problems:
                return 1
            print("Project records are valid.")
        else:
            {"reindex": reindex, "recover": recover}[args.command](args.root)
            print("Completed:", args.command)
    except (OSError, ValueError, yaml.YAMLError, TypeError) as error:
        print("Error:", error)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
