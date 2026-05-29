"""Compile AgentChart declarations into OpenClaw-style agent config."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ohmo.harness_mvp import AgentChart, load_agent_chart


class OpenClawAdapterError(RuntimeError):
    """Raised when an AgentChart cannot be compiled for OpenClaw."""


@dataclass(frozen=True)
class OpenClawAgentConfigSpec:
    """Serializable OpenClaw-oriented configuration contract."""

    name: str
    model: dict[str, Any]
    workspace: dict[str, Any]
    tools: dict[str, list[str]]
    permissions: dict[str, Any]
    session: dict[str, Any]
    memory: dict[str, Any]
    skills: list[str] = field(default_factory=list)
    channels: list[dict[str, Any]] = field(default_factory=list)
    sandbox: dict[str, Any] = field(default_factory=dict)
    heartbeat: dict[str, Any] = field(default_factory=dict)
    subagents: list[dict[str, Any]] = field(default_factory=list)
    event_stream: dict[str, Any] = field(default_factory=dict)
    extensions: dict[str, Any] = field(default_factory=dict)

    def as_config(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "model": self.model,
            "workspace": self.workspace,
            "tools": self.tools,
            "permissions": self.permissions,
            "session": self.session,
            "memory": self.memory,
            "skills": list(self.skills),
            "channels": list(self.channels),
            "sandbox": self.sandbox,
            "heartbeat": self.heartbeat,
            "subagents": list(self.subagents),
            "event_stream": self.event_stream,
            "extensions": self.extensions,
        }


def load_openclaw_chart(path: str | Path) -> OpenClawAgentConfigSpec:
    """Load an AgentChart and compile it for OpenClaw."""
    return compile_openclaw_config(load_agent_chart(path))


def compile_openclaw_config(chart: AgentChart) -> OpenClawAgentConfigSpec:
    """Compile an AgentChart into an OpenClaw-style config object."""
    _assert_openclaw_runtime(chart)
    extension = _openclaw_extension(chart)
    return OpenClawAgentConfigSpec(
        name=str(extension.get("name") or chart.metadata.name),
        model={
            "primary": chart.spec.model.primary,
            "fallbacks": list(chart.spec.model.fallbacks),
            "params": dict(chart.spec.model.params),
        },
        workspace={
            "cwd": chart.spec.workspace.cwd,
            "isolation": chart.spec.workspace.isolation,
        },
        tools={
            "allow": list(chart.spec.tools.allow),
            "deny": list(chart.spec.tools.deny),
            "refs": list(chart.spec.tools.refs),
        },
        permissions={
            "mode": chart.spec.permissions.mode,
            "rules": [rule.model_dump(mode="json") for rule in chart.spec.permissions.rules],
            "approval": dict(chart.spec.permissions.approval),
        },
        session={
            "persistence": chart.spec.session.persistence,
            "resume": chart.spec.session.resume,
            "checkpoint": dict(chart.spec.session.checkpoint),
            "compaction": dict(chart.spec.session.compaction),
        },
        memory={
            "enabled": chart.spec.memory.enabled,
            "scope": chart.spec.memory.scope,
            "sources": list(chart.spec.memory.sources),
        },
        skills=[*chart.spec.skills.refs, *_list_extension(extension, "skills")],
        channels=_list_extension(extension, "channels"),
        sandbox=_dict_extension(extension, "sandbox"),
        heartbeat=_dict_extension(extension, "heartbeat", default={"enabled": True}),
        subagents=_list_extension(extension, "subagents"),
        event_stream=_dict_extension(
            extension,
            "event_stream",
            default={"enabled": True, "events": list(chart.spec.observability.events)},
        ),
        extensions=_dict_extension(extension, "native"),
    )


def _assert_openclaw_runtime(chart: AgentChart) -> None:
    if chart.spec.runtimeClass.name not in {"openclaw", "openclaw-agent"}:
        raise OpenClawAdapterError(
            "OpenClaw adapter requires spec.runtimeClass.name to be 'openclaw' or 'openclaw-agent'."
        )


def _openclaw_extension(chart: AgentChart) -> dict[str, Any]:
    raw = chart.extensions.get("openclaw", {})
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise OpenClawAdapterError("extensions.openclaw must be an object")
    return raw


def _list_extension(extension: dict[str, Any], key: str) -> list[Any]:
    raw = extension.get(key, [])
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise OpenClawAdapterError(f"extensions.openclaw.{key} must be a list")
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
        raise OpenClawAdapterError(f"extensions.openclaw.{key} must be an object")
    return raw


__all__ = ["OpenClawAdapterError", "OpenClawAgentConfigSpec", "compile_openclaw_config", "load_openclaw_chart"]
