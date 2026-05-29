from __future__ import annotations

from pathlib import Path

import pytest

from agentchart.adapters.openclaw import OpenClawAdapterError, compile_openclaw_config
from ohmo.harness_mvp import AgentChart


def _chart(tmp_path: Path, **overrides):
    payload = {
        "apiVersion": "agentchart.dev/v0",
        "kind": "AgentChart",
        "metadata": {"name": "openclaw-smoke"},
        "spec": {
            "runtimeClass": {"name": "openclaw"},
            "model": {"primary": "kimi-k2.5", "fallbacks": ["claude"]},
            "tools": {"allow": ["read_file", "shell"], "deny": ["write_file"]},
            "permissions": {"mode": "restricted"},
            "workspace": {"cwd": str(tmp_path), "isolation": "sandbox"},
            "memory": {"enabled": True, "sources": ["memory.md"]},
            "skills": {"refs": ["research"]},
        },
        "extensions": {
            "openclaw": {
                "channels": [{"type": "telegram", "name": "dm"}],
                "sandbox": {"provider": "local"},
                "heartbeat": {"enabled": True, "intervalSeconds": 10},
                "subagents": [{"name": "worker"}],
            }
        },
    }
    payload.update(overrides)
    return AgentChart.model_validate(payload)


def test_compile_openclaw_config_maps_controller_surface(tmp_path: Path) -> None:
    spec = compile_openclaw_config(_chart(tmp_path))
    config = spec.as_config()

    assert config["name"] == "openclaw-smoke"
    assert config["model"]["primary"] == "kimi-k2.5"
    assert config["workspace"]["isolation"] == "sandbox"
    assert config["tools"] == {"allow": ["read_file", "shell"], "deny": ["write_file"], "refs": []}
    assert config["channels"] == [{"type": "telegram", "name": "dm"}]
    assert config["heartbeat"] == {"enabled": True, "intervalSeconds": 10}
    assert config["subagents"] == [{"name": "worker"}]
    assert config["event_stream"]["enabled"] is True


def test_compile_openclaw_config_rejects_wrong_runtime(tmp_path: Path) -> None:
    chart = _chart(tmp_path, spec={"runtimeClass": {"name": "codex"}})

    with pytest.raises(OpenClawAdapterError, match="runtimeClass"):
        compile_openclaw_config(chart)

