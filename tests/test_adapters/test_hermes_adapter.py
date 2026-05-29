from __future__ import annotations

from pathlib import Path

import pytest

from agentchart.adapters.hermes import HermesAdapterError, compile_hermes_spec
from ohmo.harness_mvp import AgentChart


def _chart(tmp_path: Path, **overrides):
    spec = {
        "runtimeClass": {"name": "hermes"},
        "model": {"primary": "anthropic/claude-sonnet-4.6"},
        "tools": {"allow": ["read_file", "write_file", "shell", "web_search"]},
        "permissions": {"mode": "restricted"},
        "workspace": {"cwd": str(tmp_path / "repo"), "isolation": "worktree"},
        "session": {"checkpoint": {"enabled": True}},
        "skills": {"refs": ["research", "review"]},
        "workflow": {"maxTurns": 7},
    }
    spec.update(overrides.pop("spec", {}))
    payload = {
        "apiVersion": "agentchart.dev/v0",
        "kind": "AgentChart",
        "metadata": {"name": "hermes-smoke"},
        "spec": spec,
        "extensions": {
            "hermes": {
                "query": "Summarize this repo.",
                "provider": "anthropic",
                "skills": ["review", "citation-check"],
                "toolsets": ["safe"],
            }
        },
    }
    payload.update(overrides)
    return AgentChart.model_validate(payload)


def test_compile_hermes_spec_maps_cli_and_python_contract(tmp_path: Path) -> None:
    spec = compile_hermes_spec(_chart(tmp_path))

    assert spec.query == "Summarize this repo."
    assert spec.model == "anthropic/claude-sonnet-4.6"
    assert spec.provider == "anthropic"
    assert spec.max_turns == 7
    assert spec.enabled_toolsets == ["safe", "development", "research"]
    assert spec.skills == ["research", "review", "citation-check"]
    assert spec.worktree is True
    assert spec.checkpoints is True
    assert spec.yolo is False

    assert spec.python_kwargs() == {
        "query": "Summarize this repo.",
        "model": "anthropic/claude-sonnet-4.6",
        "max_turns": 7,
        "enabled_toolsets": "safe,development,research",
        "verbose": False,
    }
    assert spec.cli_args() == [
        "hermes",
        "chat",
        "--query",
        "Summarize this repo.",
        "--model",
        "anthropic/claude-sonnet-4.6",
        "--toolsets",
        "safe,development,research",
        "--skills",
        "research",
        "--skills",
        "review",
        "--skills",
        "citation-check",
        "--provider",
        "anthropic",
        "--quiet",
        "--worktree",
        "--checkpoints",
        "--max-turns",
        "7",
        "--source",
        "agentchart",
    ]


def test_compile_hermes_spec_can_disable_denied_toolsets(tmp_path: Path) -> None:
    chart = _chart(
        tmp_path,
        spec={"tools": {"allow": ["read_file"], "deny": ["shell", "web_search"]}},
        extensions={"hermes": {"disabled_toolsets": ["browser"]}},
    )

    spec = compile_hermes_spec(chart)

    assert spec.disabled_toolsets == ["browser", "terminal", "web"]
    assert spec.python_kwargs()["disabled_toolsets"] == "browser,terminal,web"


def test_compile_hermes_spec_yolo_for_full_auto(tmp_path: Path) -> None:
    chart = _chart(tmp_path, spec={"permissions": {"mode": "full_auto"}})

    spec = compile_hermes_spec(chart)

    assert spec.yolo is True
    assert "--yolo" in spec.cli_args()


def test_compile_hermes_spec_rejects_non_hermes_runtime(tmp_path: Path) -> None:
    chart = _chart(tmp_path, spec={"runtimeClass": {"name": "deepagents"}})

    with pytest.raises(HermesAdapterError, match="runtimeClass"):
        compile_hermes_spec(chart)


def test_compile_hermes_spec_rejects_bad_extension_shape(tmp_path: Path) -> None:
    chart = _chart(tmp_path, extensions={"hermes": []})

    with pytest.raises(HermesAdapterError, match="extensions.hermes"):
        compile_hermes_spec(chart)

