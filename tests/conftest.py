"""在临时目录中测试纯记录能力。"""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    """加载可独立安装的脚本。"""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


records = load_module("records", ROOT / "skills/rondel-main/scripts/records.py")
builder = load_module("builder", ROOT / "scripts/build_skills.py")


@pytest.fixture
def api():
    return records


@pytest.fixture
def source():
    return {
        "kind": "user_message",
        "reference": "fixture/current-reply",
        "quote": "请在这个指定目录整理我的研究项目，先澄清问题。",
    }


@pytest.fixture
def project(tmp_path, source):
    root = tmp_path / "研究笔记 with spaces"
    records.initialize(
        root, "示例研究", "我想理解模型在什么条件下出错。", source
    )
    return records.archive_root(root)


@pytest.fixture
def build_api():
    return builder
