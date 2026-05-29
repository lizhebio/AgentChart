# High-Availability MVP Harness

The MVP harness is a local AgentChart runner that proves durable agent execution
without requiring an LLM provider. It is intentionally small, but the substrate
is production-shaped: policy admission, atomic state writes, append-only traces,
checkpoints, retries, heartbeats, run locks, and resumable execution.

## Why Local First

LLM runtimes add nondeterminism, provider failures, streaming formats, tool
schemas, and prompt assembly differences. Those matter, but they should not hide
whether the harness substrate itself is reliable. The local runtime makes the
controller testable:

- Same chart, same steps, reproducible behavior.
- No API key needed.
- Failure and resume paths can be exercised in unit tests.
- Later adapters can reuse the same durable run store and event protocol.

## Files

| File | Purpose |
|---|---|
| `ohmo/harness_mvp.py` | AgentChart schema, durable run store, policy engine, local runner |
| `ohmo/cli.py` | `ohmo harness ...` commands |
| `tests/test_ohmo/test_harness_mvp.py` | Persistence, resume, and sandbox policy tests |

## CLI

Generate a sample chart:

```bash
uv run agentchartmo harness sample --output agentchart.mvp.yaml --cwd .
```

Validate chart and storage:

```bash
uv run agentchartmo harness doctor agentchart.mvp.yaml
```

Run it:

```bash
uv run agentchartmo harness run agentchart.mvp.yaml
```

Inspect latest status:

```bash
uv run agentchartmo harness status latest
```

Resume an interrupted or failed run:

```bash
uv run agentchartmo harness resume latest agentchart.mvp.yaml
```

## AgentChart Shape

```yaml
apiVersion: agentchart.dev/v0
kind: AgentChart
metadata:
  name: mvp-local-smoke
spec:
  runtimeClass:
    name: mvp-local
  model:
    primary: local-deterministic
  tools:
    allow: [read_file, write_file, shell, record_note]
  permissions:
    mode: restricted
  workspace:
    cwd: /absolute/project/path
    isolation: sandbox
  session:
    persistence: runtime
    resume: true
    checkpoint:
      enabled: true
  workflow:
    retries:
      maxAttempts: 2
      backoffSeconds: 0.1
    timeoutSeconds: 30
    steps:
      - id: write-proof
        tool: write_file
        args:
          path: .agentchart-mvp/proof.txt
          content: "AgentChart MVP harness is alive.\n"
        mutates: true
      - id: read-proof
        tool: read_file
        args:
          path: .agentchart-mvp/proof.txt
      - id: shell-proof
        tool: shell
        args:
          command: test -s .agentchart-mvp/proof.txt
```

## High-Availability Properties

| Property | Implementation |
|---|---|
| Durable run state | `run.json` is written atomically with temp file + `fsync` + `os.replace` |
| Append-only audit log | `events.jsonl` records lifecycle, tool, checkpoint, and error events |
| Locking | `.lock` file prevents two processes from mutating the same run |
| Stale recovery | Resuming a `running` state marks it `recovered` before continuing |
| Idempotent resume | Completed step ids are persisted and skipped on resume |
| Heartbeats | Each run writes `heartbeat_at` during execution |
| Retry/backoff | Per-step retries are controlled by `workflow.retries` |
| Checkpoints | Mutating steps create checkpoint directories before execution |
| Path sandbox | File paths must stay inside `spec.workspace.cwd` |
| Command guard | Dangerous shell fragments such as `sudo`, `rm -rf /`, and device writes are denied |
| Provider independence | No LLM/API key is required for smoke tests |

## Limitations

The MVP intentionally avoids pretending that all side effects can be rolled back.
File writes can be checkpointed. Arbitrary shell commands cannot be made safe by
metadata alone, so the runner combines command denial, timeout, trace capture,
and conservative chart permissions.

The next adapter should reuse this controller substrate rather than bypass it.
Recommended order:

1. DeepAgents adapter: compile AgentChart into `create_deep_agent(...)`.
2. OpenClaw adapter: compile AgentChart into native agent config and preserve
   OpenClaw event/channel/sandbox semantics.
3. Claude Code adapter: preserve prompt order, sidechain transcript, MCP, and
   permission precedence.
