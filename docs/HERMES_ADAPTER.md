# Hermes Adapter

The Hermes adapter compiles an AgentChart into a Hermes Agent invocation. It is
designed for environments where Hermes is installed as a full agent application
and AgentChart provides the declarative run/package layer.

The adapter is intentionally non-invasive:

- It does not vendor or require Hermes at AgentChart import time.
- It can compile a chart into CLI arguments without running a model.
- It can call Hermes' Python entry point only when `run_agent` is importable.

## Minimal Chart

```yaml
apiVersion: agentchart.dev/v0
kind: AgentChart
metadata:
  name: hermes-research
spec:
  runtimeClass:
    name: hermes
  model:
    primary: anthropic/claude-sonnet-4.6
  tools:
    allow: [read_file, write_file, shell, web_search]
  permissions:
    mode: restricted
  workspace:
    cwd: /workspace/project
    isolation: worktree
  session:
    checkpoint:
      enabled: true
  skills:
    refs:
      - research
      - review
  workflow:
    maxTurns: 7
extensions:
  hermes:
    query: "Summarize this repository and identify adapter risks."
    provider: anthropic
    toolsets:
      - safe
    skills:
      - citation-check
```

## Compile To CLI Arguments

```python
from ohmo.harness_mvp import load_agent_chart
from agentchart.adapters.hermes import compile_hermes_spec

chart = load_agent_chart("agentchart.hermes.yaml")
spec = compile_hermes_spec(chart)

print(spec.cli_args())
```

Example output:

```text
[
  "hermes", "chat",
  "--query", "Summarize this repository and identify adapter risks.",
  "--model", "anthropic/claude-sonnet-4.6",
  "--toolsets", "safe,development,research",
  "--skills", "research",
  "--skills", "review",
  "--skills", "citation-check",
  "--provider", "anthropic",
  "--quiet",
  "--worktree",
  "--checkpoints",
  "--max-turns", "7",
  "--source", "agentchart"
]
```

## Compile To Python Entry Arguments

```python
from ohmo.harness_mvp import load_agent_chart
from agentchart.adapters.hermes import compile_hermes_spec

chart = load_agent_chart("agentchart.hermes.yaml")
spec = compile_hermes_spec(chart)

print(spec.python_kwargs())
```

These kwargs target Hermes' `run_agent.main(...)` function.

## Run Hermes From A Chart

```python
from ohmo.harness_mvp import load_agent_chart
from agentchart.adapters.hermes import run_hermes_from_chart

chart = load_agent_chart("agentchart.hermes.yaml")
run_hermes_from_chart(chart)
```

This requires Hermes' `run_agent` module to be importable in the current Python
environment.

## Mapping Rules

| AgentChart Field | Hermes Target |
|---|---|
| `spec.runtimeClass.name: hermes` | Enables the Hermes adapter |
| `spec.model.primary` | `--model` and `run_agent.main(model=...)` |
| `spec.workflow.maxTurns` | `--max-turns` and `max_turns` |
| `spec.skills.refs` plus `extensions.hermes.skills` | repeated `--skills` |
| `spec.tools.allow` | inferred Hermes toolsets |
| `spec.tools.deny` | disabled Hermes toolsets |
| `spec.workspace.isolation: worktree` | `--worktree` |
| `spec.session.checkpoint.enabled` | `--checkpoints` |
| `spec.permissions.mode: full_auto` | `--yolo` |
| `extensions.hermes.query` | `--query` and `query` |
| `extensions.hermes.provider` | `--provider` |
| `extensions.hermes.toolsets` | explicit Hermes toolsets |

