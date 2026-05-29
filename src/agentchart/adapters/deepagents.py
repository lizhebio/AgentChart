"""Compile AgentChart declarations into DeepAgents create_deep_agent inputs.

The adapter is intentionally split into two phases:

1. ``compile_deepagents_spec`` converts an AgentChart into a plain Python
   contract that is stable and easy to test without importing DeepAgents.
2. ``create_deep_agent_from_chart`` imports DeepAgents lazily and calls its
   ``create_deep_agent`` entry point when that optional dependency is available.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from ohmo.harness_mvp import AgentChart, load_agent_chart


class DeepAgentsAdapterError(RuntimeError):
    """Raised when an AgentChart cannot be compiled for DeepAgents."""


FilesystemMode = Literal["allow", "deny"]


@dataclass(frozen=True)
class DeepAgentsFilesystemPermissionSpec:
    """Serializable representation of DeepAgents FilesystemPermission."""

    operations: list[Literal["read", "write"]]
    paths: list[str]
    mode: FilesystemMode = "allow"

    def as_kwargs(self) -> dict[str, Any]:
        return {
            "operations": list(self.operations),
            "paths": list(self.paths),
            "mode": self.mode,
        }


@dataclass(frozen=True)
class DeepAgentsCreateSpec:
    """Plain create_deep_agent argument bundle."""

    model: str
    tools: list[Any] = field(default_factory=list)
    system_prompt: str | None = None
    subagents: list[dict[str, Any]] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    memory: list[str] = field(default_factory=list)
    permissions: list[DeepAgentsFilesystemPermissionSpec] = field(default_factory=list)
    backend: Any | None = None
    interrupt_on: dict[str, bool | dict[str, Any]] | None = None
    checkpointer: Any | None = None
    store: Any | None = None
    debug: bool = False
    name: str | None = None
    cache: Any | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def create_kwargs(self) -> dict[str, Any]:
        """Return kwargs that can be passed to deepagents.create_deep_agent.

        Filesystem permission dataclasses remain in serializable form here; the
        lazy builder converts them to DeepAgents' native class after import.
        """
        kwargs: dict[str, Any] = {
            "model": self.model,
            "tools": list(self.tools),
            "system_prompt": self.system_prompt,
            "subagents": list(self.subagents),
            "skills": list(self.skills),
            "memory": list(self.memory),
            "permissions": [permission.as_kwargs() for permission in self.permissions],
            "backend": self.backend,
            "interrupt_on": self.interrupt_on,
            "checkpointer": self.checkpointer,
            "store": self.store,
            "debug": self.debug,
            "name": self.name,
            "cache": self.cache,
        }
        kwargs.update(self.extra)
        return {key: value for key, value in kwargs.items() if value is not None}


_READ_TOOLS = {"read_file", "ls", "glob", "grep"}
_WRITE_TOOLS = {"write_file", "edit_file"}
_SHELL_TOOLS = {"shell", "execute"}
_LOCAL_ONLY_TOOLS = {"record_note"}
_DEEPAGENTS_BUILTIN_TOOLS = _READ_TOOLS | _WRITE_TOOLS | _SHELL_TOOLS | {"task", "write_todos"}


def load_deepagents_chart(path: str | Path) -> DeepAgentsCreateSpec:
    """Load an AgentChart and compile it for DeepAgents."""
    return compile_deepagents_spec(load_agent_chart(path))


def compile_deepagents_spec(chart: AgentChart) -> DeepAgentsCreateSpec:
    """Compile an AgentChart into DeepAgents create_deep_agent inputs."""
    _assert_deepagents_runtime(chart)
    extension = _deepagents_extension(chart)
    return DeepAgentsCreateSpec(
        model=_compile_model(chart),
        tools=_compile_tools(chart, extension),
        system_prompt=_compile_system_prompt(chart, extension),
        subagents=_list_extension(extension, "subagents"),
        skills=_compile_skills(chart, extension),
        memory=_compile_memory(chart, extension),
        permissions=_compile_filesystem_permissions(chart),
        backend=extension.get("backend"),
        interrupt_on=_compile_interrupt_on(chart, extension),
        checkpointer=extension.get("checkpointer"),
        store=extension.get("store"),
        debug=bool(chart.spec.observability.verbose or extension.get("debug", False)),
        name=extension.get("name") or chart.metadata.name,
        cache=extension.get("cache"),
        extra=_dict_extension(extension, "create_kwargs"),
    )


def create_deep_agent_from_chart(chart: AgentChart) -> Any:
    """Create a DeepAgents runnable from an AgentChart.

    DeepAgents is an optional runtime dependency. Import errors are converted to
    a clear adapter error so callers can keep the core AgentChart install light.
    """
    spec = compile_deepagents_spec(chart)
    try:
        from deepagents import create_deep_agent
        from deepagents.middleware.filesystem import FilesystemPermission
    except ImportError as exc:
        raise DeepAgentsAdapterError(
            "DeepAgents is not installed. Install the DeepAgents runtime before "
            "building a runtime agent from an AgentChart."
        ) from exc

    kwargs = spec.create_kwargs()
    kwargs["permissions"] = [
        FilesystemPermission(**permission.as_kwargs()) for permission in spec.permissions
    ]
    return create_deep_agent(**kwargs)


def _assert_deepagents_runtime(chart: AgentChart) -> None:
    runtime_name = chart.spec.runtimeClass.name
    if runtime_name not in {"deepagents", "deepagents-python"}:
        raise DeepAgentsAdapterError(
            "DeepAgents adapter requires spec.runtimeClass.name to be "
            "'deepagents' or 'deepagents-python'."
        )


def _deepagents_extension(chart: AgentChart) -> dict[str, Any]:
    raw = chart.extensions.get("deepagents", {})
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise DeepAgentsAdapterError("extensions.deepagents must be an object")
    return raw


def _compile_model(chart: AgentChart) -> str:
    model = chart.spec.model.primary
    if not model:
        raise DeepAgentsAdapterError("spec.model.primary is required for DeepAgents")
    return model


def _compile_system_prompt(chart: AgentChart, extension: dict[str, Any]) -> str | None:
    prompt_parts: list[str] = []
    if chart.spec.prompt.system:
        prompt_parts.append(chart.spec.prompt.system.strip())
    for overlay in chart.spec.prompt.overlays:
        if isinstance(overlay, dict) and isinstance(overlay.get("content"), str):
            prompt_parts.append(overlay["content"].strip())
    extension_prompt = extension.get("system_prompt")
    if isinstance(extension_prompt, str):
        prompt_parts.append(extension_prompt.strip())
    prompt = "\n\n".join(part for part in prompt_parts if part)
    return prompt or None


def _compile_tools(chart: AgentChart, extension: dict[str, Any]) -> list[Any]:
    tools = list(_list_extension(extension, "tools"))
    allow = set(chart.spec.tools.allow)
    deny = set(chart.spec.tools.deny)
    unknown_denied = sorted(deny - _DEEPAGENTS_BUILTIN_TOOLS - _LOCAL_ONLY_TOOLS)
    if unknown_denied:
        # Unknown deny entries are harmless for DeepAgents built-ins, but keeping
        # them silent makes chart policy look stricter than it really is.
        raise DeepAgentsAdapterError(f"Cannot map denied DeepAgents tools: {unknown_denied}")
    unsupported_allowed = sorted((allow - _DEEPAGENTS_BUILTIN_TOOLS) - _LOCAL_ONLY_TOOLS)
    if unsupported_allowed:
        raise DeepAgentsAdapterError(f"Cannot map allowed DeepAgents tools: {unsupported_allowed}")
    return tools


def _compile_skills(chart: AgentChart, extension: dict[str, Any]) -> list[str]:
    return _dedupe_strings([*chart.spec.skills.refs, *_list_extension(extension, "skills")])


def _compile_memory(chart: AgentChart, extension: dict[str, Any]) -> list[str]:
    memory = list(chart.spec.memory.sources if chart.spec.memory.enabled else [])
    memory.extend(_list_extension(extension, "memory"))
    return _dedupe_strings(memory)


def _compile_interrupt_on(
    chart: AgentChart,
    extension: dict[str, Any],
) -> dict[str, bool | dict[str, Any]] | None:
    raw = extension.get("interrupt_on")
    if raw is not None:
        if not isinstance(raw, dict):
            raise DeepAgentsAdapterError("extensions.deepagents.interrupt_on must be an object")
        return raw
    if chart.spec.permissions.mode in {"default", "restricted", "ask"}:
        mutating_tools = [
            tool
            for tool in ("write_file", "edit_file", "execute")
            if _tool_permitted_for_deepagents(chart, tool)
        ]
        return {tool: True for tool in mutating_tools} or None
    if chart.spec.permissions.mode in {"plan", "read-only", "audit"}:
        return {"write_file": True, "edit_file": True, "execute": True}
    return None


def _compile_filesystem_permissions(
    chart: AgentChart,
) -> list[DeepAgentsFilesystemPermissionSpec]:
    rules: list[DeepAgentsFilesystemPermissionSpec] = []
    allow = set(chart.spec.tools.allow)
    deny = set(chart.spec.tools.deny)
    workspace_path = _deepagents_workspace_path(chart)

    if allow:
        if not (allow & _READ_TOOLS):
            rules.append(DeepAgentsFilesystemPermissionSpec(["read"], ["/**"], "deny"))
        if not (allow & _WRITE_TOOLS):
            rules.append(DeepAgentsFilesystemPermissionSpec(["write"], ["/**"], "deny"))

    if deny & _READ_TOOLS:
        rules.append(DeepAgentsFilesystemPermissionSpec(["read"], ["/**"], "deny"))
    if deny & _WRITE_TOOLS:
        rules.append(DeepAgentsFilesystemPermissionSpec(["write"], ["/**"], "deny"))

    if chart.spec.permissions.mode in {"plan", "read-only", "audit"}:
        rules.append(DeepAgentsFilesystemPermissionSpec(["write"], ["/**"], "deny"))

    if chart.spec.workspace.isolation in {"sandbox", "worktree", "runtime-default"}:
        rules.append(DeepAgentsFilesystemPermissionSpec(["read", "write"], [workspace_path], "allow"))
        rules.append(DeepAgentsFilesystemPermissionSpec(["read", "write"], ["/**"], "deny"))

    for permission in chart.spec.permissions.rules:
        fs_permission = _compile_permission_rule(permission.model_dump(mode="json"))
        if fs_permission is not None:
            rules.append(fs_permission)

    return rules


def _compile_permission_rule(raw: dict[str, Any]) -> DeepAgentsFilesystemPermissionSpec | None:
    resource = raw.get("resource")
    if resource not in {"filesystem", "file", "workspace"}:
        return None
    effect = raw.get("effect")
    if effect == "ask":
        return None
    match = raw.get("match") or {}
    paths = match.get("paths") or match.get("path") or match.get("patterns") or "/**"
    if isinstance(paths, str):
        path_list = [paths]
    elif isinstance(paths, list) and all(isinstance(item, str) for item in paths):
        path_list = paths
    else:
        raise DeepAgentsAdapterError("filesystem permission paths must be a string or list of strings")
    operations = _permission_operations(raw.get("action"))
    return DeepAgentsFilesystemPermissionSpec(
        operations,
        [_normalize_deepagents_path(path) for path in path_list],
        "allow" if effect == "allow" else "deny",
    )


def _permission_operations(action: Any) -> list[Literal["read", "write"]]:
    if action in {None, "*", "all"}:
        return ["read", "write"]
    if action in {"read", "list", "search"}:
        return ["read"]
    if action in {"write", "edit", "delete"}:
        return ["write"]
    raise DeepAgentsAdapterError(f"Unsupported filesystem permission action: {action!r}")


def _deepagents_workspace_path(chart: AgentChart) -> str:
    raw = chart.spec.workspace.cwd
    if raw in {"", "."}:
        return "/**"
    path = Path(raw).expanduser()
    if path.is_absolute():
        return _normalize_deepagents_path(f"/{path.name}/**")
    return _normalize_deepagents_path(f"/{path.as_posix().strip('/')}/**")


def _normalize_deepagents_path(path: str) -> str:
    normalized = path.replace("\\", "/")
    if not normalized.startswith("/"):
        normalized = "/" + normalized
    return normalized


def _tool_permitted_for_deepagents(chart: AgentChart, tool: str) -> bool:
    allow = set(chart.spec.tools.allow)
    deny = set(chart.spec.tools.deny)
    mapped = {"execute": "shell"}.get(tool, tool)
    return mapped not in deny and (not allow or mapped in allow or tool in allow)


def _list_extension(extension: dict[str, Any], key: str) -> list[Any]:
    raw = extension.get(key, [])
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise DeepAgentsAdapterError(f"extensions.deepagents.{key} must be a list")
    return raw


def _dict_extension(extension: dict[str, Any], key: str) -> dict[str, Any]:
    raw = extension.get(key, {})
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise DeepAgentsAdapterError(f"extensions.deepagents.{key} must be an object")
    return raw


def _dedupe_strings(values: list[Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            raise DeepAgentsAdapterError("Expected a list of strings")
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


__all__ = [
    "DeepAgentsAdapterError",
    "DeepAgentsCreateSpec",
    "DeepAgentsFilesystemPermissionSpec",
    "compile_deepagents_spec",
    "create_deep_agent_from_chart",
    "load_deepagents_chart",
]
