"""验证轻量路由输入隔离、结构化返回与宿主模板。"""

import json
import tomllib
from copy import deepcopy

import pytest
import yaml
from conftest import ROOT, load_module

routing = load_module(
    "subagent_routing_test", ROOT / "skills/rondel-main/scripts/routing.py"
)


def decision():
    return {
        "mode": "pre.protocol",
        "intent": "核对当前数据协议",
        "read_only": True,
        "targets": [],
        "needs_main_review": False,
        "reason": "用户只请求核对协议。",
    }


def test_seed_is_small_isolated_and_uses_requested_runtime_profile():
    value = routing.intent_seed(
        "先别实验，只核对支持集和查询集的协议。",
        context_hint={"phase": "prepare", "task_label": "准备复现"},
        read_only_constraint=True,
    )
    assert value["preferred_profile"] == {
        "model": "gpt-6-luna",
        "reasoning_effort": "low",
        "fork_turns": "none",
    }
    assert value["max_calls"] == 1
    assert len(json.dumps(value, ensure_ascii=False)) <= 4000
    assert (
        "pre.protocol" in value["allowed_modes"]
        and "mid.execute" in value["allowed_modes"]
        and "future.execute" not in value["allowed_modes"]
    )
    claude = routing.intent_seed("找相关论文", runtime="claude")
    assert claude["preferred_profile"]["model"] == "sonnet"
    assert claude["preferred_profile"]["omit_claude_md"] is True


def test_seed_rejects_history_and_oversized_payloads():
    with pytest.raises(ValueError, match="hints"):
        routing.intent_seed(
            "核对协议",
            context_hint={"conversation_history": "不能复制完整对话"},
        )
    with pytest.raises(ValueError, match="concise"):
        routing.intent_seed("很长材料" * 1000)
    with pytest.raises(ValueError, match="hints"):
        routing.intent_seed("核对协议", context_hint=[])


def test_validated_route_never_authorizes_execution_or_new_sessions():
    seed = routing.intent_seed("核对协议")
    value = routing.validate_intent_result(
        json.dumps(decision(), ensure_ascii=False), seed
    )
    assert value["decision"]["mode"] == "pre.protocol"
    assert value["request_key"] == seed["request_key"]
    assert value["execution_authorized"] is False
    assert value["session_creation_authorized"] is False


@pytest.mark.parametrize(
    "patch,pattern",
    [
        ({"mode": "future.execute"}, "available mode"),
        ({"targets": ["record:invented"]}, "invent targets"),
        ({"read_only": "false"}, "booleans"),
        ({"needs_main_review": 1}, "booleans"),
        ({"reason": "长" * 161}, "concise"),
        ({"commands": ["launch-training"]}, "six routing fields"),
    ],
)
def test_subagent_cannot_expand_schema_targets_or_scope(patch, pattern):
    result = {**decision(), **patch}
    with pytest.raises(ValueError, match=pattern):
        routing.validate_intent_result(result, routing.intent_seed("核对协议"))


def test_original_read_only_constraint_wins_over_subagent_classification():
    seed = routing.intent_seed(
        "只查看协议，不改文件。", read_only_constraint=True
    )
    with pytest.raises(ValueError, match="read-only"):
        routing.validate_intent_result({**decision(), "read_only": False}, seed)


def test_target_allowlist_and_stale_request_correlation():
    seed = routing.intent_seed(
        "核对这个协议", allowed_targets=["record:protocol-current"]
    )
    result = {**decision(), "targets": ["record:protocol-current"]}
    assert (
        routing.validate_intent_result(result, seed)["decision"]["targets"]
        == seed["allowed_targets"]
    )
    newer = routing.intent_seed("先保存交接，暂停项目。")
    with pytest.raises(ValueError, match="stale"):
        routing.validate_intent_result(result, seed, newer["request_key"])
    corrupted = deepcopy(seed)
    corrupted["read_only_constraint"] = True
    with pytest.raises(ValueError, match="stale"):
        routing.validate_intent_result(result, corrupted)
    first_project = routing.intent_seed(
        "核对协议", context_hint={"project_id": "project-a"}
    )
    other_project = routing.intent_seed(
        "核对协议", context_hint={"project_id": "project-b"}
    )
    assert first_project["request_key"] != other_project["request_key"]


def test_write_route_requires_main_review_even_when_child_omits_it():
    result = {**decision(), "read_only": False, "needs_main_review": False}
    value = routing.validate_intent_result(
        result, routing.intent_seed("修改协议")
    )
    assert value["requires_main_review"] is True
    assert value["execution_authorized"] is False


def test_generated_host_templates_parse_and_share_the_same_prompt(build_api):
    generated = build_api.agent_templates()
    codex_path = build_api.SKILL / "assets/agents/codex/rondel-router.toml"
    claude_path = build_api.SKILL / "assets/agents/claude/rondel-router.md"
    codex = tomllib.loads(generated[codex_path].decode())
    claude_text = generated[claude_path].decode()
    _, front, prompt = claude_text.split("---", 2)
    claude = yaml.safe_load(front)
    assert (
        codex["model"] == "gpt-6-luna"
        and codex["model_reasoning_effort"] == "low"
    )
    assert codex["features"]["shell_tool"] is False
    assert codex["skills"]["include_instructions"] is False
    assert claude["model"] == "sonnet" and claude["maxTurns"] == 1
    assert claude["omitClaudeMd"] is True
    assert codex["developer_instructions"].strip() == prompt.strip()
