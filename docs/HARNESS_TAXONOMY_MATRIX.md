# Harness Taxonomy Matrix

This matrix turns the harness research notes into a working comparison surface.
It separates model capability from the surrounding runtime substrate: workflow,
memory, skills, tools, permissions, sandboxing, orchestration, observability, and
evaluation.

## Scoring

| Score | Meaning |
|---|---|
| 0 | Not present or no clear evidence |
| 1 | Partial, ad hoc, or external-only support |
| 2 | First-class support with meaningful runtime behavior |
| 3 | Mature support with policy, lifecycle, and observability hooks |

## Matrix

| Project | Workflow Loop | Tool Adapter | Workspace / Sandbox | Memory | Skills | Subagents | Permissions | Observability | Evaluation Fit | Notes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| OpenHarness | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | Python CLI harness with tools, skills, sessions, memory, permissions, and tests. The new MVP adds durable AgentChart runs. |
| OpenClaw | 3 | 3 | 3 | 2 | 2 | 3 | 3 | 3 | 2 | Strongest controller evidence: channel bindings, heartbeat, subagent policy, sandbox config, event stream, SDK run surface. |
| DeepAgents | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | Clean library abstraction around graph assembly, middleware, filesystem, memory, skills, permissions, and subagents. Controller is mostly external. |
| Claude Code Extracted | 3 | 3 | 3 | 2 | 2 | 3 | 3 | 3 | 2 | Strong AgentDefinition and runtime adapter semantics: tools/MCP, permission precedence, isolation, sidechain transcript, cleanup. |
| Hermes Agent | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | Runtime loop and checkpoint/delegate mechanisms exist, but they are function/config driven rather than a standalone manifest. |
| open-webui | 1 | 2 | 0 | 2 | 1 | 0 | 2 | 2 | 1 | Best treated as chat/tool/function/memory resource provider, not as an autonomous agent harness runtime. |

## Capability Breakdown

| Capability | What Good Looks Like | Strong Local Evidence |
|---|---|---|
| Agent package | Declarative identity, model, prompt, tools, permissions, memory, skills, session, and workflow intent | OpenClaw `AgentConfig`; Claude Code `AgentDefinition`; DeepAgents `create_deep_agent(...)` parameters |
| Harness adapter | Compiles package intent into native runtime config and preserves prompt/tool/session semantics | DeepAgents graph assembler; Claude Code `runAgent`; OpenClaw runner; Hermes conversation loop |
| Controller | Installs, runs, resumes, pauses, binds channels, applies policy, captures telemetry, and tracks status | OpenClaw has the strongest native shape; the MVP adds this as a local durable runner |
| Tool adapter | Structured tool schema, executor boundary, result normalization, timeout, and failure semantics | Claude Code tools/MCP; OpenHarness tool tests; open-webui tools/functions |
| Permissions | Tool/resource allow and deny rules, approval, sandbox, and inheritance policy | Claude Code permission precedence; DeepAgents HITL; OpenClaw sandbox/subagent policy |
| Memory lifecycle | Separates active context, summaries, durable notes, reconstructible tool output, and stale state | Claude memory scopes; DeepAgents memory middleware; OpenHarness/ohmo workspace memory |
| Skills | Versionable procedural knowledge loaded on demand | Claude skills; DeepAgents skills middleware; OpenHarness skills/plugins |
| Observability | Normalized event stream plus raw runtime events, transcripts, checkpoints, and cost counters | OpenClaw event stream; Claude sidechain transcript; OpenHarness testable traces |
| Evaluation | Final output plus trace, safety, cost, state, and attribution metrics | Existing benchmark literature; MVP stores run-level traces for later evaluators |

## Practical Design Rules

1. Treat `open-webui` as a chat/tool/memory platform, not as a full agent runtime.
2. Keep portable AgentChart fields small; put runtime-specific behavior under extensions.
3. Preserve native prompt assembly order in each adapter.
4. Do not pretend tool execution is idempotent. Add checkpoints, approvals, and compensation hooks.
5. Evaluate a run, not only its final answer. Store trace, tool calls, retries, checkpoints, and policy decisions.
6. Separate reconstructible data from durable decisions. Tool output can often be re-read; user choices and confirmed conclusions should persist.

## Recommended Build Order

| Phase | Goal | Deliverable |
|---|---|---|
| 1 | Prove controller substrate | `mvp-local` durable AgentChart runner |
| 2 | Add one library adapter | DeepAgents adapter, because its graph creation surface is clean |
| 3 | Add one product runtime adapter | OpenClaw adapter, because it has the richest controller/runtime config |
| 4 | Add high-value closed runtime adapter | Claude Code adapter, preserving sidechain, permission, and MCP semantics |
| 5 | Add platform resource adapter | open-webui as tool/function/chat/memory provider |
