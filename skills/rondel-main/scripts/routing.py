"""发现档案、按已识别模式提供小型上下文包，并维护阶段摘要与归档导航。"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

import yaml

spec = importlib.util.spec_from_file_location(
    "rondel_routing_records", Path(__file__).with_name("records.py")
)
records = importlib.util.module_from_spec(spec)
spec.loader.exec_module(records)

ROLE_PURPOSES = {
    "pre.framing": {"preparation", "field_pain", "core_question"},
    "pre.library": {"literature_map", "core_paper"},
    "pre.data": {"dataset"},
    "pre.protocol": {"protocol"},
    "pre.baseline": {"baseline", "baseline_selection"},
    "pre.environment": {"machine", "environment"},
    "mid.issue": {"research_issue", "core_question"},
    "mid.retrieve": {"method_source"},
    "mid.design": set(),
    "mid.implement": {"implementation_note"},
    "mid.preflight": {"preflight"},
    "mid.execute": {"preflight"},
    "mid.inspect": {"run_inspection"},
    "mid.analyze": {"experiment_analysis"},
    "post.converge": {
        "convergence",
        "experiment_analysis",
        "paper_material_selection",
    },
    "post.mechanisms": {"mechanism"},
    "post.claims": {"claim_evidence"},
    "post.visualize": {"figure_plan"},
    "post.write": {"manuscript", "claim_evidence", "paper_material_selection"},
    "post.submission": {"submission_requirements", "submission_package"},
    "post.closeout": {
        "project_closeout",
        "reproduction_package",
        "materials_package",
    },
}
ROLE_TYPES = {
    "mid.issue": {"question", "hypothesis"},
    "mid.design": {"hypothesis", "experiment"},
    "mid.implement": {"experiment"},
    "mid.preflight": {"experiment", "run"},
    "mid.execute": {"experiment", "run"},
    "mid.inspect": {"run"},
    "mid.analyze": {"run", "hypothesis"},
    "post.converge": {"claim", "hypothesis", "direction"},
    "post.mechanisms": {"claim", "hypothesis"},
    "post.claims": {"claim"},
    "post.visualize": {"claim"},
    "post.write": {"claim"},
}
TASK_REF_KEYS = (
    "task_ref",
    "question_ref",
    "hypothesis_ref",
    "experiment_ref",
    "claim_ref",
    "manuscript_ref",
)
BRIEF_FIELDS = {
    "question",
    "findings",
    "decisions",
    "open_questions",
    "carryovers",
    "next_step",
}
INACTIVE = {
    "closed",
    "resolved",
    "parked",
    "withdrawn",
    "superseded",
    "cancelled",
}


def normalize_mode(mode: str) -> str:
    mode = mode.removeprefix("main.")
    if mode == "pre.benchmarks":
        mode = "pre.baseline"
    if mode != "general" and mode not in records.MODE_REFERENCES:
        raise ValueError("Choose an available research mode, or general.")
    return mode


def router_policy() -> dict:
    path = (
        Path(__file__).resolve().parents[1]
        / "references/shared/router-models.yaml"
    )
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _request_key(value: dict) -> str:
    data = {k: v for k, v in value.items() if k != "request_key"}
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def intent_seed(
    request: str,
    runtime: str = "codex",
    context_hint: dict | None = None,
    allowed_targets: list[str] | None = None,
    read_only_constraint: bool = False,
) -> dict:
    """生成发给轻量子 Agent 的输入；不携带对话、正文或任意画像。"""
    policy = router_policy()
    limits = policy["limits"]
    if (
        runtime not in {"codex", "claude"}
        or type(read_only_constraint) is not bool
    ):
        raise ValueError(
            "Choose a supported runtime and a boolean scope constraint."
        )
    if (
        not isinstance(request, str)
        or not request.strip()
        or len(request) > limits["max_request_chars"]
    ):
        raise ValueError(
            "Use a concise current action request; link long materials instead of copying them."
        )
    hints = {} if context_hint is None else context_hint
    if (
        not isinstance(hints, dict)
        or set(hints) - {"project_id", "phase", "current_mode", "task_label"}
        or any(not isinstance(v, str) for v in hints.values())
        or len(json.dumps(hints, ensure_ascii=False)) > limits["max_hint_chars"]
    ):
        raise ValueError(
            "Context hints allow only short project_id, phase, current_mode and task_label fields."
        )
    targets = [] if allowed_targets is None else allowed_targets
    if (
        not isinstance(targets, list)
        or len(targets) > 8
        or any(
            not isinstance(ref, str)
            or not ref.startswith("record:")
            or len(ref) > 150
            for ref in targets
        )
    ):
        raise ValueError("Provide at most eight explicit record references.")
    modes = ["general"] + [
        m if "." in m else "main." + m for m in records.MODE_REFERENCES
    ]
    value = {
        "schema_version": 1,
        "request": request,
        "context_hint": deepcopy(hints),
        "allowed_modes": modes,
        "allowed_targets": list(dict.fromkeys(targets)),
        "read_only_constraint": read_only_constraint,
        "runtime": runtime,
        "preferred_profile": policy[runtime],
        "max_calls": limits["max_calls_per_intent"],
        "max_result_chars": limits["max_result_chars"],
    }
    value["request_key"] = _request_key(value)
    if len(json.dumps(value, ensure_ascii=False)) > limits["max_seed_chars"]:
        raise ValueError(
            "Routing input exceeds the seed budget; reduce hints without dropping constraints."
        )
    return value


def validate_intent_result(
    result: dict | str, seed: dict, current_request_key: str | None = None
) -> dict:
    """校验子 Agent 结果；范围与新 session 的选择仍由主 Agent 决定。"""
    if seed.get("request_key") != _request_key(seed) or (
        current_request_key is not None
        and current_request_key != seed["request_key"]
    ):
        raise ValueError(
            "Routing result belongs to a changed or stale request."
        )
    raw = (
        result
        if isinstance(result, str)
        else json.dumps(result, ensure_ascii=False)
    )
    if len(raw) > router_policy()["limits"]["max_result_chars"]:
        raise ValueError("Routing result exceeds its output budget.")
    result = json.loads(raw)
    fields = {
        "mode",
        "intent",
        "read_only",
        "targets",
        "needs_main_review",
        "reason",
    }
    if (
        not isinstance(result, dict)
        or set(result) != fields
        or result["mode"] not in seed["allowed_modes"]
    ):
        raise ValueError(
            "Return only the six routing fields and an available mode."
        )
    if (
        type(result["read_only"]) is not bool
        or type(result["needs_main_review"]) is not bool
    ):
        raise ValueError("Routing scope and review flags must be booleans.")
    for field, limit in (("intent", 240), ("reason", 160)):
        if (
            not isinstance(result[field], str)
            or not result[field].strip()
            or len(result[field]) > limit
        ):
            raise ValueError("Use a concise intent and routing reason.")
    targets = result["targets"]
    if (
        not isinstance(targets, list)
        or any(not isinstance(ref, str) for ref in targets)
        or (
            len(targets) > 8
            or len(set(targets)) != len(targets)
            or not set(targets).issubset(seed["allowed_targets"])
        )
    ):
        raise ValueError(
            "A router cannot invent targets or expand its target set."
        )
    if seed["read_only_constraint"] and not result["read_only"]:
        raise ValueError(
            "Routing result conflicts with the current read-only constraint."
        )
    return {
        "request_key": seed["request_key"],
        "decision": result,
        "requires_main_review": result["needs_main_review"]
        or not result["read_only"],
        "execution_authorized": False,
        "session_creation_authorized": False,
    }


def discover(start: Path, boundary: Path | None = None) -> dict:
    """仅查指定边界内的当前目录和祖先，不递归搜索磁盘。"""
    start = start.resolve()
    if start.is_file():
        start = start.parent
    if start.name.casefold() == ".rondal":
        boundary = start = start.parent
    if boundary is None:
        boundary = next(
            (p for p in [start, *start.parents] if (p / ".git").exists()), start
        )
    boundary = boundary.resolve()
    if not start.is_relative_to(boundary):
        raise ValueError(
            "Discovery start must stay within the selected boundary."
        )
    candidates = []
    cursor = start
    while True:
        root = records.archive_root(cursor)
        if (root / "init.md").is_file():
            meta, _ = records.read_note(root / "init.md")
            records.check_meta(meta)
            candidates.append(
                {
                    "workspace": str(cursor),
                    "archive": str(root),
                    "project_id": meta["project_id"],
                }
            )
        if cursor == boundary:
            break
        cursor = cursor.parent
    return {
        "boundary": str(boundary),
        "candidates": candidates,
        "resolution": "found"
        if len(candidates) == 1
        else "ambiguous"
        if candidates
        else "not_found",
    }


def _index(root: Path) -> list[dict]:
    path = records.within(root, ".state/index.json")
    return (
        json.loads(path.read_text(encoding="utf-8"))["records"]
        if path.exists()
        else []
    )


def _live(root: Path, row: dict) -> dict:
    path = records.within(root, row["path"])
    meta, _ = records.read_note(path)
    records.check_meta(meta)
    project, _ = records.read_note(root / "init.md")
    if meta["id"] != row["id"] or meta["project_id"] != project["project_id"]:
        raise ValueError(
            "Indexed record identity changed; review before loading."
        )
    return {
        **meta,
        "path": row["path"],
        "sha256": records.digest(path),
        "stale_index": records.digest(path) != row["sha256"],
    }


def _registry(root: Path, rows: list[dict]) -> dict:
    matches = [r for r in rows if r.get("purpose") == "context_registry"]
    if len(matches) > 1:
        raise ValueError("Reconcile duplicate context registries.")
    return _live(root, matches[0]).get("entries", {}) if matches else {}


def _card(row: dict) -> dict:
    return {
        key: row[key]
        for key in (
            "id",
            "display_name",
            "type",
            "status",
            "revision",
            "path",
            "sha256",
        )
    }


def lookup(
    workspace: Path, query: str, include_archive: bool = False, limit: int = 8
) -> list[dict]:
    if not query.strip() or not 1 <= limit <= 20:
        raise ValueError(
            "Use a nonempty query and a lookup limit from 1 to 20."
        )
    root = records.archive_root(workspace)
    rows = _index(root)
    visibility = _registry(root, rows)
    hits = []
    for row in rows:
        state = visibility.get("record:" + row["id"], {}).get("state", "active")
        if row.get("purpose") == "context_registry" or (
            state != "active" and not include_archive
        ):
            continue
        haystack = " ".join(
            str(row.get(k, ""))
            for k in ("id", "display_name", "type", "purpose")
        ).casefold()
        if all(term in haystack for term in query.casefold().split()):
            current = _live(root, row)
            hits.append(
                {
                    **_card(current),
                    "visibility": state,
                    "stale_index": current["stale_index"],
                }
            )
        if len(hits) == limit:
            break
    return hits


def _summary_stale(root: Path, summary: dict, rows: list[dict]) -> list[str]:
    by_ref = {"record:" + r["id"]: r for r in rows}
    stale = []
    for source in summary.get("source_snapshots", []):
        row = by_ref.get(source["ref"])
        path = records.within(root, row["path"]) if row else None
        if (
            path is None
            or not path.is_file()
            or records.digest(path) != source["sha256"]
        ):
            stale.append(source["ref"])
    for pin in summary.get("setting_refs", []):
        original = by_ref.get(pin["ref"], {})
        if any(
            r.get("setting_key") == original.get("setting_key")
            and r.get("setting_state") == "frozen"
            and r.get("setting_version", 0) > pin["version"]
            for r in rows
        ):
            stale.append(pin["ref"])
    return stale


def _check_brief(brief: dict, refs: list[str], by_ref: dict) -> None:
    if (
        not isinstance(brief, dict)
        or set(brief) - BRIEF_FIELDS
        or not isinstance(brief.get("question"), str)
        or not brief["question"].strip()
        or not isinstance(brief.get("next_step"), dict)
        or not brief["next_step"].get("label")
    ):
        raise ValueError(
            "A phase brief needs a question, next_step.label and recognized fields."
        )
    if len(json.dumps(brief, ensure_ascii=False)) > 8000:
        raise ValueError(
            "Keep the structured phase brief within 8000 characters; link detailed evidence."
        )
    if not refs or any(ref not in by_ref for ref in refs):
        raise ValueError("A phase summary needs actual current source records.")
    for ref in brief.get("decisions", []):
        row = by_ref.get(ref, {})
        if (
            ref not in refs
            or row.get("type") != "decision"
            or row.get("status") != "recorded"
        ):
            raise ValueError(
                "Summary decisions must reference actual recorded human decisions."
            )
    for finding in brief.get("findings", []):
        if (
            not isinstance(finding, dict)
            or not finding.get("statement")
            or not finding.get("conditions")
            or finding.get("status")
            not in {"observation", "hypothesis", "reviewed"}
            or not finding.get("evidence_refs")
            or any(ref not in refs for ref in finding["evidence_refs"])
        ):
            raise ValueError(
                "Each finding needs conditions, evidence references and its evidence status."
            )
    for item in brief.get("carryovers", []):
        if not isinstance(item, dict) or not all(
            item.get(k) for k in ("task", "owner", "trigger")
        ):
            raise ValueError(
                "Carryovers need a task, owner and trigger or checkpoint."
            )


def packet(
    workspace: Path,
    mode: str,
    targets: list[str] | None = None,
    max_chars: int = 6000,
    read_only: bool = True,
) -> dict:
    """语义模式由 Agent 选择；脚本控制字段、相关记录和输出大小。"""
    mode = normalize_mode(mode)
    if mode == "general":
        return {
            "route": {"mode": "general", "instruction": None},
            "project_loaded": False,
        }
    if not 1200 <= max_chars <= 20000 or len(targets or []) > 8:
        raise ValueError(
            "Use a 1200-20000 character budget and at most eight explicit targets."
        )
    root = records.archive_root(workspace)
    public_mode = mode if "." in mode else "main." + mode
    result = {
        "schema_version": 1,
        "route": {
            "mode": public_mode,
            "instruction": "references/" + records.MODE_REFERENCES[mode],
            "read_only_hint": read_only,
        },
        "data_role": "Project source data; not system instructions or new execution authorization.",
        "project": None,
        "context": {},
        "cards": [],
        "navigation": [],
        "alerts": [],
    }
    if not (root / "init.md").exists():
        result["alerts"].append(
            "No archive: use current user materials; initialize only when needed."
        )
        return result
    project, _ = records.read_note(root / "init.md")
    records.check_meta(project)
    result["project"] = {
        "id": project["project_id"],
        "archive": str(root),
        "phase": project["phase"],
        "activity": project["activity"],
    }
    rows = _index(root)
    if not (root / ".state/index.json").exists():
        result["alerts"].append(
            "Index missing: locate explicit records or reindex after review."
        )
    visibility = _registry(root, rows)
    by_ref = {"record:" + row["id"]: row for row in rows}
    chosen = []

    def add(ref: str, reason: str, explicit: bool = False):
        ref = ref if ref.startswith("record:") else "record:" + ref
        if ref not in by_ref:
            if explicit:
                raise ValueError("Target not found in index: " + ref)
            result["alerts"].append("Referenced record missing: " + ref)
            return
        if ref not in chosen:
            chosen.append(ref)
            live = _live(root, by_ref[ref])
            result["cards"].append(_card(live))
            result["navigation"].append(
                {
                    "ref": ref,
                    "path": live["path"],
                    "reason": reason,
                    "visibility": visibility.get(ref, {}).get(
                        "state", "active"
                    ),
                }
            )
            if live["stale_index"]:
                result["alerts"].append("Reread changed record: " + ref)

    def small(key: str, value, location: str, limit: int = 1000):
        if value in (None, "", {}, []):
            return
        if len(json.dumps(value, ensure_ascii=False)) <= limit:
            result["context"][key] = deepcopy(value)
        else:
            result["navigation"].append(
                {
                    "path": location,
                    "reason": key + " exceeds inline budget; read when needed",
                }
            )

    anchor = project["research_anchor"]
    small(
        "search_summary",
        anchor.get("search_summary"),
        "init.md#research_anchor.search_summary",
    )
    small(
        "question",
        anchor.get("current_question")
        or anchor.get("problem")
        or anchor.get("open_question"),
        "init.md#research_anchor",
    )
    step = project.get("next_step", {})
    small(
        "current_task",
        {
            k: step[k]
            for k in (
                "label",
                "plan_ref",
                "decision_ref",
                "scope_ref",
                *TASK_REF_KEYS,
            )
            if k in step
        },
        "init.md#next_step",
    )
    profile = project["collaboration"].get("profile", {})
    pref_keys = (
        (
            "addressing",
            "background",
            "experience",
            "support_needs",
            "expression",
            "question_rhythm",
        )
        if mode == "init"
        else ("expression", "question_rhythm")
    )
    small(
        "preferences",
        {
            k: profile[k].get("summary")
            for k in pref_keys
            if isinstance(profile.get(k), dict)
        },
        "init.md#collaboration.profile",
    )
    if mode in {"open", "status", "review", "handoff"}:
        small(
            "user_current_state",
            project["collaboration"].get("current_state", {}).get("summary"),
            "init.md#collaboration.current_state",
        )
    for ref in targets or []:
        add(ref, "explicit target", True)
    task_anchors = set()
    if mode.startswith(("mid.", "post.")):
        for key in () if targets else TASK_REF_KEYS:
            if step.get(key):
                add(step[key], "current " + key)
                task_anchors.add(
                    step[key]
                    if step[key].startswith("record:")
                    else "record:" + step[key]
                )
        task_anchors.update(
            ref if ref.startswith("record:") else "record:" + ref
            for ref in targets or []
        )
    if mode in {"open", "status", "review", "handoff"}:
        for key in ("plan_ref", "review_ref"):
            if step.get(key):
                add(step[key], "current " + key)
    active = [
        r
        for r in rows
        if visibility.get("record:" + r["id"], {}).get("state", "active")
        == "active"
        and r["status"] not in INACTIVE
        and r.get("purpose") != "context_registry"
    ]
    summaries = [
        r
        for r in active
        if r.get("purpose") == "phase_summary"
        and r.get("summary_for") == project["phase"]
        and r["status"] == "recorded"
        and r.get("reviewed_by")
    ]
    if summaries:
        summary = _live(root, max(summaries, key=lambda r: r["updated_at"]))
        records.human_source(summary["reviewed_by"])
        add("record:" + summary["id"], "reviewed summary for current phase")
        stale = _summary_stale(root, summary, rows)
        if stale:
            result["alerts"].append(
                "Phase summary sources changed; verify before conclusions: "
                + ", ".join(stale)
            )
        else:
            brief = summary.get("brief", {})
            fields = (
                BRIEF_FIELDS
                if mode in {"open", "status", "review", "handoff"}
                else {"question", "next_step"}
            )
            small(
                "phase_brief",
                {k: brief[k] for k in sorted(fields) if k in brief},
                summary["path"],
                2200,
            )
    if (
        mode.startswith("pre.")
        or mode == "mid.issue"
        or project["phase"] == "prepare"
        and mode in {"open", "status", "review", "handoff"}
    ):
        boards = [r for r in active if r.get("purpose") == "preparation"]
        if boards:
            board = _live(root, max(boards, key=lambda r: r["updated_at"]))
            small(
                "research_focus",
                board.get("focus", {}),
                board["path"] + "#focus",
            )
            primary = board.get("focus", {}).get("primary_question_ref")
            if primary and (mode != "mid.issue" or not task_anchors):
                add(primary, "current primary question")
                if mode == "mid.issue":
                    task_anchors.add(primary)
    heads = {}
    for row in active:
        if row.get("setting_state") == "frozen" and row.get(
            "setting_version", 0
        ) > heads.get(row.get("setting_key"), {}).get("setting_version", 0):
            heads[row["setting_key"]] = row
    purposes = ROLE_PURPOSES.get(
        mode,
        {"preparation"}
        if mode in {"open", "status", "review", "handoff"}
        and project["phase"] == "prepare"
        else set(),
    )
    active = [
        r
        for r in active
        if not r.get("setting_key")
        or r["id"] == heads.get(r["setting_key"], r)["id"]
    ]
    related = set(task_anchors)
    if task_anchors:
        aliases = {"project:" + r["path"]: "record:" + r["id"] for r in rows}

        def dependencies(row):
            refs = row.get("refs", []) + [
                row[k]
                for k in ("experiment_ref", "hypothesis_ref")
                if row.get(k)
            ]
            return {aliases.get(ref, ref) for ref in refs}

        for anchor_ref in task_anchors:
            if anchor_ref in by_ref:
                related.update(dependencies(by_ref[anchor_ref]))
        descendants = set(task_anchors)
        structural = {
            "phase_summary",
            "context_registry",
            "preparation",
            "research_plan",
            "phase_review",
            "main_review",
        }
        for _ in range(2):
            children = {
                "record:" + row["id"]
                for row in active
                if row["type"] != "resource"
                and row.get("purpose") not in structural
                and dependencies(row).intersection(descendants)
            }
            descendants.update(children)
        related.update(descendants)
    types = ROLE_TYPES.get(mode, set())
    if mode.startswith(("mid.", "post.")) and not task_anchors:
        result["alerts"].append(
            "Select a task/experiment/claim/manuscript reference to expand scoped evidence; unrelated records stay deferred."
        )
        purposes = set()
    candidates = sorted(
        (
            r
            for r in active
            if (
                r.get("purpose") in purposes
                or bool(task_anchors)
                and r["type"] in types
            )
            and (not task_anchors or "record:" + r["id"] in related)
        ),
        key=lambda r: r["updated_at"],
        reverse=True,
    )
    result["role_records_deferred"] = max(0, len(candidates) - 4)
    for row in candidates[:4]:
        add(
            "record:" + row["id"],
            "selected mode role: " + row.get("purpose", row["type"]),
        )
    if mode in {"open", "handoff"} and not summaries:
        handoffs = [
            r
            for r in active
            if r["type"] == "handoff" and r["status"] == "current"
        ]
        if handoffs:
            add(
                "record:" + max(handoffs, key=lambda r: r["updated_at"])["id"],
                "latest handoff; read relevant sections",
            )
    result["deferred_counts"] = {
        state: sum(e.get("state") == state for e in visibility.values())
        for state in ("archive", "temporary")
    }
    result["lookup"] = (
        "routing.py lookup --query <terms>; add --include-archive for historical directions"
    )
    if len(json.dumps(result, ensure_ascii=False)) > max_chars:
        for key in ("phase_brief", "preferences", "user_current_state"):
            if key in result["context"]:
                del result["context"][key]
                result["alerts"].append(
                    key
                    + " omitted as a whole to respect budget; use source navigation"
                )
            if len(json.dumps(result, ensure_ascii=False)) <= max_chars:
                break
    while (
        len(json.dumps(result, ensure_ascii=False)) > max_chars
        and result["cards"]
    ):
        card = result["cards"].pop()
        result["alerts"].append(
            "Metadata deferred, source path retained: record:" + card["id"]
        )
    if len(json.dumps(result, ensure_ascii=False)) > max_chars:
        raise ValueError(
            "Required navigation exceeds budget; split this task or increase max_chars."
        )
    return result


def set_visibility(
    workspace: Path,
    refs: list[str],
    state: str,
    reason: str,
    source: dict | None = None,
) -> Path:
    if (
        state not in {"active", "archive", "temporary"}
        or not refs
        or not reason.strip()
    ):
        raise ValueError(
            "Choose records, a visibility state and an archival reason."
        )
    if source is not None:
        records.human_source(source)
    root = records.archive_root(workspace)
    with records.locked(root):
        rows = records._records(root)
        by_ref = {"record:" + r["id"]: r for r in rows}
        if any(
            ref not in by_ref
            or by_ref[ref].get("purpose") == "context_registry"
            for ref in refs
        ):
            raise ValueError(
                "Visibility targets must be current project records."
            )
        registries = [r for r in rows if r.get("purpose") == "context_registry"]
        if len(registries) > 1:
            raise ValueError("Reconcile duplicate context registries.")
        if registries:
            path = records.within(root, registries[0]["path"])
            meta, body = records.read_note(path)
            expected = records.digest(path)
            meta["revision"] += 1
        else:
            project, _ = records.read_note(root / "init.md")
            meta = {
                "schema_version": 1,
                "id": "discussion-" + uuid4().hex,
                "project_id": project["project_id"],
                "type": "discussion",
                "display_name": "上下文归档导航",
                "status": "open",
                "revision": 1,
                "purpose": "context_registry",
                "refs": [],
                "entries": {},
            }
            path = root / "discussions" / (meta["id"] + ".md")
            expected = None
            body = "# 上下文归档导航\n\n只管理默认加载与历史定位，原记录、设置定义和科学状态保持各自来源。\n"
        for ref in refs:
            meta["entries"][ref] = {
                "state": state,
                "reason": reason,
                "recorded_at": records.now(),
            }
        records._commit(
            root,
            path,
            meta,
            body,
            expected,
            "human" if source else "assistant",
            reason,
            source,
        )
        records._reindex(root)
    return path


def create_summary(
    workspace: Path,
    name: str,
    summary_of: str,
    summary_for: str,
    brief: dict,
    source_refs: list[str],
    body: str,
    setting_refs: list[dict] | None = None,
) -> Path:
    if summary_of not in records.PHASES or summary_for not in records.PHASES:
        raise ValueError("Use known source and destination phases.")
    root = records.archive_root(workspace)
    by_ref = {"record:" + r["id"]: r for r in records._records(root)}
    refs = list(
        dict.fromkeys(
            source_refs
            + brief.get("decisions", [])
            + [p["ref"] for p in setting_refs or []]
        )
    )
    _check_brief(brief, refs, by_ref)
    snapshots = [
        {
            "ref": ref,
            "revision": by_ref[ref]["revision"],
            "sha256": by_ref[ref]["sha256"],
        }
        for ref in refs
    ]
    return records.create_record(
        root,
        "discussion",
        name,
        body,
        refs=refs,
        fields={
            "purpose": "phase_summary",
            "summary_of": summary_of,
            "summary_for": summary_for,
            "brief": deepcopy(brief),
            "source_snapshots": snapshots,
            "setting_refs": setting_refs or [],
        },
    )


def publish_summary(
    workspace: Path, relative: str, expected: str, source: dict
) -> None:
    records.human_source(source)
    root = records.archive_root(workspace)
    with records.locked(root):
        rows = records._records(root)
        path = records.within(root, relative)
        meta, body = records.read_note(path)
        project, _ = records.read_note(root / "init.md")
        if (
            meta.get("purpose") != "phase_summary"
            or meta["status"] != "open"
            or meta["project_id"] != project["project_id"]
            or path.parent != root / "discussions"
        ):
            raise ValueError(
                "Publish a current phase-summary draft in this project."
            )
        if _summary_stale(root, meta, rows):
            raise ValueError(
                "Phase summary sources changed; revise the draft and source snapshots first."
            )
        _check_brief(
            meta.get("brief"),
            meta.get("refs", []),
            {"record:" + r["id"]: r for r in rows},
        )
        if {s["ref"] for s in meta.get("source_snapshots", [])} != set(
            meta["refs"]
        ):
            raise ValueError(
                "Source snapshots must cover every phase-summary reference."
            )
        meta.update(status="recorded", reviewed_by=source)
        meta["revision"] += 1
        records._commit(
            root,
            path,
            meta,
            body,
            expected,
            "human",
            "Review phase summary for routed context",
            source,
        )
        records._reindex(root)


def main() -> int:
    parser = argparse.ArgumentParser(description="Rondel context routing")
    sub = parser.add_subparsers(dest="command", required=True)
    find = sub.add_parser("discover")
    find.add_argument("--start", required=True, type=Path)
    find.add_argument("--boundary", type=Path)
    intent = sub.add_parser("intent")
    intent.add_argument("--request", required=True, type=Path)
    validate_intent = sub.add_parser("validate-intent")
    validate_intent.add_argument("--seed", required=True, type=Path)
    validate_intent.add_argument("--result", required=True, type=Path)
    validate_intent.add_argument("--current-request-key")
    for command in ("packet", "lookup", "visibility", "summary", "publish"):
        p = sub.add_parser(command)
        p.add_argument("--root", required=True, type=Path)
        if command == "packet":
            p.add_argument("--mode", required=True)
            p.add_argument("--target", action="append", default=[])
            p.add_argument("--max-chars", type=int, default=6000)
            p.add_argument("--stdout", action="store_true")
            p.add_argument("--out")
        elif command == "lookup":
            p.add_argument("--query", required=True)
            p.add_argument("--include-archive", action="store_true")
        else:
            p.add_argument("--request", required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.command == "discover":
            result = discover(args.start, args.boundary)
        elif args.command == "intent":
            request = yaml.safe_load(
                args.request.read_text(encoding="utf-8-sig")
            )
            result = intent_seed(**request)
        elif args.command == "validate-intent":
            seed = json.loads(args.seed.read_text(encoding="utf-8-sig"))
            result = validate_intent_result(
                args.result.read_text(encoding="utf-8-sig"),
                seed,
                args.current_request_key,
            )
        elif args.command == "packet":
            result = packet(args.root, args.mode, args.target, args.max_chars)
            if args.out:
                root = records.archive_root(args.root)
                target = records.within(root, args.out)
                if (
                    not target.is_relative_to(root / ".state/context")
                    or target.suffix != ".json"
                ):
                    raise ValueError(
                        "Write context packets to JSON inside .state/context."
                    )
                records.atomic_write(
                    target, json.dumps(result, ensure_ascii=False) + "\n"
                )
                print("Context packet:", target)
            if not args.stdout:
                print("Selected mode:", result["route"]["mode"])
                return 0
            print(json.dumps(result, ensure_ascii=False))
            return 0
        elif args.command == "lookup":
            result = lookup(args.root, args.query, args.include_archive)
        else:
            request = yaml.safe_load(
                args.request.read_text(encoding="utf-8-sig")
            )
            functions = {
                "visibility": set_visibility,
                "summary": create_summary,
                "publish": publish_summary,
            }
            print(
                "Saved:",
                functions[args.command](args.root, **request)
                or "reviewed summary",
            )
            return 0
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, TypeError, KeyError, yaml.YAMLError) as error:
        print("Error:", error)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
