"""按显式清单导出两个研究包并核对文件完整性，不运行科研命令。"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import shutil
from pathlib import Path, PurePosixPath

spec = importlib.util.spec_from_file_location(
    "rondel_closeout_records", Path(__file__).with_name("records.py")
)
records = importlib.util.module_from_spec(spec)
spec.loader.exec_module(records)
PACKAGES = {"reproduction", "materials"}


def file_digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def plan(workspace: Path, request: dict) -> dict:
    """只读展开明确选择的本地文件；外部资料保持引用。"""
    root = records.archive_root(workspace)
    records.read_note(root / "init.md")
    if not isinstance(request, dict):
        raise ValueError("Use a JSON object for the delivery request.")
    release = request.get("release_id", "")
    if not isinstance(release, str) or not re.fullmatch(
        r"[a-z0-9][a-z0-9_-]{0,63}", release
    ):
        raise ValueError("Use a short lowercase release_id.")
    items = request.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("Select explicit files in items.")
    files, seen = [], set()
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Each item must be a file-selection object.")
        package, target = item.get("package"), item.get("target", "")
        if package not in PACKAGES or not isinstance(target, str) or not target:
            raise ValueError(
                "Use reproduction/materials and a relative target."
            )
        relative = PurePosixPath(target)
        if (
            relative.is_absolute()
            or any(p == ".." for p in relative.parts)
            or any(c in target for c in "\\:")
            or target == "."
        ):
            raise ValueError("Use safe relative targets with forward slashes.")
        output = package + "/" + relative.as_posix()
        normalized = output.casefold()
        if any(
            normalized == p
            or normalized.startswith(p + "/")
            or p.startswith(normalized + "/")
            for p in seen
        ):
            raise ValueError("Duplicate or conflicting package targets.")
        seen.add(normalized)
        source = Path(item["source"])
        source = source if source.is_absolute() else root / source
        if source.is_symlink() or not source.is_file():
            raise ValueError("Each source must be an existing regular file.")
        files.append(
            {
                "source": str(source.resolve()),
                "path": output,
                "bytes": source.stat().st_size,
                "sha256": file_digest(source),
            }
        )
    if not {p + "/readme.md" for p in PACKAGES} <= seen:
        raise ValueError("Select a README.md entry for each package.")
    references = request.get("references", [])
    if not isinstance(references, list):
        raise ValueError("references must be a list.")
    for ref in references:
        if not isinstance(ref, dict):
            raise ValueError("Each external reference must be an object.")
        if ref.get("package") not in PACKAGES or not all(
            isinstance(ref.get(k), str) and ref[k].strip()
            for k in ("location", "description")
        ):
            raise ValueError(
                "Each reference needs package, location and description."
            )
    return {
        "release_id": release,
        "files": files,
        "references": references,
        "destination": str(records.within(root, "deliverables/" + release)),
    }


def build(workspace: Path, request: dict) -> Path:
    """新建不可覆盖的交付目录；不改变项目阶段、原文件或验证声明。"""
    root = records.archive_root(workspace)
    with records.locked(root):
        selected = plan(root, request)
        destination = Path(selected["destination"])
        destination.mkdir(parents=True, exist_ok=False)
        manifest = {
            "schema_version": 1,
            "release_id": selected["release_id"],
            "verification_level": "file_integrity_only",
            "files": [],
            "references": selected["references"],
        }
        for item in selected["files"]:
            target = records.within(destination, item["path"])
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(item["source"], target)
            if file_digest(target) != item["sha256"]:
                raise ValueError(
                    "Source changed during export; keep this incomplete release and use a new ID."
                )
            manifest["files"].append(
                {k: item[k] for k in ("path", "bytes", "sha256")}
            )
        records.atomic_write(
            destination / "manifest.json",
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        )
        return destination


def verify(workspace: Path, release_id: str) -> dict:
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", release_id):
        raise ValueError("Use a valid release_id.")
    root = records.archive_root(workspace)
    destination = records.within(root, "deliverables/" + release_id)
    manifest = json.loads(
        (destination / "manifest.json").read_text(encoding="utf-8")
    )
    issues = []
    for item in manifest["files"]:
        path = records.within(destination, item["path"])
        if not path.is_file() or file_digest(path) != item["sha256"]:
            issues.append(item["path"])
    return {
        "file_integrity_ok": not issues,
        "issues": issues,
        "reproduction_verified": False,
        "references_fetched": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Research delivery file exporter"
    )
    parser.add_argument("--root", required=True, type=Path)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("plan", "build"):
        sub.add_parser(name).add_argument("--request", required=True, type=Path)
    sub.add_parser("verify").add_argument("--release", required=True)
    args = parser.parse_args()
    try:
        if args.command == "verify":
            value = verify(args.root, args.release)
            print("File integrity:", value["file_integrity_ok"])
            print("Research commands were not executed.")
            return 0 if value["file_integrity_ok"] else 1
        request = json.loads(args.request.read_text(encoding="utf-8"))
        if args.command == "plan":
            value = plan(args.root, request)
            print("Selected files:", len(value["files"]))
            print("External references:", len(value["references"]))
        else:
            print("Created:", build(args.root, request))
        return 0
    except (OSError, ValueError, TypeError, KeyError) as error:
        print("Error:", error)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
