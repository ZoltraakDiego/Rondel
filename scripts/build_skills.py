"""同步共享维护源，并生成只包含可用技能的安装包。"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import tomllib
import zipfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/rondel-main"
VERSION = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
    "project"
]["version"]


def shared_files() -> dict[Path, Path]:
    """映射共享源到安装目录，保证技能可独立使用。"""
    mapping = {
        ROOT / "LICENSE": SKILL / "LICENSE",
        ROOT / "shared/contracts/note-contract.md": (
            SKILL / "references/shared/note-contract.md"
        ),
        ROOT / "shared/context/context-loading.md": (
            SKILL / "references/shared/context-loading.md"
        ),
        ROOT / "shared/styles/communication.md": (
            SKILL / "references/shared/communication.md"
        ),
        ROOT / "shared/tool-catalog.yaml": (
            SKILL / "references/shared/tool-catalog.yaml"
        ),
        ROOT / "shared/context/router-models.yaml": (
            SKILL / "references/shared/router-models.yaml"
        ),
    }
    for source in (ROOT / "shared/templates").glob("*.md"):
        mapping[source] = SKILL / "assets/templates" / source.name
    return mapping


def agent_templates() -> dict[Path, bytes]:
    """从同一提示词与模型策略生成两种宿主模板，不修改用户配置。"""
    policy = yaml.safe_load(
        (ROOT / "shared/context/router-models.yaml").read_text(encoding="utf-8")
    )
    prompt = (ROOT / "shared/templates/router-subagent.md").read_text(
        encoding="utf-8"
    )
    codex = (
        'name = "rondel-router"\n'
        'description = "Classify new Rondel task intents and return only compact routing JSON."\n'
        + "model = "
        + json.dumps(policy["codex"]["model"])
        + "\n"
        + "model_reasoning_effort = "
        + json.dumps(policy["codex"]["reasoning_effort"])
        + "\n"
        + "developer_instructions = "
        + json.dumps(prompt, ensure_ascii=False)
        + "\n\n"
        + "[features]\nshell_tool = false\napps = false\nplugins = false\nmemories = false\nrequest_permissions_tool = false\n\n"
        + "[skills]\ninclude_instructions = false\n"
    )
    claude = {
        "name": "rondel-router",
        "description": "Classify new Rondel task intents proactively; return only compact routing JSON.",
        "model": policy["claude"]["model"],
        "tools": "Read",
        "maxTurns": policy["claude"]["max_turns"],
        "omitClaudeMd": policy["claude"]["omit_claude_md"],
    }
    markdown = (
        "---\n" + yaml.safe_dump(claude, sort_keys=False) + "---\n\n" + prompt
    )
    return {
        SKILL / "assets/agents/codex/rondel-router.toml": codex.encode(),
        SKILL / "assets/agents/claude/rondel-router.md": markdown.encode(),
    }


def sync(check: bool = False) -> list[str]:
    """检查或同步共享资源，检查模式不写文件。"""
    issues = []
    payloads = {}
    for source, target in shared_files().items():
        if not source.exists():
            issues.append(f"Missing shared source: {source.relative_to(ROOT)}")
            continue
        payloads[target] = source.read_bytes()
    payloads.update(agent_templates())
    for target, payload in payloads.items():
        if target.exists() and target.read_bytes() == payload:
            continue
        if check:
            issues.append(
                f"Shared resource out of date: {target.relative_to(ROOT)}"
            )
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
    return issues


def files() -> list[Path]:
    """选择发布资源，排除缓存、链接和生成的字节码。"""
    result = []
    for path in sorted(SKILL.rglob("*")):
        if any(
            part.startswith(".") or part == "__pycache__"
            for part in path.relative_to(SKILL).parts
        ):
            continue
        if path.is_symlink():
            raise ValueError("Release resources must be regular files.")
        if path.is_file() and path.suffix not in {".pyc", ".pyo"}:
            result.append(path)
    return result


def check_links() -> list[str]:
    """核对安装包内 Markdown 的相对文件引用。"""
    issues = []
    for path in files():
        if path.suffix != ".md":
            continue
        for link in re.findall(
            r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")
        ):
            if re.match(r"[a-zA-Z][a-zA-Z0-9+.-]*:", link) or link.startswith(
                "#"
            ):
                continue
            relative = link.split("#", 1)[0]
            target = (path.parent / relative).resolve()
            if (
                not target.is_relative_to(SKILL.resolve())
                or not target.is_file()
            ):
                issues.append(f"Unresolved skill link in {path.name}: {link}")
    return issues


def check_catalog() -> list[str]:
    """核对公开能力与实际入口一致。"""
    catalog = yaml.safe_load(
        (ROOT / "shared/tool-catalog.yaml").read_text(encoding="utf-8")
    )
    tools = catalog["tools"]
    issues = []
    ids = [tool["id"] for tool in tools]
    if len(ids) != len(set(ids)):
        issues.append("Duplicate tool IDs.")
    for tool in tools:
        if tool["status"] == "available":
            target = ROOT / "skills" / tool["entrypoint"] / tool["reference"]
            if not target.is_file():
                issues.append(
                    f"Available tool missing implementation: {tool['id']}"
                )
        elif tool["status"] != "planned":
            issues.append(f"Unknown capability status: {tool['id']}")
    return issues


def package(destination: Path | None = None) -> Path:
    """生成带逐文件摘要的独立技能压缩包。"""
    issues = sync(check=True) + check_links() + check_catalog()
    if issues:
        raise ValueError("; ".join(issues))
    destination = destination or ROOT / "dist"
    destination.mkdir(parents=True, exist_ok=True)
    archive = destination / f"rondel-main-{VERSION}.zip"
    manifest = []
    with zipfile.ZipFile(
        archive, "w", compression=zipfile.ZIP_DEFLATED
    ) as stream:
        for path in files():
            relative = "rondel-main/" + path.relative_to(SKILL).as_posix()
            payload = path.read_bytes()
            info = zipfile.ZipInfo(relative, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            stream.writestr(info, payload)
            manifest.append(
                {
                    "path": relative,
                    "bytes": len(payload),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                }
            )
    (destination / f"rondel-main-{VERSION}.manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return archive


def main() -> int:
    """打印英文状态摘要，不向终端展开结构化清单。"""
    parser = argparse.ArgumentParser(description="Build Rondel skill resources")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--package", action="store_true")
    args = parser.parse_args()
    issues = sync(check=args.check)
    issues += check_links() + check_catalog()
    for issue in issues:
        print("Issue:", issue)
    if issues:
        return 1
    if args.package:
        print("Created:", package())
    print("Skill resources are consistent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
