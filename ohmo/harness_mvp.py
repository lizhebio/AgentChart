"""High-availability minimum viable agent harness.

This module intentionally keeps the first runtime local and deterministic.  It
proves the harness substrate before binding to a model runtime: AgentChart
loading, policy admission, durable run state, append-only event logs, retries,
heartbeats, checkpoints, and resumable step execution.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Literal
from uuid import uuid4

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator


RunStatus = Literal[
    "created",
    "running",
    "pending_approval",
    "completed",
    "failed",
    "cancelled",
    "recovered",
]


class HarnessMvpError(RuntimeError):
    """Base exception for the MVP harness."""


class PolicyDenied(HarnessMvpError):
    """Raised when a chart or tool action violates policy."""


class ChartDiagnostic(BaseModel):
    level: Literal["error", "warning"]
    field: str
    message: str


class RuntimeClass(BaseModel):
    name: str = "mvp-local"
    version: str | None = None


class ModelSpec(BaseModel):
    primary: str = "local-deterministic"
    fallbacks: list[str] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)


class PromptSpec(BaseModel):
    system: str | None = None
    files: list[dict[str, Any]] = Field(default_factory=list)
    overlays: list[dict[str, Any]] = Field(default_factory=list)


class ToolSpec(BaseModel):
    refs: list[str] = Field(default_factory=list)
    allow: list[str] = Field(default_factory=list)
    deny: list[str] = Field(default_factory=list)


class PermissionRule(BaseModel):
    resource: str
    action: str | None = None
    effect: Literal["allow", "deny", "ask"]
    match: dict[str, Any] = Field(default_factory=dict)


class PermissionSpec(BaseModel):
    mode: str = "restricted"
    rules: list[PermissionRule] = Field(default_factory=list)
    approval: dict[str, Any] = Field(default_factory=dict)


class WorkspaceSpec(BaseModel):
    cwd: str = "."
    isolation: Literal["none", "worktree", "sandbox", "remote", "runtime-default"] = "sandbox"


class SessionSpec(BaseModel):
    persistence: Literal["none", "runtime", "external"] = "runtime"
    resume: bool = True
    checkpoint: dict[str, Any] = Field(default_factory=lambda: {"enabled": True, "maxSnapshots": 20})
    compaction: dict[str, Any] = Field(default_factory=dict)


class MemorySpec(BaseModel):
    enabled: bool = False
    scope: str = "session"
    sources: list[str] = Field(default_factory=list)


class SkillSpec(BaseModel):
    refs: list[str] = Field(default_factory=list)


class WorkflowRetrySpec(BaseModel):
    maxAttempts: int = 2
    on: list[str] = Field(default_factory=lambda: ["tool_error", "timeout"])
    backoffSeconds: float = 0.2

    @field_validator("maxAttempts")
    @classmethod
    def _positive_attempts(cls, value: int) -> int:
        if value < 1:
            raise ValueError("maxAttempts must be >= 1")
        return value


class WorkflowStep(BaseModel):
    id: str
    tool: Literal["read_file", "write_file", "shell", "record_note"]
    args: dict[str, Any] = Field(default_factory=dict)
    mutates: bool = False
    timeoutSeconds: int | None = None

    @field_validator("id")
    @classmethod
    def _valid_step_id(cls, value: str) -> str:
        if not value or any(ch.isspace() for ch in value):
            raise ValueError("step id must be non-empty and contain no whitespace")
        return value


class WorkflowSpec(BaseModel):
    maxTurns: int | None = None
    retries: WorkflowRetrySpec = Field(default_factory=WorkflowRetrySpec)
    timeoutSeconds: int | None = 120
    steps: list[WorkflowStep] = Field(default_factory=list)


class ObservabilitySpec(BaseModel):
    events: list[str] = Field(default_factory=lambda: ["lifecycle", "tool", "checkpoint", "error"])
    traces: bool = True
    verbose: bool = False


class AgentChartSpec(BaseModel):
    runtimeClass: RuntimeClass = Field(default_factory=RuntimeClass)
    model: ModelSpec = Field(default_factory=ModelSpec)
    prompt: PromptSpec = Field(default_factory=PromptSpec)
    tools: ToolSpec = Field(default_factory=ToolSpec)
    permissions: PermissionSpec = Field(default_factory=PermissionSpec)
    workspace: WorkspaceSpec = Field(default_factory=WorkspaceSpec)
    session: SessionSpec = Field(default_factory=SessionSpec)
    memory: MemorySpec = Field(default_factory=MemorySpec)
    skills: SkillSpec = Field(default_factory=SkillSpec)
    workflow: WorkflowSpec = Field(default_factory=WorkflowSpec)
    observability: ObservabilitySpec = Field(default_factory=ObservabilitySpec)


class AgentChartMetadata(BaseModel):
    name: str
    description: str | None = None
    labels: dict[str, str] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def _safe_name(cls, value: str) -> str:
        if not value or not all(ch.isalnum() or ch in "-_" for ch in value):
            raise ValueError("metadata.name may contain only letters, numbers, '-' and '_'")
        return value


class AgentChart(BaseModel):
    apiVersion: str = "agentchart.dev/v0"
    kind: Literal["AgentChart"] = "AgentChart"
    metadata: AgentChartMetadata
    spec: AgentChartSpec = Field(default_factory=AgentChartSpec)
    extensions: dict[str, Any] = Field(default_factory=dict)


class RunState(BaseModel):
    run_id: str
    chart_name: str
    chart_hash: str
    workspace: str
    status: RunStatus = "created"
    current_step: str | None = None
    completed_steps: list[str] = Field(default_factory=list)
    failed_step: str | None = None
    error: str | None = None
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    heartbeat_at: float | None = None
    attempts: dict[str, int] = Field(default_factory=dict)


def load_agent_chart(path: str | Path) -> AgentChart:
    """Load an AgentChart from YAML or JSON."""
    chart_path = Path(path)
    data = yaml.safe_load(chart_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise HarnessMvpError(f"AgentChart must be an object: {chart_path}")
    try:
        return AgentChart.model_validate(data)
    except ValidationError as exc:
        raise HarnessMvpError(str(exc)) from exc


def chart_hash(chart: AgentChart) -> str:
    """Return a stable short content hash for a chart."""
    import hashlib

    raw = json.dumps(chart.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=str(path.parent),
        prefix=f".{path.name}.",
        delete=False,
    ) as tmp:
        tmp.write(encoded)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp_path = Path(tmp.name)
    os.replace(tmp_path, path)


class DurableRunStore:
    """Append-only run storage with atomic state updates and simple locks."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()
        self.runs_dir = self.root / "runs"
        self.runs_dir.mkdir(parents=True, exist_ok=True)

    def run_dir(self, run_id: str) -> Path:
        return self.runs_dir / run_id

    def create_run(self, chart: AgentChart, workspace: Path) -> RunState:
        run_id = f"run-{int(time.time())}-{uuid4().hex[:8]}"
        run = RunState(
            run_id=run_id,
            chart_name=chart.metadata.name,
            chart_hash=chart_hash(chart),
            workspace=str(workspace),
        )
        run_path = self.run_dir(run_id)
        (run_path / "checkpoints").mkdir(parents=True, exist_ok=False)
        self.save_state(run)
        self.append_event(run_id, "lifecycle", {"status": "created"})
        return run

    def latest_run_id(self) -> str | None:
        latest = self.root / "latest-run"
        if not latest.exists():
            return None
        value = latest.read_text(encoding="utf-8").strip()
        return value or None

    def mark_latest(self, run_id: str) -> None:
        path = self.root / "latest-run"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(run_id + "\n", encoding="utf-8")

    def state_path(self, run_id: str) -> Path:
        return self.run_dir(run_id) / "run.json"

    def save_state(self, state: RunState) -> None:
        state.updated_at = time.time()
        _atomic_write_json(self.state_path(state.run_id), state.model_dump(mode="json"))

    def load_state(self, run_id: str) -> RunState:
        path = self.state_path(run_id)
        if not path.exists():
            raise HarnessMvpError(f"Run not found: {run_id}")
        return RunState.model_validate_json(path.read_text(encoding="utf-8"))

    def append_event(self, run_id: str, event_type: str, payload: dict[str, Any]) -> None:
        path = self.run_dir(run_id) / "events.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        event = {
            "time": time.time(),
            "run_id": run_id,
            "type": event_type,
            "payload": payload,
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    @contextmanager
    def lock(self, run_id: str, *, stale_after_seconds: int = 300) -> Iterator[None]:
        lock_path = self.run_dir(run_id) / ".lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        while True:
            try:
                fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, f"{os.getpid()} {time.time()}\n".encode("utf-8"))
                os.close(fd)
                break
            except FileExistsError:
                try:
                    age = time.time() - lock_path.stat().st_mtime
                except FileNotFoundError:
                    continue
                if age > stale_after_seconds:
                    lock_path.unlink(missing_ok=True)
                    continue
                raise HarnessMvpError(f"Run is locked by another process: {run_id}")
        try:
            yield
        finally:
            lock_path.unlink(missing_ok=True)


class HarnessPolicy:
    """Small conservative admission controller for local tools."""

    dangerous_fragments = (
        "rm -rf /",
        "rm -rf .",
        "sudo ",
        "mkfs",
        ":(){",
        "shutdown",
        "reboot",
        "dd if=",
        "> /dev/",
    )

    def __init__(self, workspace: Path, chart: AgentChart) -> None:
        self.workspace = workspace.resolve()
        self.chart = chart

    def validate_chart(self) -> list[ChartDiagnostic]:
        diagnostics: list[ChartDiagnostic] = []
        runtime = self.chart.spec.runtimeClass.name
        if runtime != "mvp-local":
            diagnostics.append(
                ChartDiagnostic(
                    level="error",
                    field="spec.runtimeClass.name",
                    message="MVP runner supports only runtimeClass.name=mvp-local",
                )
            )
        if not self.chart.spec.workflow.steps:
            diagnostics.append(
                ChartDiagnostic(
                    level="error",
                    field="spec.workflow.steps",
                    message="MVP runner needs at least one workflow step",
                )
            )
        step_ids = [step.id for step in self.chart.spec.workflow.steps]
        if len(step_ids) != len(set(step_ids)):
            diagnostics.append(
                ChartDiagnostic(
                    level="error",
                    field="spec.workflow.steps",
                    message="workflow step ids must be unique",
                )
            )
        return diagnostics

    def assert_path_allowed(self, raw_path: str | Path) -> Path:
        path = (self.workspace / raw_path).resolve()
        try:
            path.relative_to(self.workspace)
        except ValueError as exc:
            raise PolicyDenied(f"path escapes workspace: {raw_path}") from exc
        return path

    def assert_tool_allowed(self, tool: str) -> None:
        allow = self.chart.spec.tools.allow
        deny = set(self.chart.spec.tools.deny)
        if tool in deny:
            raise PolicyDenied(f"tool denied by chart: {tool}")
        if allow and tool not in allow:
            raise PolicyDenied(f"tool not in allow list: {tool}")

    def assert_shell_allowed(self, command: str) -> None:
        if self.chart.spec.permissions.mode in {"read-only", "audit"}:
            raise PolicyDenied("shell is not allowed in read-only/audit mode")
        lowered = command.lower()
        for fragment in self.dangerous_fragments:
            if fragment in lowered:
                raise PolicyDenied(f"dangerous shell command denied: {fragment}")


class LocalMvpHarness:
    """Durable local AgentChart runner."""

    def __init__(self, *, chart: AgentChart, store: DurableRunStore) -> None:
        self.chart = chart
        self.workspace = Path(chart.spec.workspace.cwd).expanduser().resolve()
        self.store = store
        self.policy = HarnessPolicy(self.workspace, chart)

    def health(self) -> dict[str, Any]:
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.store.root.mkdir(parents=True, exist_ok=True)
        probe = self.store.root / ".write-probe"
        probe.write_text("ok\n", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return {
            "ok": True,
            "runtime": self.chart.spec.runtimeClass.name,
            "workspace": str(self.workspace),
            "store": str(self.store.root),
        }

    def validate_or_raise(self) -> None:
        diagnostics = self.policy.validate_chart()
        errors = [item for item in diagnostics if item.level == "error"]
        if errors:
            joined = "; ".join(f"{item.field}: {item.message}" for item in errors)
            raise HarnessMvpError(joined)

    def start(self) -> RunState:
        self.validate_or_raise()
        self.health()
        run = self.store.create_run(self.chart, self.workspace)
        self.store.mark_latest(run.run_id)
        return self.resume(run.run_id)

    def resume(self, run_id: str) -> RunState:
        with self.store.lock(run_id):
            state = self.store.load_state(run_id)
            if state.status in {"completed", "cancelled"}:
                self.store.append_event(run_id, "lifecycle", {"status": state.status, "already_terminal": True})
                return state

            if state.status == "running":
                state.status = "recovered"
                self.store.append_event(run_id, "lifecycle", {"status": "recovered"})

            state.status = "running"
            self._heartbeat(state)
            try:
                for step in self.chart.spec.workflow.steps:
                    if step.id in state.completed_steps:
                        self.store.append_event(run_id, "tool", {"step": step.id, "status": "skipped"})
                        continue
                    self._run_step_with_retries(state, step)
                state.status = "completed"
                state.current_step = None
                self.store.append_event(run_id, "lifecycle", {"status": "completed"})
            except Exception as exc:
                state.status = "failed"
                state.error = str(exc)
                self.store.append_event(run_id, "error", {"message": str(exc), "step": state.current_step})
                raise
            finally:
                self.store.save_state(state)
            return state

    def _heartbeat(self, state: RunState) -> None:
        state.heartbeat_at = time.time()
        self.store.save_state(state)
        self.store.append_event(state.run_id, "lifecycle", {"status": state.status, "heartbeat": state.heartbeat_at})

    def _run_step_with_retries(self, state: RunState, step: WorkflowStep) -> None:
        retry = self.chart.spec.workflow.retries
        attempts = 0
        while attempts < retry.maxAttempts:
            attempts += 1
            state.current_step = step.id
            state.attempts[step.id] = attempts
            self.store.save_state(state)
            try:
                if step.mutates or step.tool in {"write_file", "shell"}:
                    self._checkpoint(state, step)
                result = self._execute_step(state, step)
                state.completed_steps.append(step.id)
                state.current_step = None
                state.failed_step = None
                self.store.append_event(
                    state.run_id,
                    "tool",
                    {"step": step.id, "tool": step.tool, "status": "completed", "result": result},
                )
                self._heartbeat(state)
                return
            except Exception as exc:
                state.failed_step = step.id
                self.store.append_event(
                    state.run_id,
                    "error",
                    {"step": step.id, "attempt": attempts, "max_attempts": retry.maxAttempts, "message": str(exc)},
                )
                if attempts >= retry.maxAttempts:
                    raise
                time.sleep(retry.backoffSeconds * attempts)

    def _checkpoint(self, state: RunState, step: WorkflowStep) -> None:
        checkpoints = self.store.run_dir(state.run_id) / "checkpoints"
        checkpoint_dir = checkpoints / f"{len(list(checkpoints.iterdir())) + 1:04d}-{step.id}"
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        manifest: dict[str, Any] = {"step": step.id, "files": []}
        if step.tool == "write_file":
            target = step.args.get("path")
            if target:
                path = self.policy.assert_path_allowed(str(target))
                if path.exists() and path.is_file():
                    backup = checkpoint_dir / path.name
                    shutil.copy2(path, backup)
                    manifest["files"].append({"path": str(path), "backup": str(backup)})
        _atomic_write_json(checkpoint_dir / "manifest.json", manifest)
        self.store.append_event(state.run_id, "checkpoint", {"step": step.id, "path": str(checkpoint_dir)})

    def _execute_step(self, state: RunState, step: WorkflowStep) -> dict[str, Any]:
        self.policy.assert_tool_allowed(step.tool)
        if step.tool == "read_file":
            path = self.policy.assert_path_allowed(str(step.args["path"]))
            text = path.read_text(encoding="utf-8")
            max_chars = int(step.args.get("maxChars", 4000))
            return {"path": str(path), "chars": len(text), "preview": text[:max_chars]}

        if step.tool == "write_file":
            if self.chart.spec.permissions.mode == "read-only":
                raise PolicyDenied("write_file is not allowed in read-only mode")
            path = self.policy.assert_path_allowed(str(step.args["path"]))
            path.parent.mkdir(parents=True, exist_ok=True)
            content = str(step.args.get("content", ""))
            path.write_text(content, encoding="utf-8")
            return {"path": str(path), "bytes": len(content.encode("utf-8"))}

        if step.tool == "shell":
            command = str(step.args["command"])
            self.policy.assert_shell_allowed(command)
            timeout = step.timeoutSeconds or self.chart.spec.workflow.timeoutSeconds or 120
            completed = subprocess.run(
                command,
                cwd=str(self.workspace),
                shell=True,
                text=True,
                capture_output=True,
                timeout=timeout,
                check=False,
            )
            result = {
                "command": command,
                "returncode": completed.returncode,
                "stdout": completed.stdout[-4000:],
                "stderr": completed.stderr[-4000:],
            }
            if completed.returncode != 0:
                raise HarnessMvpError(f"shell step failed with exit code {completed.returncode}: {command}")
            return result

        if step.tool == "record_note":
            note_path = self.store.run_dir(state.run_id) / "notes.md"
            note_path.parent.mkdir(parents=True, exist_ok=True)
            note = str(step.args.get("note", ""))
            with note_path.open("a", encoding="utf-8") as handle:
                handle.write(note.rstrip() + "\n")
            return {"note": note}

        raise HarnessMvpError(f"Unsupported tool: {step.tool}")


def sample_chart(cwd: str | Path) -> dict[str, Any]:
    """Return a conservative sample chart dictionary."""
    return {
        "apiVersion": "agentchart.dev/v0",
        "kind": "AgentChart",
        "metadata": {
            "name": "mvp-local-smoke",
            "description": "High-availability local harness smoke run",
        },
        "spec": {
            "runtimeClass": {"name": "mvp-local", "version": "0.1"},
            "model": {"primary": "local-deterministic"},
            "tools": {"allow": ["read_file", "write_file", "shell", "record_note"]},
            "permissions": {"mode": "restricted"},
            "workspace": {"cwd": str(Path(cwd).resolve()), "isolation": "sandbox"},
            "session": {"persistence": "runtime", "resume": True, "checkpoint": {"enabled": True}},
            "workflow": {
                "retries": {"maxAttempts": 2, "backoffSeconds": 0.1},
                "timeoutSeconds": 30,
                "steps": [
                    {
                        "id": "write-proof",
                        "tool": "write_file",
                        "args": {
                            "path": ".agentchart-mvp/proof.txt",
                            "content": "AgentChart MVP harness is alive.\\n",
                        },
                        "mutates": True,
                    },
                    {
                        "id": "read-proof",
                        "tool": "read_file",
                        "args": {"path": ".agentchart-mvp/proof.txt", "maxChars": 200},
                    },
                    {
                        "id": "shell-proof",
                        "tool": "shell",
                        "args": {"command": "test -s .agentchart-mvp/proof.txt"},
                        "timeoutSeconds": 10,
                    },
                ],
            },
            "observability": {"events": ["lifecycle", "tool", "checkpoint", "error"], "traces": True},
        },
    }


def write_sample_chart(path: str | Path, cwd: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(yaml.safe_dump(sample_chart(cwd), sort_keys=False), encoding="utf-8")
    return output
