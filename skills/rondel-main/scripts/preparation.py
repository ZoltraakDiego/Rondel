"""维护前期总表、冻结设置、版本变更和可重建的 Todo/Changelog。"""

from __future__ import annotations

import argparse
import importlib.util
import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import yaml

spec = importlib.util.spec_from_file_location(
    "rondel_preparation_records", Path(__file__).with_name("records.py")
)
records = importlib.util.module_from_spec(spec)
spec.loader.exec_module(records)

TASKS = {
    "field_pains": "核心领域痛点有来源、条件与当前优先级",
    "core_questions": "核心问题关联痛点，当前主问题明确",
    "literature": "领域地图与核心阅读集合已经审阅",
    "core_reading": "用户自己的摘要、解释与未解疑问已保存",
    "datasets": "选定数据设置已核验并冻结",
    "protocols": "数据、监督与评价协议已核验并冻结",
    "baselines": "Baseline 来源、版本和配方已核验并冻结",
    "environment": "目标环境设置已核验并冻结",
    "reproduction": "约定范围的基线复现有可信证据",
    "phase_review": "前期完成依据、剩余缺口与下一项验证已审阅",
}
TASK_PURPOSES = {
    "datasets": "dataset",
    "protocols": "protocol",
    "baselines": "baseline",
    "environment": "environment",
}
START, END = (
    "<!-- rondel:preparation:start -->",
    "<!-- rondel:preparation:end -->",
)


def _todo_body(body: str, tasks: dict) -> str:
    lines = [START, "| 准备项 | 已记录状态 | 说明 |", "|---|---|---|"]
    for key, label in TASKS.items():
        task = tasks[key]
        note = task.get("note", "").replace("|", "／").replace("\n", " ")
        lines.append(f"| {label} | {task['state']} | {note} |")
    block = "\n".join(lines) + "\n" + END
    if START in body and END in body:
        before, rest = body.split(START, 1)
        _, after = rest.split(END, 1)
        return before + block + after
    return body.rstrip() + "\n\n" + block + "\n"


def _rows(root: Path) -> dict:
    return {"record:" + row["id"]: row for row in records._records(root)}


def _board(root: Path) -> tuple[Path, dict, str]:
    matches = [
        r for r in _rows(root).values() if r.get("purpose") == "preparation"
    ]
    if len(matches) != 1:
        raise ValueError(
            "Initialize one preparation board, or reconcile duplicates."
        )
    path = records.within(root, matches[0]["path"])
    meta, body = records.read_note(path)
    return path, meta, body


def initialize(workspace: Path, source: dict) -> Path:
    """按需建立唯一总表；重复进入保留已有进度，不虚构已选设置。"""
    records.human_source(source)
    root = records.archive_root(workspace)
    with records.locked(root):
        existing = [
            r for r in _rows(root).values() if r.get("purpose") == "preparation"
        ]
        if existing:
            return _board(root)[0]
        project, _ = records.read_note(root / "init.md")
        meta = {
            "schema_version": 1,
            "id": "discussion-" + uuid4().hex,
            "project_id": project["project_id"],
            "type": "discussion",
            "display_name": "前期准备总表",
            "status": "open",
            "revision": 1,
            "purpose": "preparation",
            "refs": [],
            "focus": {
                "pain_refs": [],
                "question_refs": [],
                "primary_question_ref": None,
            },
            "tasks": {
                key: {"state": "todo", "evidence": [], "note": ""}
                for key in TASKS
            },
        }
        path = records.within(root, "discussions/" + meta["id"] + ".md")
        body = (
            "# 前期准备总表\n\n"
            "领域痛点、核心问题、设置与待办在本记录中持续接续。"
            "未知设置先留空，选定后核验并冻结；每项完成需要实际依据。\n\n"
            "## 研究者讨论\n\n"
            "记录当前最需要判断的缺口、取舍和下一次检查点。\n"
        )
        records._commit(
            root,
            path,
            meta,
            _todo_body(body, meta["tasks"]),
            None,
            "human",
            "Initialize preparation tracking",
            source,
        )
        records._reindex(root)
    return path


def create_setting(
    workspace: Path,
    key: str,
    purpose: str,
    name: str,
    spec: dict,
    body: str,
    refs: list[str] | None = None,
) -> Path:
    return records.create_record(
        workspace,
        "resource",
        name,
        body,
        refs=refs,
        fields={
            "purpose": purpose,
            "setting_key": key,
            "setting_version": 1,
            "setting_state": "draft",
            "spec": spec,
        },
    )


def _setting(
    root: Path, relative: str, expected: str | None = None
) -> tuple[Path, dict, str]:
    path = records.within(root, relative)
    meta, body = records.read_note(path)
    project, _ = records.read_note(root / "init.md")
    records.check_meta(meta)
    if (
        path.parent != records.within(root, records.FOLDERS["resource"])
        or meta.get("project_id") != project["project_id"]
        or "setting_key" not in meta
    ):
        raise ValueError(
            "Choose a current preparation setting in this project."
        )
    if expected is not None and records.digest(path) != expected:
        raise ValueError("Setting changed; reread before continuing.")
    if (
        meta["setting_state"] == "frozen"
        and records.definition_digest(meta, body) != meta["definition_sha256"]
    ):
        raise ValueError(
            "Frozen setting definition changed; review before continuing."
        )
    return path, meta, body


def pin(workspace: Path, relative: str) -> dict:
    root = records.archive_root(workspace)
    _, meta, _ = _setting(root, relative)
    if meta["setting_state"] != "frozen":
        raise ValueError("Only frozen settings can be pinned to results.")
    return {
        "ref": "record:" + meta["id"],
        "version": meta["setting_version"],
        "definition_sha256": meta["definition_sha256"],
    }


def freeze(
    workspace: Path, relative: str, expected: str, source: dict, reason: str
) -> None:
    records.human_source(source)
    root = records.archive_root(workspace)
    with records.locked(root):
        path, meta, body = _setting(root, relative, expected)
        if (
            meta["setting_state"] != "draft"
            or meta["status"] != "checked"
            or not meta["spec"]
        ):
            raise ValueError(
                "Freeze a checked draft with a nonempty definition."
            )
        prior = sorted(
            (
                r
                for r in _rows(root).values()
                if r.get("setting_key") == meta["setting_key"]
                and r.get("setting_state") == "frozen"
            ),
            key=lambda r: r["setting_version"],
        )
        if prior:
            latest = prior[-1]
            if (
                meta.get("supersedes") != "record:" + latest["id"]
                or meta["setting_version"] != latest["setting_version"] + 1
            ):
                raise ValueError(
                    "Revise the current frozen setting before adopting a new version."
                )
        elif meta["setting_version"] != 1:
            raise ValueError("The first frozen setting must be version 1.")
        meta.update(
            setting_state="frozen",
            frozen_by=source,
            definition_sha256=records.definition_digest(meta, body),
        )
        meta["revision"] += 1
        records._commit(
            root, path, meta, body, expected, "human", reason, source
        )
        records._reindex(root)


def revise(
    workspace: Path,
    relative: str,
    expected: str,
    spec: dict,
    source: dict,
    reason: str,
    impact_review: dict,
    body: str | None = None,
) -> Path:
    """旧定义不动，新版本先成为草案；影响说明与自动依赖清单一起入历史。"""
    records.human_source(source)
    if not isinstance(impact_review, dict) or not impact_review.get("summary"):
        raise ValueError("A setting revision needs an impact review summary.")
    root = records.archive_root(workspace)
    with records.locked(root):
        _, old, previous_body = _setting(root, relative, expected)
        if old["setting_state"] != "frozen":
            raise ValueError("Edit a draft normally; revise a frozen setting.")
        siblings = [
            r
            for r in _rows(root).values()
            if r.get("setting_key") == old["setting_key"]
        ]
        if any(r["setting_version"] > old["setting_version"] for r in siblings):
            raise ValueError(
                "A newer setting version already exists; review it first."
            )
        meta = {
            "schema_version": 1,
            "id": "resource-" + uuid4().hex,
            "project_id": old["project_id"],
            "type": "resource",
            "display_name": old["display_name"],
            "status": "recorded",
            "revision": 1,
            "purpose": old["purpose"],
            "setting_key": old["setting_key"],
            "setting_version": old["setting_version"] + 1,
            "setting_state": "draft",
            "spec": deepcopy(spec),
            "supersedes": "record:" + old["id"],
            "refs": list(
                dict.fromkeys(old.get("refs", []) + ["record:" + old["id"]])
            ),
            "impact_review": deepcopy(impact_review),
        }
        path = records.within(root, "setup/resources/" + meta["id"] + ".md")
        records._commit(
            root,
            path,
            meta,
            previous_body if body is None else body,
            None,
            "human",
            reason,
            source,
        )
        records._reindex(root)
    return path


def set_task(
    workspace: Path,
    key: str,
    state: str,
    evidence: list[str],
    note: str,
    expected: str,
    source: dict | None = None,
) -> None:
    if key not in TASKS or state not in {
        "todo",
        "in_progress",
        "blocked",
        "done",
        "waived",
    }:
        raise ValueError("Unknown preparation task or state.")
    if state == "waived":
        records.human_source(source)
    if not note.strip() or state == "done" and not evidence:
        raise ValueError("Task completion needs evidence and an explanation.")
    root = records.archive_root(workspace)
    with records.locked(root):
        path, meta, body = _board(root)
        rows = _rows(root)
        if any(ref not in rows for ref in evidence):
            raise ValueError(
                "Task evidence must reference current project records."
            )
        meta["tasks"][key] = {
            "state": state,
            "evidence": evidence,
            "note": note,
            "evidence_hashes": {ref: rows[ref]["sha256"] for ref in evidence},
            "source": source,
        }
        meta["refs"] = list(dict.fromkeys(meta.get("refs", []) + evidence))
        meta["revision"] += 1
        records._commit(
            root,
            path,
            meta,
            _todo_body(body, meta["tasks"]),
            expected,
            "human" if source else "assistant",
            "Update preparation task: " + key,
            source,
        )
        records._reindex(root)


def changelog(workspace: Path) -> list[dict]:
    root = records.archive_root(workspace)
    path = root / "history/events.jsonl"
    return (
        [
            event
            for line in path.read_text(encoding="utf-8").splitlines()
            if "preparation_change" in (event := json.loads(line))
        ]
        if path.exists()
        else []
    )


def _settings_used(rows: dict, ref: str, seen: set | None = None) -> set[str]:
    seen = set() if seen is None else seen
    if ref in seen:
        return set()
    seen.add(ref)
    row = rows.get(ref, {})
    if "setting_key" in row:
        return {ref}
    aliases = {"project:" + r["path"]: key for key, r in rows.items()}
    refs = row.get("refs", []) + [p["ref"] for p in row.get("setting_refs", [])]
    result = set()
    for target in refs:
        result.update(_settings_used(rows, aliases.get(target, target), seen))
    return result


def status(workspace: Path) -> dict:
    """只读计算准备情况；文件齐全不替代语义审阅和人的阶段决定。"""
    root = records.archive_root(workspace)
    path, meta, _ = _board(root)
    rows = _rows(root)
    focus = meta.get("focus", {})
    issues = []
    project, _ = records.read_note(root / "init.md")
    if not project["research_anchor"].get("search_summary"):
        issues.append("search_summary_missing")
    pains = [rows.get(ref, {}) for ref in focus.get("pain_refs", [])]
    questions = [rows.get(ref, {}) for ref in focus.get("question_refs", [])]
    if not pains or any(r.get("purpose") != "field_pain" for r in pains):
        issues.append("field_pains_missing")
    if not questions or any(
        r.get("purpose") != "core_question" for r in questions
    ):
        issues.append("core_questions_missing")
    if focus.get("primary_question_ref") not in focus.get("question_refs", []):
        issues.append("primary_question_missing")
    elif rows.get(focus["primary_question_ref"], {}).get("status") != "active":
        issues.append("primary_question_not_selected")
    for question in questions:
        if not set(question.get("pain_refs", [])).intersection(
            focus.get("pain_refs", [])
        ):
            issues.append("core_question_without_pain_link")
    current = {}
    for ref, row in rows.items():
        if row.get("setting_state") == "frozen":
            key = row["setting_key"]
            if (
                key not in current
                or row["setting_version"] > current[key]["version"]
            ):
                current[key] = {
                    "ref": ref,
                    "version": row["setting_version"],
                    "purpose": row["purpose"],
                }
    tasks = {}
    for key, label in TASKS.items():
        task = deepcopy(
            meta.get("tasks", {}).get(key, {"state": "todo", "evidence": []})
        )
        problems = []
        evidence = task.get("evidence", [])
        if task["state"] == "waived":
            records.human_source(task.get("source"))
            if not task.get("note"):
                problems.append("waiver_reason_missing")
        if task["state"] == "done":
            if not evidence or any(ref not in rows for ref in evidence):
                problems.append("evidence_missing")
            for ref in evidence:
                row = rows.get(ref, {})
                if task.get("evidence_hashes", {}).get(ref) != row.get(
                    "sha256"
                ):
                    problems.append("evidence_changed")
                if key in TASK_PURPOSES and (
                    row.get("purpose") != TASK_PURPOSES[key]
                    or row.get("setting_state") != "frozen"
                    or row.get("status") != "checked"
                    or current.get(row.get("setting_key"), {}).get("ref") != ref
                ):
                    problems.append("setting_missing_unchecked_or_superseded")
                for used in _settings_used(rows, ref):
                    old = rows[used]
                    latest = current.get(old["setting_key"], {})
                    if latest.get("ref") != used:
                        reviews = (
                            rows.get(latest.get("ref"), {})
                            .get("impact_review", {})
                            .get("results", {})
                        )
                        review = reviews.get(ref, {})
                        if review.get("action") != "keep" or not review.get(
                            "reason"
                        ):
                            problems.append(
                                "evidence_uses_previous_setting_needs_review"
                            )
            expected = {
                "literature": "literature_map",
                "core_reading": "core_paper",
                "phase_review": "phase_review",
                "field_pains": "field_pain",
                "core_questions": "core_question",
            }.get(key)
            if expected and not any(
                rows.get(ref, {}).get("purpose") == expected for ref in evidence
            ):
                problems.append("evidence_role_mismatch")
            if key == "reproduction" and not any(
                rows.get(ref, {}).get("type") == "run"
                and rows[ref]["status"] == "completed"
                and rows[ref].get("check_status") == "valid"
                for ref in evidence
            ):
                problems.append("valid_reproduction_run_missing")
        task.update(
            label=label,
            effective_state="needs_review" if problems else task["state"],
            issues=problems,
        )
        tasks[key] = task
    return {
        "board_ref": "record:" + meta["id"],
        "board_path": path.relative_to(root).as_posix(),
        "focus": focus,
        "tasks": tasks,
        "settings": current,
        "issues": issues,
        "pre_review_tasks_complete": not issues
        and all(
            task["effective_state"] in {"done", "waived"}
            for key, task in tasks.items()
            if key != "phase_review"
        ),
        "checklist_complete": not issues
        and all(
            t["effective_state"] in {"done", "waived"} for t in tasks.values()
        ),
        "pending_setting_drafts": [
            ref
            for ref, row in rows.items()
            if row.get("setting_state") == "draft"
        ],
    }


def write_reports(workspace: Path) -> list[Path]:
    """显式生成可读投影；总表与历史事件仍为来源。"""
    root = records.archive_root(workspace)
    with records.locked(root):
        value = status(root)
        rows = _rows(root)
        changes = changelog(root)
        todo = "# 前期准备 Todo\n\n由前期总表与当前记录重建，修改通过原记录进行。\n\n"
        todo += (
            "常规准备项结构检查："
            + (
                "已齐，可发起退出评审"
                if value["pre_review_tasks_complete"]
                else "仍有待核对项，评审可明确补充与取舍"
            )
            + "。阶段是否转换由实际证据与用户选择决定。\n\n"
        )
        todo += "| 项目 | 有效状态 | 说明 |\n|---|---|---|\n"
        for task in value["tasks"].values():
            note = task.get("note", "").replace("|", "／").replace("\n", " ")
            todo += (
                f"| {task['label']} | {task['effective_state']} | {note} |\n"
            )
        todo += "\n## 核心痛点与问题\n\n| 角色 | 内容 |\n|---|---|\n"
        for role, key in (
            ("领域痛点", "pain_refs"),
            ("核心问题", "question_refs"),
        ):
            for ref in value["focus"].get(key, []):
                row = rows.get(ref, {})
                name = (
                    row.get("display_name", ref)
                    .replace("|", "／")
                    .replace("\n", " ")
                )
                todo += f"| {role} | {name} |\n"
        todo += "\n## 当前冻结设置\n\n| 设置 | 版本 | 记录 |\n|---|---|---|\n"
        for key, setting in value["settings"].items():
            row = rows[setting["ref"]]
            name = row["display_name"].replace("|", "／").replace("\n", " ")
            todo += f"| {name} | {setting['version']} | [查看](../{row['path']}) |\n"
        todo += "\n\n## 待核对项\n\n" + "、".join(
            value["issues"] or ["清单状态仍需结合内容共同审阅"]
        )
        log = "# 前期设置 Changelog\n\n从历史事件重建；潜在影响需逐项判断处理方式。\n"
        for event in changes:
            change = event["preparation_change"]
            stamp = (
                datetime.fromisoformat(event["timestamp"])
                .astimezone(timezone(timedelta(hours=8)))
                .isoformat()
            )
            log += f"\n## {stamp} · {change['setting_key']} v{change['version']} · {change['state']}\n\n"
            source = event.get("source") or {}
            log += (
                event["reason"]
                + "\n\n来源："
                + source.get("quote", "Agent 草案记录")
                + "\n\n"
            )
            log += (
                "变化字段："
                + "、".join(change.get("changed_spec_fields", []))
                + "\n\n"
            )
            log += (
                "处理说明："
                + change["impact_review"].get("summary", "初始化或待审阅")
                + "\n\n"
            )
            log += "| 潜在影响对象 | 处理建议 | 理由 |\n|---|---|---|\n"
            for row in change["affected"]:
                review = (
                    change["impact_review"]
                    .get("results", {})
                    .get(row["ref"], {})
                )
                name = row["name"].replace("|", "／").replace("\n", " ")
                reason = (
                    review.get("reason", "待核对实际条件")
                    .replace("|", "／")
                    .replace("\n", " ")
                )
                log += f"| [{name}](../{row['path']}) | {review.get('action', 'needs_review')} | {reason} |\n"
            if change["untracked_results"]:
                log += (
                    "另有缺少依赖引用的历史结果，需人工核对："
                    + "、".join(change["untracked_results"])
                    + "\n"
                )
        paths = [
            root / "setup/preparation-todo.md",
            root / "history/preparation-changelog.md",
        ]
        for path, text in zip(paths, [todo, log], strict=True):
            records.atomic_write(
                records.within(root, path.relative_to(root).as_posix()),
                text + "\n",
            )
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Preparation tracking and setting versions"
    )
    parser.add_argument("--root", required=True, type=Path)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("report")
    sub.add_parser("changelog")
    init = sub.add_parser("init")
    init.add_argument("--source", required=True, type=Path)
    pin_parser = sub.add_parser("pin")
    pin_parser.add_argument("--note", required=True)
    pin_parser.add_argument("--out", required=True)
    for name in ("setting", "freeze", "revise", "task"):
        request = sub.add_parser(name)
        request.add_argument("--request", required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.command == "init":
            source = yaml.safe_load(args.source.read_text(encoding="utf-8-sig"))
            print("Preparation board:", initialize(args.root, source))
        elif args.command == "status":
            result = status(args.root)
            print("Preparation tasks:", len(result["tasks"]))
            print(
                "Pre-review task checklist complete:",
                result["pre_review_tasks_complete"],
            )
            print(
                "Preparation checklist complete:", result["checklist_complete"]
            )
            for key, task in result["tasks"].items():
                print(key, task["effective_state"])
        elif args.command == "changelog":
            print("Setting change events:", len(changelog(args.root)))
        elif args.command == "report":
            for path in write_reports(args.root):
                print("Generated:", path)
        elif args.command == "pin":
            value = pin(args.root, args.note)
            root = records.archive_root(args.root)
            path = records.within(root, args.out)
            if (
                not path.is_relative_to(root / ".state/preparation")
                or path.suffix != ".json"
            ):
                raise ValueError(
                    "Write pins to a JSON file inside .state/preparation."
                )
            records.atomic_write(
                path, json.dumps(value, ensure_ascii=False, indent=2) + "\n"
            )
            print("Setting reference:", path)
        else:
            request = yaml.safe_load(
                args.request.read_text(encoding="utf-8-sig")
            )
            functions = {
                "setting": create_setting,
                "freeze": freeze,
                "revise": revise,
                "task": set_task,
            }
            print(
                "Saved:",
                functions[args.command](args.root, **request)
                or "preparation update",
            )
        return 0
    except (OSError, ValueError, TypeError, KeyError, yaml.YAMLError) as error:
        print("Error:", error)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
