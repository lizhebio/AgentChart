from __future__ import annotations

from pathlib import Path

import pytest

from agentchart.adapters.codex import CodexAdapterError, compile_codex_run
from ohmo.harness_mvp import AgentChart


def _chart(tmp_path: Path, **overrides):
    payload = {
        "apiVersion": "agentchart.dev/v0",
        "kind": "AgentChart",
        "metadata": {"name": "codex-smoke"},
        "spec": {
            "runtimeClass": {"name": "codex"},
            "model": {"primary": "gpt-5.5-codex"},
            "prompt": {
                "system": "Review this repository.",
                "files": [{"path": "AGENTS.md"}],
            },
            "tools": {"allow": ["shell", "read_file"], "deny": ["web_search"]},
            "permissions": {"mode": "restricted"},
            "workspace": {"cwd": str(tmp_path), "isolation": "sandbox"},
        },
        "extensions": {"codex": {"knowledge_files": ["README.md"], "evals": {"run_tests": True}}},
    }
    payload.update(overrides)
    return AgentChart.model_validate(payload)


def test_compile_codex_run_maps_repo_workflow_fields(tmp_path: Path) -> None:
    spec = compile_codex_run(_chart(tmp_path))
    config = spec.as_run_config()

    assert config["model"] == "gpt-5.5-codex"
    assert config["cwd"] == str(tmp_path)
    assert config["sandbox"] == "sandbox"
    assert config["approval_policy"] == "on-failure"
    assert config["tools"] == {"allow": ["shell", "read_file"], "deny": ["web_search"]}
    assert config["knowledge_files"] == ["AGENTS.md", "README.md"]
    assert config["evals"] == {"run_tests": True}


def test_compile_codex_run_rejects_wrong_runtime(tmp_path: Path) -> None:
    chart = _chart(tmp_path, spec={"runtimeClass": {"name": "hermes"}})

    with pytest.raises(CodexAdapterError, match="runtimeClass"):
        compile_codex_run(chart)

