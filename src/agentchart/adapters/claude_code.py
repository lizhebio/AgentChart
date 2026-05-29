"""Compile AgentChart declarations into Claude Code-style agent definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ohmo.harness_mvp import AgentChart, load_agent_chart


class ClaudeCodeAdapterError(RuntimeError):
    """Raised when an AgentChart cannot be compiled for Claude Code."""


@dataclass(frozen=True)
class ClaudeCodeAgentDefinitionSpec:
    """Serializable Claude Code-oriented agent definition contract."""

    name: str
    model: str
    system_prompt: str | None
    allowed_tools: list[str] = field(default_factory=list)
    disallowed_tools: list[str] = field(default_factory=list)
    permission_mode: str = "default"
    cwd: str = "."
    isolation: str = "runtime-default"
    skills: list[str] = field(default_factory=list)
    memory: list[str] = field(default_factory=list)
    mcp_servers: dict[str, Any] = field(default_factory=dict)
    max_turns: int | None = None
    sidechain: dict[str, Any] = field(default_factory=dict)
    native: dict[str, Any] = field(default_factory=dict)

    def as_definition(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "model": self.model,
            "system_prompt": self.system_prompt,
            "allowed_tools": list(self.allowed_tools),
            "disallowed_tools": list(self.disallowed_tools),
            "permission_mode": self.permission_mode,
            "cwd": self.cwd,
            "isolation": self.isolation,
            "skills": list(self.skills),
            "memory": list(self.memory),
            "mcp_servers": self.mcp_servers,
            "max_turns": self.max_turns,
            "sidechain": self.sidechain,
            "native": self.native,
        }


def load_claude_code_chart(path: str | Path) -> ClaudeCodeAgentDefinitionSpec:
    """Load an AgentChart and compile it for Claude Code."""
    return compile_claude_code_definition(load_agent_chart(path))


def compile_claude_code_definition(chart: AgentChart) -> ClaudeCodeAgentDefinitionSpec:
    """Compile an AgentChart into a Claude Code-style agent definition."""
    _assert_claude_runtime(chart)
    extension = _claude_extension(chart)
    return ClaudeCodeAgentDefinitionSpec(
        name=str(extension.get("name") or chart.metadata.name),
        model=str(extension.get("model") or chart.spec.model.primary),
        system_prompt=_compile_system_prompt(chart, extension),
        allowed_tools=list(chart.spec.tools.allow),
        disallowed_tools=list(chart.spec.tools.deny),
        permission_mode=_permission_mode(chart.spec.permissions.mode),
        cwd=chart.spec.workspace.cwd,
        isolation=chart.spec.workspace.isolation,
        skills=[*chart.spec.skills.refs, *_list_extension(extension, "skills")],
        memory=list(chart.spec.memory.sources if chart.spec.memory.enabled else []),
        mcp_servers=_dict_extension(extension, "mcp_servers"),
        max_turns=chart.spec.workflow.maxTurns,
        sidechain=_dict_extension(extension, "sidechain", default={"transcript": True}),
        native=_dict_extension(extension, "native"),
    )


def _assert_claude_runtime(chart: AgentChart) -> None:
    if chart.spec.runtimeClass.name not in {"claude-code", "claude_code", "claude"}:
        raise ClaudeCodeAdapterError(
            "Claude Code adapter requires spec.runtimeClass.name to be 'claude-code', 'claude_code', or 'claude'."
        )


def _claude_extension(chart: AgentChart) -> dict[str, Any]:
    raw = chart.extensions.get("claude_code", chart.extensions.get("claude", {}))
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ClaudeCodeAdapterError("extensions.claude_code must be an object")
    return raw


def _compile_system_prompt(chart: AgentChart, extension: dict[str, Any]) -> str | None:
    parts: list[str] = []
    if chart.spec.prompt.system:
        parts.append(chart.spec.prompt.system.strip())
    for file_ref in chart.spec.prompt.files:
        if isinstance(file_ref, dict) and isinstance(file_ref.get("path"), str):
            parts.append(f"Include prompt file: {file_ref['path']}")
    for overlay in chart.spec.prompt.overlays:
        if isinstance(overlay, dict) and isinstance(overlay.get("content"), str):
            parts.append(overlay["content"].strip())
    if isinstance(extension.get("system_prompt"), str):
        parts.append(extension["system_prompt"].strip())
    prompt = "\n\n".join(part for part in parts if part)
    return prompt or None


def _permission_mode(mode: str) -> str:
    mapping = {
        "restricted": "default",
        "default": "default",
        "plan": "plan",
        "read-only": "plan",
        "audit": "plan",
        "full_auto": "acceptEdits",
        "auto": "acceptEdits",
    }
    return mapping.get(mode, mode)


def _list_extension(extension: dict[str, Any], key: str) -> list[Any]:
    raw = extension.get(key, [])
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ClaudeCodeAdapterError(f"extensions.claude_code.{key} must be a list")
    return raw


def _dict_extension(
    extension: dict[str, Any],
    key: str,
    *,
    default: dict[str, Any] | None = None,
) -> dict[str, Any]:
    raw = extension.get(key, default or {})
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ClaudeCodeAdapterError(f"extensions.claude_code.{key} must be an object")
    return raw


__all__ = [
    "ClaudeCodeAdapterError",
    "ClaudeCodeAgentDefinitionSpec",
    "compile_claude_code_definition",
    "load_claude_code_chart",
]
