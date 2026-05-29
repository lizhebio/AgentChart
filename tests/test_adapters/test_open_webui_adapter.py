from __future__ import annotations

from pathlib import Path

import pytest

from agentchart.adapters.open_webui import OpenWebUIAdapterError, compile_open_webui_resource
from ohmo.harness_mvp import AgentChart


def _chart(tmp_path: Path, **overrides):
    payload = {
        "apiVersion": "agentchart.dev/v0",
        "kind": "AgentChart",
        "metadata": {"name": "open-webui-smoke"},
        "spec": {
            "runtimeClass": {"name": "open-webui"},
            "model": {"primary": "qwen3"},
            "prompt": {"system": "Use open-webui as a resource provider."},
            "tools": {"allow": ["web_search"], "deny": ["shell"]},
            "permissions": {"mode": "restricted"},
            "workspace": {"cwd": str(tmp_path), "isolation": "none"},
            "memory": {"enabled": True, "scope": "user", "sources": ["user-memory"]},
        },
        "extensions": {
            "open_webui": {
                "base_url": "http://localhost:3000",
                "functions": [{"name": "lookup"}],
                "auth": {"type": "bearer"},
            }
        },
    }
    payload.update(overrides)
    return AgentChart.model_validate(payload)


def test_compile_open_webui_resource_maps_platform_surface(tmp_path: Path) -> None:
    spec = compile_open_webui_resource(_chart(tmp_path))
    config = spec.as_resource_config()

    assert config["name"] == "open-webui-smoke"
    assert config["base_url"] == "http://localhost:3000"
    assert config["model"] == "qwen3"
    assert config["tools"] == {"allow": ["web_search"], "deny": ["shell"]}
    assert config["functions"] == [{"name": "lookup"}]
    assert config["memory"]["enabled"] is True
    assert config["memory"]["scope"] == "user"
    assert config["auth"] == {"type": "bearer"}


def test_compile_open_webui_resource_rejects_wrong_runtime(tmp_path: Path) -> None:
    chart = _chart(tmp_path, spec={"runtimeClass": {"name": "deepagents"}})

    with pytest.raises(OpenWebUIAdapterError, match="runtimeClass"):
        compile_open_webui_resource(chart)

