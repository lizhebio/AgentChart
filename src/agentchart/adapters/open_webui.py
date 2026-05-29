"""Compile AgentChart declarations into open-webui resource adapter specs."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ohmo.harness_mvp import AgentChart, load_agent_chart


class OpenWebUIAdapterError(RuntimeError):
    """Raised when an AgentChart cannot be compiled for open-webui."""


@dataclass(frozen=True)
class OpenWebUIResourceSpec:
    """open-webui is treated as a chat/tool/memory resource provider."""

    name: str
    base_url: str
    model: str
    chat: dict[str, Any]
    tools: dict[str, list[str]]
    functions: list[dict[str, Any]] = field(default_factory=list)
    memory: dict[str, Any] = field(default_factory=dict)
    auth: dict[str, Any] = field(default_factory=dict)
    native: dict[str, Any] = field(default_factory=dict)

    def as_resource_config(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "base_url": self.base_url,
            "model": self.model,
            "chat": self.chat,
            "tools": self.tools,
            "functions": list(self.functions),
            "memory": self.memory,
            "auth": self.auth,
            "native": self.native,
        }


def load_open_webui_chart(path: str | Path) -> OpenWebUIResourceSpec:
    """Load an AgentChart and compile it for open-webui."""
    return compile_open_webui_resource(load_agent_chart(path))


def compile_open_webui_resource(chart: AgentChart) -> OpenWebUIResourceSpec:
    """Compile an AgentChart into an open-webui resource provider config."""
    _assert_open_webui_runtime(chart)
    extension = _open_webui_extension(chart)
    return OpenWebUIResourceSpec(
        name=str(extension.get("name") or chart.metadata.name),
        base_url=str(extension.get("base_url", "http://localhost:8080")),
        model=str(extension.get("model") or chart.spec.model.primary),
        chat={
            "system_prompt": chart.spec.prompt.system,
            "overlays": list(chart.spec.prompt.overlays),
            "output_format": extension.get("output_format", "text"),
        },
        tools={"allow": list(chart.spec.tools.allow), "deny": list(chart.spec.tools.deny)},
        functions=_list_extension(extension, "functions"),
        memory={
            "enabled": chart.spec.memory.enabled,
            "scope": chart.spec.memory.scope,
            "sources": list(chart.spec.memory.sources),
            **_dict_extension(extension, "memory"),
        },
        auth=_dict_extension(extension, "auth"),
        native=_dict_extension(extension, "native"),
    )


def _assert_open_webui_runtime(chart: AgentChart) -> None:
    if chart.spec.runtimeClass.name not in {"open-webui", "open_webui"}:
        raise OpenWebUIAdapterError(
            "open-webui adapter requires spec.runtimeClass.name to be 'open-webui' or 'open_webui'."
        )


def _open_webui_extension(chart: AgentChart) -> dict[str, Any]:
    raw = chart.extensions.get("open_webui", chart.extensions.get("open-webui", {}))
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise OpenWebUIAdapterError("extensions.open_webui must be an object")
    return raw


def _list_extension(extension: dict[str, Any], key: str) -> list[Any]:
    raw = extension.get(key, [])
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise OpenWebUIAdapterError(f"extensions.open_webui.{key} must be a list")
    return raw


def _dict_extension(extension: dict[str, Any], key: str) -> dict[str, Any]:
    raw = extension.get(key, {})
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise OpenWebUIAdapterError(f"extensions.open_webui.{key} must be an object")
    return raw


__all__ = [
    "OpenWebUIAdapterError",
    "OpenWebUIResourceSpec",
    "compile_open_webui_resource",
    "load_open_webui_chart",
]
