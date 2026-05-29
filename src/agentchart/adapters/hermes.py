"""Compile AgentChart declarations into Hermes Agent invocations."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ohmo.harness_mvp import AgentChart, load_agent_chart


class HermesAdapterError(RuntimeError):
    """Raised when an AgentChart cannot be compiled for Hermes."""


@dataclass(frozen=True)
class HermesRunSpec:
    """Hermes CLI and Python-call contract derived from an AgentChart."""

    query: str | None = None
    model: str = ""
    api_key: str | None = None
    base_url: str = ""
    max_turns: int = 10
    enabled_toolsets: list[str] = field(default_factory=list)
    disabled_toolsets: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    provider: str | None = None
    quiet: bool = True
    verbose: bool = False
    worktree: bool = False
    yolo: bool = False
    checkpoints: bool = False
    resume: str | None = None
    continue_session: str | bool | None = None
    source: str = "agentchart"
    extra_cli_args: list[str] = field(default_factory=list)

    def enabled_toolsets_csv(self) -> str | None:
        return ",".join(self.enabled_toolsets) if self.enabled_toolsets else None

    def disabled_toolsets_csv(self) -> str | None:
        return ",".join(self.disabled_toolsets) if self.disabled_toolsets else None

    def python_kwargs(self) -> dict[str, Any]:
        """Return kwargs for ``run_agent.main(...)``."""
        kwargs: dict[str, Any] = {
            "query": self.query,
            "model": self.model,
            "api_key": self.api_key,
            "base_url": self.base_url,
            "max_turns": self.max_turns,
            "enabled_toolsets": self.enabled_toolsets_csv(),
            "disabled_toolsets": self.disabled_toolsets_csv(),
            "verbose": self.verbose,
        }
        return {key: value for key, value in kwargs.items() if value not in {None, ""}}

    def cli_args(self, executable: str = "hermes") -> list[str]:
        """Return argv for ``hermes chat`` without executing it."""
        args = [executable, "chat"]
        if self.query:
            args.extend(["--query", self.query])
        if self.model:
            args.extend(["--model", self.model])
        if self.enabled_toolsets:
            args.extend(["--toolsets", ",".join(self.enabled_toolsets)])
        for skill in self.skills:
            args.extend(["--skills", skill])
        if self.provider:
            args.extend(["--provider", self.provider])
        if self.quiet:
            args.append("--quiet")
        if self.verbose:
            args.append("--verbose")
        if self.worktree:
            args.append("--worktree")
        if self.yolo:
            args.append("--yolo")
        if self.checkpoints:
            args.append("--checkpoints")
        if self.resume:
            args.extend(["--resume", self.resume])
        if self.continue_session is True:
            args.append("--continue")
        elif isinstance(self.continue_session, str):
            args.extend(["--continue", self.continue_session])
        if self.max_turns:
            args.extend(["--max-turns", str(self.max_turns)])
        if self.source:
            args.extend(["--source", self.source])
        args.extend(self.extra_cli_args)
        return args


_HERMES_TOOLSET_ALIASES: dict[str, str] = {
    "read_file": "development",
    "write_file": "development",
    "shell": "development",
    "terminal": "development",
    "web_search": "research",
    "web_extract": "research",
    "browser": "browser",
    "mcp": "mcp",
    "memory": "memory",
    "vision": "vision",
}


def load_hermes_chart(path: str | Path) -> HermesRunSpec:
    """Load an AgentChart and compile it for Hermes."""
    return compile_hermes_spec(load_agent_chart(path))


def compile_hermes_spec(chart: AgentChart) -> HermesRunSpec:
    """Compile an AgentChart into a Hermes invocation contract."""
    _assert_hermes_runtime(chart)
    extension = _hermes_extension(chart)
    enabled_toolsets = _compile_toolsets(chart, extension)
    disabled_toolsets = _compile_disabled_toolsets(chart, extension)
    return HermesRunSpec(
        query=_compile_query(chart, extension),
        model=extension.get("model") or chart.spec.model.primary,
        api_key=extension.get("api_key"),
        base_url=extension.get("base_url", ""),
        max_turns=int(extension.get("max_turns") or chart.spec.workflow.maxTurns or 10),
        enabled_toolsets=enabled_toolsets,
        disabled_toolsets=disabled_toolsets,
        skills=_compile_skills(chart, extension),
        provider=extension.get("provider"),
        quiet=bool(extension.get("quiet", True)),
        verbose=bool(extension.get("verbose", chart.spec.observability.verbose)),
        worktree=chart.spec.workspace.isolation == "worktree" or bool(extension.get("worktree", False)),
        yolo=_compile_yolo(chart, extension),
        checkpoints=bool(
            extension.get(
                "checkpoints",
                chart.spec.session.checkpoint.get("enabled", False),
            )
        ),
        resume=extension.get("resume"),
        continue_session=extension.get("continue_session"),
        source=extension.get("source", "agentchart"),
        extra_cli_args=_list_extension(extension, "extra_cli_args"),
    )


def run_hermes_from_chart(chart: AgentChart) -> Any:
    """Run Hermes via its Python entry point using a compiled AgentChart."""
    spec = compile_hermes_spec(chart)
    try:
        import run_agent
    except ImportError as exc:
        raise HermesAdapterError(
            "Hermes is not importable. Install hermes-agent or make its source "
            "available on PYTHONPATH before running this adapter."
        ) from exc
    return run_agent.main(**spec.python_kwargs())


def _assert_hermes_runtime(chart: AgentChart) -> None:
    runtime_name = chart.spec.runtimeClass.name
    if runtime_name not in {"hermes", "hermes-agent"}:
        raise HermesAdapterError(
            "Hermes adapter requires spec.runtimeClass.name to be 'hermes' or 'hermes-agent'."
        )


def _hermes_extension(chart: AgentChart) -> dict[str, Any]:
    raw = chart.extensions.get("hermes", {})
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise HermesAdapterError("extensions.hermes must be an object")
    return raw


def _compile_query(chart: AgentChart, extension: dict[str, Any]) -> str | None:
    query = extension.get("query")
    if query is not None and not isinstance(query, str):
        raise HermesAdapterError("extensions.hermes.query must be a string")
    return query


def _compile_toolsets(chart: AgentChart, extension: dict[str, Any]) -> list[str]:
    explicit = _list_extension(extension, "toolsets")
    inferred: list[str] = []
    for tool in chart.spec.tools.allow:
        alias = _HERMES_TOOLSET_ALIASES.get(tool)
        if alias and alias not in inferred:
            inferred.append(alias)
    return _dedupe_strings([*explicit, *inferred])


def _compile_disabled_toolsets(chart: AgentChart, extension: dict[str, Any]) -> list[str]:
    disabled = list(_list_extension(extension, "disabled_toolsets"))
    denied = set(chart.spec.tools.deny)
    if denied & {"shell", "terminal"}:
        disabled.append("terminal")
    if denied & {"web_search", "web_extract", "browser"}:
        disabled.append("web")
    return _dedupe_strings(disabled)


def _compile_skills(chart: AgentChart, extension: dict[str, Any]) -> list[str]:
    return _dedupe_strings([*chart.spec.skills.refs, *_list_extension(extension, "skills")])


def _compile_yolo(chart: AgentChart, extension: dict[str, Any]) -> bool:
    if "yolo" in extension:
        return bool(extension["yolo"])
    return chart.spec.permissions.mode in {"full_auto", "auto"}


def _list_extension(extension: dict[str, Any], key: str) -> list[Any]:
    raw = extension.get(key, [])
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise HermesAdapterError(f"extensions.hermes.{key} must be a list")
    return raw


def _dedupe_strings(values: list[Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            raise HermesAdapterError("Expected a list of strings")
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


__all__ = [
    "HermesAdapterError",
    "HermesRunSpec",
    "compile_hermes_spec",
    "load_hermes_chart",
    "run_hermes_from_chart",
]
