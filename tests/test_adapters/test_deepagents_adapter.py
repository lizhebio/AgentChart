from __future__ import annotations

from pathlib import Path

import pytest

from agentchart.adapters.deepagents import (
    DeepAgentsAdapterError,
    compile_deepagents_spec,
)
from ohmo.harness_mvp import AgentChart


def _chart(tmp_path: Path, **overrides):
    spec = {
        "runtimeClass": {"name": "deepagents"},
        "model": {"primary": "anthropic:claude-sonnet-4-5"},
        "prompt": {
            "system": "You are Hermes.",
            "overlays": [{"content": "Prefer concise status updates."}],
        },
        "tools": {"allow": ["read_file", "write_file", "shell"]},
        "permissions": {"mode": "restricted"},
        "workspace": {"cwd": str(tmp_path / "workspace"), "isolation": "sandbox"},
        "memory": {"enabled": True, "sources": ["memory/hermes.md"]},
        "skills": {"refs": ["research", "review"]},
    }
    spec.update(overrides.pop("spec", {}))
    payload = {
        "apiVersion": "agentchart.dev/v0",
        "kind": "AgentChart",
        "metadata": {"name": "hermes"},
        "spec": spec,
        "extensions": {
            "deepagents": {
                "skills": ["review", "citation-check"],
                "memory": ["memory/project.md"],
                "subagents": [{"name": "critic", "description": "Review outputs"}],
                "create_kwargs": {"debug": False},
            }
        },
    }
    payload.update(overrides)
    return AgentChart.model_validate(payload)


def test_compile_deepagents_spec_maps_core_chart_fields(tmp_path: Path) -> None:
    spec = compile_deepagents_spec(_chart(tmp_path))

    assert spec.model == "anthropic:claude-sonnet-4-5"
    assert spec.name == "hermes"
    assert spec.tools == []
    assert spec.skills == ["research", "review", "citation-check"]
    assert spec.memory == ["memory/hermes.md", "memory/project.md"]
    assert spec.subagents == [{"name": "critic", "description": "Review outputs"}]
    assert spec.interrupt_on == {"write_file": True, "execute": True}
    assert spec.system_prompt == "You are Hermes.\n\nPrefer concise status updates."
    assert any(permission.mode == "allow" for permission in spec.permissions)
    assert any(permission.mode == "deny" for permission in spec.permissions)


def test_compile_deepagents_spec_uses_explicit_interrupt_policy(tmp_path: Path) -> None:
    chart = _chart(
        tmp_path,
        extensions={"deepagents": {"interrupt_on": {"write_file": {"allowed_decisions": ["approve"]}}}},
    )

    spec = compile_deepagents_spec(chart)

    assert spec.interrupt_on == {"write_file": {"allowed_decisions": ["approve"]}}


def test_compile_deepagents_spec_denies_writes_in_plan_mode(tmp_path: Path) -> None:
    chart = _chart(
        tmp_path,
        spec={
            "permissions": {"mode": "plan"},
            "workspace": {"cwd": str(tmp_path / "workspace"), "isolation": "none"},
        },
        extensions={"deepagents": {}},
    )

    spec = compile_deepagents_spec(chart)

    assert {"operations": ["write"], "paths": ["/**"], "mode": "deny"} in [
        permission.as_kwargs() for permission in spec.permissions
    ]
    assert spec.interrupt_on == {"write_file": True, "edit_file": True, "execute": True}


def test_compile_deepagents_spec_rejects_non_deepagents_runtime(tmp_path: Path) -> None:
    chart = _chart(tmp_path, spec={"runtimeClass": {"name": "mvp-local"}})

    with pytest.raises(DeepAgentsAdapterError, match="runtimeClass"):
        compile_deepagents_spec(chart)


def test_compile_deepagents_spec_rejects_unmapped_tools(tmp_path: Path) -> None:
    chart = _chart(tmp_path, spec={"tools": {"allow": ["read_file", "unknown_tool"]}})

    with pytest.raises(DeepAgentsAdapterError, match="Cannot map allowed"):
        compile_deepagents_spec(chart)

