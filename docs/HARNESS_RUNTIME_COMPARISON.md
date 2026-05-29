# AgentChart vs Claude Code vs Codex vs DeepAgents

This report compares representative harness runtimes by engineering surface, not
by model quality. The central question is: what infrastructure turns a model into
a reliable long-horizon agent?

## Executive View

| Runtime | Best At | Main Tradeoff |
|---|---|---|
| AgentChart | Open, hackable Python harness substrate with CLI, tools, skills, memory, permissions, sessions, and local extensibility | Needs stronger declarative packaging and production-grade controller boundaries |
| Claude Code | Polished coding-agent runtime with strong AgentDefinition, tools/MCP, permission semantics, isolation, transcript, and cleanup | Product-internal behavior is complex; adapter must preserve exact prompt/cache/permission semantics |
| Codex | Agent-first software engineering workflow, repository knowledge, review/test/fix loops, and practical harness iteration | Public implementation details are limited; best used as design reference rather than direct adapter target |
| DeepAgents | Clean composable library for deep agents with graph, middleware, filesystem, memory, skills, subagents, and permissions | Less of a full lifecycle controller; caller must own install/run/resume/channel lifecycle |
| OpenClaw | Broad agent platform shape: runtime config, channels, heartbeat, subagents, sandbox, event stream, SDK | Larger surface area; adapter must avoid flattening platform-specific lifecycle semantics |

## Comparison Matrix

| Dimension | AgentChart | Claude Code | Codex | DeepAgents | OpenClaw |
|---|---|---|---|---|---|
| Declarative agent package | Medium | High | Medium, repo-knowledge centered | Medium, function parameter centered | High |
| Tool calling | High | High | High | High | High |
| MCP/tool server support | Medium | High | High conceptually | Medium | Medium |
| Workspace state | Medium | High | High | Medium | High |
| Permissions | Medium | High | High product-side | Medium | High |
| Checkpoint/resume | Medium | High | High product-side | Medium via checkpointer/store | High |
| Memory | Medium | Medium | Repository knowledge emphasis | Medium | Medium |
| Skills | Medium | High | Repository/process knowledge | High | Medium |
| Subagents | Medium | High | Limited public detail | High | High |
| Observability | Medium | High | High product-side | Medium | High |
| Evaluation integration | Medium | Medium | Strong workflow practice | Medium | Medium |
| Best adapter priority | Native | Third | Reference only | First | Second |

## Architecture Read

### AgentChart

AgentChart is the right place to host the open harness experiment because it is
already an agent CLI substrate with tools, skills, memory, permission tests, and
session storage. The gap is not basic capability; the gap is a crisp split among:

- Agent package: declarative intent.
- Adapter: runtime-specific compilation.
- Controller: durable lifecycle, policy, resume, and telemetry.

The new `mvp-local` runner starts closing that gap with a deterministic runtime
that proves the controller substrate before any LLM-specific complexity enters.

### Claude Code

Claude Code has one of the strongest agent package stories: Markdown/JSON agent
definitions, tool allow/deny fields, MCP servers, permission mode, isolation,
skills, memory, max turns, and background behavior. Its adapter complexity is in
the runtime: prompt-cache-sensitive context construction, parent/child permission
precedence, sidechain transcript, remote isolation, MCP lifecycle, and cleanup.

Adapter guidance: do not compile Claude Code by approximating its prompt order.
Preserve native semantics and expose normalized events around them.

### Codex

Codex is most useful here as a design reference. OpenAI's public harness writing
emphasizes repository knowledge, evaluation-driven harness improvement, review
feedback loops, tests, build recovery, and keeping agent knowledge in the repo.
That suggests a practical principle for AgentChart:

> Repositories should contain knowledge for agents, not just humans.

AgentChart should therefore support prompt files, repo-local policy, known test
commands, failure recovery recipes, and evaluation hooks.

### DeepAgents

DeepAgents is the best first external adapter target. Its creation surface is
clear: model, tools, prompt, middleware, subagents, skills, memory, permissions,
backend, interrupt policy, checkpointer, store, name, and cache. It maps well to
AgentChart core fields without pretending to own the whole platform lifecycle.

Adapter guidance: let AgentChart compile to `create_deep_agent(...)`, then let
the AgentChart controller own run state, normalized events, policy admission,
and deployment metadata.

Initial implementation: `src/agentchart/adapters/deepagents.py` compiles an
AgentChart into a testable `create_deep_agent` argument bundle and lazily imports
DeepAgents only when building the runnable. This keeps the core package usable
without requiring the external runtime dependency.

### OpenClaw

OpenClaw is the strongest local evidence for a full controller-style runtime:
agent config, defaults, channel bindings, heartbeat, sandbox, subagent policy,
event stream, SDK namespaces, and runtime fallback. It is the best second adapter
target because it can validate AgentChart beyond a library call.

Adapter guidance: keep OpenClaw-specific fields under `extensions.openclaw`.
Do not force channel binding, heartbeat, ACP, embedded runtime, and sandbox into
portable fields.

## Decision

1. Build the AgentChart schema and controller substrate locally.
2. Add DeepAgents adapter first.
3. Add OpenClaw adapter second.
4. Treat Claude Code as a high-value but delicate adapter.
5. Treat Codex as harness design guidance unless more public integration surface
   becomes available.
6. Treat open-webui as a resource provider or chat adapter, not as the first
   autonomous harness runtime.
