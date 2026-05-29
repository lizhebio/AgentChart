from __future__ import annotations

from pathlib import Path

import pytest

from agentchart.adapters.claude_code import (
    ClaudeCodeAdapterError,
    compile_claude_code_definition,
)
from ohmo.harness_mvp import AgentChart


def _chart(tmp_path: Path, **overrides):
    payload = {
        "apiVersion": "agentchart.dev/v0",
        "kind": "AgentChart",
        "metadata": {"name": "claude-code-smoke"},
        "spec": {
            "runtimeClass": {"name": "claude-code"},
            "model": {"primary": "claude-sonnet"},
            "prompt": {
                "system": "You are a coding agent.",
                "files": [{"path": "CLAUDE.md"}],
                "overlays": [{"content": "Preserve prompt order."}],
            },
            "tools": {"allow": ["Read", "Edit"], "deny": ["Bash"]},
            "permissions": {"mode": "plan"},
            "workspace": {"cwd": str(tmp_path), "isolation": "worktree"},
            "memory": {"enabled": True, "sources": ["MEMORY.md"]},
            "skills": {"refs": ["review"]},
            "workflow": {"maxTurns": 5},
        },
        "extensions": {
            "claude_code": {
                "skills": ["commit"],
                "mcp_servers": {"browser": {"command": "npx"}},
            }
        },
    }
    payload.update(overrides)
    return AgentChart.model_validate(payload)


def test_compile_claude_code_definition_preserves_prompt_and_policy(tmp_path: Path) -> None:
    spec = compile_claude_code_definition(_chart(tmp_path))
    definition = spec.as_definition()

    assert definition["name"] == "claude-code-smoke"
    assert definition["model"] == "claude-sonnet"
    assert definition["permission_mode"] == "plan"
    assert definition["allowed_tools"] == ["Read", "Edit"]
    assert definition["disallowed_tools"] == ["Bash"]
    assert definition["skills"] == ["review", "commit"]
    assert definition["memory"] == ["MEMORY.md"]
    assert definition["mcp_servers"] == {"browser": {"command": "npx"}}
    assert "CLAUDE.md" in (definition["system_prompt"] or "")
    assert "Preserve prompt order." in (definition["system_prompt"] or "")


def test_compile_claude_code_definition_rejects_wrong_runtime(tmp_path: Path) -> None:
    chart = _chart(tmp_path, spec={"runtimeClass": {"name": "openclaw"}})

    with pytest.raises(ClaudeCodeAdapterError, match="runtimeClass"):
        compile_claude_code_definition(chart)

