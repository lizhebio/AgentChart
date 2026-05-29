# DeepAgents Adapter

The DeepAgents adapter is the first external runtime adapter after the
high-availability MVP runner. It compiles an AgentChart into the argument bundle
expected by DeepAgents' `create_deep_agent(...)` API.

The adapter does not make DeepAgents a hard dependency of AgentChart. The core
compile step is pure Python and testable without the external runtime installed.
DeepAgents is imported only when `create_deep_agent_from_chart(...)` is called.

## Why This Adapter Comes First

DeepAgents has a clean library surface:

- `model`
- `tools`
- `system_prompt`
- `subagents`
- `skills`
- `memory`
- `permissions`
- `backend`
- `interrupt_on`
- `checkpointer`
- `store`
- `name`
- `cache`

That maps well to AgentChart's portable fields without forcing AgentChart to own
DeepAgents' whole lifecycle.

## Minimal Chart

```yaml
apiVersion: agentchart.dev/v0
kind: AgentChart
metadata:
  name: hermes-deepagents
spec:
  runtimeClass:
    name: deepagents
  model:
    primary: anthropic:claude-sonnet-4-5
  prompt:
    system: |
      You are Hermes, a careful long-horizon research agent.
  tools:
    allow: [read_file, write_file, shell]
  permissions:
    mode: restricted
  workspace:
    cwd: /workspace/hermes
    isolation: sandbox
  memory:
    enabled: true
    sources:
      - memory/hermes.md
  skills:
    refs:
      - research
      - review
extensions:
  deepagents:
    skills:
      - citation-check
    memory:
      - memory/project.md
    subagents:
      - name: critic
        description: Review the main agent's conclusions before final output.
    interrupt_on:
      write_file: true
      execute: true
```

## Compile Without DeepAgents Installed

```python
from ohmo.harness_mvp import load_agent_chart
from agentchart.adapters.deepagents import compile_deepagents_spec

chart = load_agent_chart("agentchart.deepagents.yaml")
spec = compile_deepagents_spec(chart)

print(spec.create_kwargs())
```

## Build A DeepAgents Runnable

```python
from ohmo.harness_mvp import load_agent_chart
from agentchart.adapters.deepagents import create_deep_agent_from_chart

chart = load_agent_chart("agentchart.deepagents.yaml")
agent = create_deep_agent_from_chart(chart)
```

This requires the DeepAgents runtime package to be installed in the Python
environment. If it is not installed, the adapter raises a clear
`DeepAgentsAdapterError`.

## Mapping Rules

| AgentChart Field | DeepAgents Target |
|---|---|
| `spec.model.primary` | `model` |
| `spec.prompt.system` and prompt overlays | `system_prompt` |
| `spec.skills.refs` plus `extensions.deepagents.skills` | `skills` |
| `spec.memory.sources` plus `extensions.deepagents.memory` | `memory` |
| `spec.permissions.mode` | `permissions` and default `interrupt_on` |
| `spec.permissions.rules` for filesystem resources | `FilesystemPermission` |
| `spec.workspace.isolation` | filesystem allow/deny scoping |
| `metadata.name` | `name` |
| `extensions.deepagents.subagents` | `subagents` |
| `extensions.deepagents.create_kwargs` | extra `create_deep_agent(...)` kwargs |

## Current Limits

- This is a compile adapter, not yet a full controller integration.
- AgentChart still owns durable run lifecycle separately from DeepAgents.
- DeepAgents runtime objects such as custom backends, stores, and checkpointers
  can be passed through `extensions.deepagents` only when constructing charts in
  Python. YAML charts should use serializable fields.
- Unsupported allowed tools are rejected instead of silently dropped.

