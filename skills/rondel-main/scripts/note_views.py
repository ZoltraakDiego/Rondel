"""导出 Markdown/Obsidian 笔记视图，捕获批注而不覆盖研究记录。"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
from pathlib import Path
from urllib.parse import quote

import yaml

spec = importlib.util.spec_from_file_location(
    "rondel_view_records", Path(__file__).with_name("records.py")
)
records = importlib.util.module_from_spec(spec)
spec.loader.exec_module(records)
MANIFEST = ".state/note-views.json"


def _manifest(root: Path) -> dict:
    path = records.within(root, MANIFEST)
    if not path.exists():
        return {"schema_version": 1, "exports": {}, "captures": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def _save(root: Path, manifest: dict) -> None:
    records.atomic_write(
        records.within(root, MANIFEST),
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
    )


def _current_note(root: Path, relative: str) -> tuple[Path, dict, str]:
    path = records.within(root, relative)
    meta, body = records.read_note(path)
    records.check_meta(meta)
    project, _ = records.read_note(root / "init.md")
    if meta["project_id"] != project["project_id"]:
        raise ValueError("Note belongs to another project.")
    if meta["type"] == "project":
        allowed = path == root / "init.md"
    else:
        allowed = path.parent == records.within(
            root, records.FOLDERS[meta["type"]]
        )
    if not allowed:
        raise ValueError("Export a current record, not history or state files.")
    return path, meta, body


def _filename(meta: dict) -> str:
    name = re.sub(r'[<>:"/\\|?*#\[\]^\x00-\x1f]', "-", meta["display_name"])
    name = re.sub(r"\s+", " ", name).strip(" .")[:80] or "研究笔记"
    reserved = {"CON", "PRN", "AUX", "NUL"}
    reserved |= {
        f"{prefix}{n}" for prefix in ("COM", "LPT") for n in range(1, 10)
    }
    if name.split(".")[0].upper() in reserved:
        name = "研究-" + name
    suffix = hashlib.sha256(meta["id"].encode()).hexdigest()[:8]
    return f"{name}--{suffix}.md"


def _render(
    meta: dict, body: str, relative: str, format: str, entries: dict
) -> str:
    properties = {
        "rondel_id": meta["id"],
        "rondel_project": meta["project_id"],
        "rondel_type": meta["type"],
        "rondel_revision": meta["revision"],
        "rondel_status": meta["status"],
        "rondel_source": relative,
        "rondel_format": format,
        "aliases": [meta["display_name"]],
        "tags": ["rondal/view", "rondal/" + meta["type"]],
    }
    related = []
    for ref in meta.get("refs", []):
        match = next(
            (
                entry
                for entry in entries.values()
                if ref == "record:" + entry["record_id"]
                or ref == "project:" + entry["source_relative"]
            ),
            None,
        )
        if match:
            filename = Path(match["view_path"]).name
            label = (
                match["display_name"]
                .replace("|", "／")
                .replace("[", "（")
                .replace("]", "）")
                .replace("\n", " ")
            )
            if format == "obsidian":
                related.append(f"[[{Path(filename).stem}|{label}]]")
            else:
                related.append(f"[{label}]({quote(filename)})")
        else:
            related.append(f"`{ref}`")
    if related:
        body = body.rstrip() + "\n\n## 相关记录视图\n\n" + " · ".join(related)
    body = body.rstrip() + (
        "\n\n## 研究者批注\n\n"
        "在这里写下自己的解释、疑问或修改意见。Agent 回收为待审阅反馈，"
        "不会据此自动批准实验或改写已冻结方案。\n"
    )
    return records.render(properties, body)


def export_note(
    workspace: Path, relative: str, destination: Path, format: str = "obsidian"
) -> Path:
    if format not in {"markdown", "obsidian"}:
        raise ValueError("Unknown note format.")
    root = records.archive_root(workspace)
    records.read_note(root / "init.md")
    destination = destination.resolve()
    if destination.is_relative_to(root):
        raise ValueError("Choose a visible notes directory outside .rondel.")
    if destination == root.parent:
        raise ValueError("Choose a notes directory, not the workspace root.")
    if format == "obsidian" and destination.name.startswith("."):
        raise ValueError("Choose a visible directory in the Obsidian vault.")
    with records.locked(root):
        path, meta, body = _current_note(root, relative)
        manifest = _manifest(root)
        key = hashlib.sha256(
            (meta["id"] + "|" + str(destination) + "|" + format).encode()
        ).hexdigest()
        previous = manifest["exports"].get(key)
        target = destination / (
            Path(previous["view_path"]).name if previous else _filename(meta)
        )
        if target.resolve().parent != destination or target.is_symlink():
            raise ValueError("View target leaves the selected notes directory.")
        if target.exists() and (
            previous is None
            or records.digest(target) != previous["view_sha256"]
        ):
            raise ValueError(
                "View was edited or is unowned; preserve and review it."
            )
        visible = {
            k: entry
            for k, entry in manifest["exports"].items()
            if Path(entry["view_path"]).parent == destination
            and entry["format"] == format
        }
        text = _render(meta, body, relative, format, visible)
        if not target.exists() or target.read_text(encoding="utf-8") != text:
            records.atomic_write(target, text)
        manifest["exports"][key] = {
            "record_id": meta["id"],
            "source_relative": relative,
            "source_revision": meta["revision"],
            "source_sha256": records.digest(path),
            "display_name": meta["display_name"],
            "view_path": str(target),
            "view_sha256": records.digest(target),
            "format": format,
        }
        _save(root, manifest)
    return target


def capture_feedback(workspace: Path, view: Path, source: dict) -> Path | None:
    """捕获编辑内容为新讨论；不回写原记录、状态或批准范围。"""
    records.human_source(source)
    root = records.archive_root(workspace)
    records.read_note(root / "init.md")
    view = view.resolve()
    manifest = _manifest(root)
    entry = next(
        (
            item
            for item in manifest["exports"].values()
            if item["view_path"] == str(view)
        ),
        None,
    )
    if entry is None:
        raise ValueError("View is not registered for this project.")
    content = view.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    if digest == entry["view_sha256"]:
        return None
    capture_key = hashlib.sha256(
        (str(view) + "|" + digest).encode()
    ).hexdigest()
    if capture_key in manifest["captures"]:
        return records.within(root, manifest["captures"][capture_key])
    original, meta, _ = _current_note(root, entry["source_relative"])
    if meta["id"] != entry["record_id"]:
        raise ValueError("Source record identity changed; review the binding.")
    text = content.decode("utf-8-sig")
    fence = "`" * max(
        3, max((len(v) for v in re.findall(r"`+", text)), default=0) + 1
    )
    body = (
        "# 笔记视图反馈待审阅\n\n"
        "以下内容是研究者所编辑视图的完整文本，作为来源材料保存。"
        "原记录、科学状态与已批准实验保持原样；Main 审阅后按实际决定处理。\n\n"
        + fence
        + "markdown\n"
        + text
        + "\n"
        + fence
        + "\n"
    )
    feedback = records.create_record(
        root,
        "discussion",
        "笔记反馈：" + meta["display_name"],
        body,
        refs=["record:" + meta["id"]],
        fields={
            "purpose": "note_feedback",
            "source": source,
            "view_sha256": digest,
            "exported_revision": entry["source_revision"],
            "source_has_advanced": records.digest(original)
            != entry["source_sha256"],
            "resolution": "pending_review",
        },
    )
    with records.locked(root):
        current = _manifest(root)
        current["captures"][capture_key] = feedback.relative_to(root).as_posix()
        _save(root, current)
    return feedback


def view_status(workspace: Path) -> list[dict]:
    """只读定位视图批注与来源变动，不改写笔记或状态。"""
    root = records.archive_root(workspace)
    records.read_note(root / "init.md")
    result = []
    for entry in _manifest(root)["exports"].values():
        view = Path(entry["view_path"])
        source = records.within(root, entry["source_relative"])
        missing = not view.is_file()
        source_missing = not source.is_file()
        result.append(
            {
                "display_name": entry["display_name"],
                "view_path": str(view),
                "view_missing": missing,
                "edited": not missing
                and records.digest(view) != entry["view_sha256"],
                "source_missing": source_missing,
                "source_has_advanced": not source_missing
                and records.digest(source) != entry["source_sha256"],
            }
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Research note views")
    parser.add_argument("--root", required=True, type=Path)
    sub = parser.add_subparsers(dest="command", required=True)
    export = sub.add_parser("export")
    export.add_argument("--note", required=True)
    export.add_argument("--destination", required=True, type=Path)
    export.add_argument(
        "--format", choices=["markdown", "obsidian"], default="obsidian"
    )
    capture = sub.add_parser("capture")
    capture.add_argument("--view", required=True, type=Path)
    capture.add_argument("--source", required=True, type=Path)
    sub.add_parser("status")
    args = parser.parse_args()
    try:
        if args.command == "status":
            rows = view_status(args.root)
            print("Registered views:", len(rows))
            for row in rows:
                flags = [
                    name
                    for name in (
                        "edited",
                        "view_missing",
                        "source_missing",
                        "source_has_advanced",
                    )
                    if row[name]
                ]
                if flags:
                    print("Review:", row["view_path"], ", ".join(flags))
            return 0
        if args.command == "export":
            result = export_note(
                args.root, args.note, args.destination, args.format
            )
        else:
            source = yaml.safe_load(args.source.read_text(encoding="utf-8-sig"))
            result = capture_feedback(args.root, args.view, source)
        print("Saved:" if result else "No new edits:", result or args.view)
        return 0
    except (OSError, ValueError, TypeError, KeyError) as error:
        print("Error:", error)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
