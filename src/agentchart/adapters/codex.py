"""Compile AgentChart declarations into Codex-oriented run specs."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ohmo.harness_mvp import AgentChart, load_agent_chart


class CodexAdapterError(RuntimeError):
    """Raised when an AgentChart cannot be compiled for Codex."""


@dataclass(frozen=True)
class CodexRunSpec:
    """Codex-oriented run contract centered on repository work."""

    prompt: str | None
    model: str
    cwd: str
    sandbox: str
    approval_policy: str
    tools: dict[str, list[str]]
    knowledge_files: list[str] = field(default_factory=list)
    evals: dict[str, Any] = field(default_factory=dict)
    output_format: str = "text"
    auth_source: str = "codex_subscription"
    native: dict[str, Any] = field(default_factory=dict)

    def as_run_config(self) -> dict[str, Any]:
        return {
            "prompt": self.prompt,
            "model": self.model,
            "cwd": self.cwd,
            "sandbox": self.sandbox,
            "approval_policy": self.approval_policy,
            "tools": self.tools,
            "knowledge_files": list(self.knowledge_files),
            "evals": self.evals,
            "output_format": self.output_format,
            "auth_source": self.auth_source,
            "native": self.native,
        }


def load_codex_chart(path: str | Path) -> CodexRunSpec:
    """Load an AgentChart and compile it for Codex."""
    return compile_codex_run(load_agent_chart(path))


def compile_codex_run(chart: AgentChart) -> CodexRunSpec:
    """Compile an AgentChart into a Codex-oriented run spec."""
    _assert_codex_runtime(chart)
    extension = _codex_extension(chart)
    return CodexRunSpec(
        prompt=_compile_prompt(chart, extension),
        model=str(extension.get("model") or chart.spec.model.primary),
        cwd=chart.spec.workspace.cwd,
        sandbox=_sandbox_mode(chart.spec.workspace.isolation),
        approval_policy=_approval_policy(chart.spec.permissions.mode),
        tools={
            "allow": list(chart.spec.tools.allow),
            "deny": list(chart.spec.tools.deny),
        },
        knowledge_files=[
            *[str(item.get("path")) for item in chart.spec.prompt.files if isinstance(item, dict) and item.get("path")],
            *_list_extension(extension, "knowledge_files"),
        ],
        evals=_dict_extension(extension, "evals"),
        output_format=str(extension.get("output_format", "text")),
        auth_source=str(extension.get("auth_source", "codex_subscription")),
        native=_dict_extension(extension, "native"),
    )


def _assert_codex_runtime(chart: AgentChart) -> None:
    if chart.spec.runtimeClass.name not in {"codex", "openai-codex", "codex-cli"}:
        raise CodexAdapterError(
            "Codex adapter requires spec.runtimeClass.name to be 'codex', 'openai-codex', or 'codex-cli'."
        )


def _codex_extension(chart: AgentChart) -> dict[str, Any]:
    raw = chart.extensions.get("codex", {})
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise CodexAdapterError("extensions.codex must be an object")
    return raw


def _compile_prompt(chart: AgentChart, extension: dict[str, Any]) -> str | None:
    if isinstance(extension.get("prompt"), str):
        return extension["prompt"]
    parts: list[str] = []
    if chart.spec.prompt.system:
        parts.append(chart.spec.prompt.system.strip())
    for overlay in chart.spec.prompt.overlays:
        if isinstance(overlay, dict) and isinstance(overlay.get("content"), str):
            parts.append(overlay["content"].strip())
    prompt = "\n\n".join(part for part in parts if part)
    return prompt or None


def _sandbox_mode(isolation: str) -> str:
    if isolation in {"sandbox", "worktree", "remote"}:
        return isolation
    if isolation == "none":
        return "workspace-write"
    return "runtime-default"


def _approval_policy(mode: str) -> str:
    if mode in {"full_auto", "auto"}:
        return "never"
    if mode in {"plan", "read-only", "audit"}:
        return "on-request"
    return "on-failure"


def _list_extension(extension: dict[str, Any], key: str) -> list[Any]:
    raw = extension.get(key, [])
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise CodexAdapterError(f"extensions.codex.{key} must be a list")
    return raw


def _dict_extension(extension: dict[str, Any], key: str) -> dict[str, Any]:
    raw = extension.get(key, {})
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise CodexAdapterError(f"extensions.codex.{key} must be an object")
    return raw


__all__ = ["CodexAdapterError", "CodexRunSpec", "compile_codex_run", "load_codex_chart"]
