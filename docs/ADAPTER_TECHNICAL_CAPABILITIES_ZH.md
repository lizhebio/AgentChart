# 不同 Agent Adapter 的技术能力特点

本文从 **harness** 视角整理当前 AgentChart workspace 中几个 agent/runtime adapter 的技术特点。

这里的 adapter 不是简单的“把命令拼起来”，而是把 AgentChart 的声明式意图编译到不同 agent/runtime 的原生能力面上：

```text
AgentChart YAML
  -> adapter compile
  -> runtime-native config / invocation / resource spec
  -> harness/controller 负责状态、策略、trace、resume 的统一治理
```

当前已经有的 adapter：

| Adapter | 当前实现 | 定位 |
|---|---|---|
| DeepAgents | `src/agentchart/adapters/deepagents.py` | library runtime adapter |
| Hermes | `src/agentchart/adapters/hermes.py` | full agent application adapter |
| OpenClaw | `src/agentchart/adapters/openclaw.py` | controller/platform runtime adapter |
| Claude Code | `src/agentchart/adapters/claude_code.py` | coding-agent runtime definition adapter |
| Codex | `src/agentchart/adapters/codex.py` | repository-workflow agent adapter |

这些 adapter 目前都是 **compile-first**：先把 AgentChart 编译成稳定、可测试的契约，不在 adapter 层贸然执行外部 runtime。

## 总览矩阵

| Adapter | AgentChart runtimeClass | 编译目标 | Harness 价值 | 主要风险 |
|---|---|---|---|---|
| DeepAgents | `deepagents` | `create_deep_agent(...)` 参数包 | 最适合作为第一 library adapter，映射面清晰 | Controller 生命周期需要 AgentChart 自己补 |
| Hermes | `hermes` | `hermes chat ...` / `run_agent.main(...)` | 连接完整个人 agent 应用，能复用 Hermes 的产品化能力 | Hermes 自身状态、记忆、渠道语义较重 |
| OpenClaw | `openclaw` | OpenClaw-style agent config | 最接近完整 controller/platform runtime | 平台语义多，不能过度压平 |
| Claude Code | `claude-code` | Claude Code-style AgentDefinition | 强工具/MCP/权限/sidechain 语义 | prompt order、permission precedence 必须谨慎保留 |
| Codex | `codex` | Codex-oriented repo run config | repo 知识、评审、测试、修复循环强 | 公开 runtime surface 有限，宜作为 workflow adapter |

## DeepAgents Adapter

**定位：** library runtime adapter。

DeepAgents 的优势是创建面清晰：`model`、`tools`、`system_prompt`、`subagents`、`skills`、`memory`、`permissions`、`backend`、`interrupt_on`、`checkpointer`、`store` 等参数都能自然映射 AgentChart。

从 harness 角度看，DeepAgents 的特点是：

| 能力 | 特点 |
|---|---|
| Agent package | 中等偏强，主要通过函数参数组织 |
| Tool adapter | 强，内置文件、shell、task 等工具 |
| Permission | 有 filesystem permission 和 HITL interrupt surface |
| Memory/skills | 有明确参数面 |
| Subagents | 原生支持 |
| Controller | 偏弱，调用方仍要负责 run lifecycle、resume、trace、部署 |

AgentChart 的适配策略：

- 把 portable AgentChart 字段编译成 `DeepAgentsCreateSpec`。
- 把 filesystem policy 编译成 DeepAgents `FilesystemPermission`。
- 把 restricted/default 权限模式编译成默认 `interrupt_on`。
- DeepAgents 未安装时不影响 AgentChart core。

适合场景：

- 快速验证 AgentChart schema 能否映射到真实 agent library。
- 做外部 runtime 的第一条 adapter。
- 需要 subagents、skills、memory，但暂时不需要完整平台 lifecycle。

## Hermes Adapter

**定位：** full agent application adapter。

Hermes 不是单纯 runtime library，而是一个完整 agent 应用：有 CLI、模型配置、工具集、skills、memory、gateway、sessions、profiles 等产品化能力。

从 harness 角度看，Hermes 的特点是：

| 能力 | 特点 |
|---|---|
| Agent package | 当前偏函数/config 驱动，AgentChart 可补声明层 |
| Tool adapter | 强，Hermes 自带丰富工具和 toolsets |
| Memory | 强，带个人 agent 记忆和外部 memory 集成 |
| Channels | 强，gateway/IM/channel 能力是应用层优势 |
| Controller | 中等，Hermes 自有 session/状态；AgentChart 需要避免重复造轮子 |
| Product UX | 强，直接面向用户 |

AgentChart 的适配策略：

- 编译为 Hermes CLI：`hermes chat ...`。
- 编译为 Python 入口：`run_agent.main(...)` kwargs。
- 从 AgentChart tools 推断 Hermes toolsets。
- 从 AgentChart permissions 推断 `--yolo`、checkpoint、worktree 等运行标志。

适合场景：

- 用户已经安装 Hermes，希望通过 AgentChart 声明 Hermes run。
- 把 Hermes 当完整 agent app，而不是低层 library。
- 用 AgentChart 统一描述模型、工具、权限、skills、workspace。

注意：

- Hermes 的长期记忆、渠道接入、profile 语义应该保留在 Hermes 应用层。
- AgentChart 不应把 Hermes 的所有产品字段强行纳入核心 schema，应放在 `extensions.hermes`。

## OpenClaw Adapter

**定位：** controller/platform runtime adapter。

OpenClaw 在 taxonomy 中体现出最强的 controller 形态：channel binding、heartbeat、sandbox config、subagent policy、event stream、SDK run surface。

从 harness 角度看，OpenClaw 的特点是：

| 能力 | 特点 |
|---|---|
| Agent package | 强，接近完整 agent config |
| Controller | 强，有平台级 run lifecycle 语义 |
| Channels | 强，适合验证多渠道 agent |
| Sandbox | 强，适合验证隔离和策略 |
| Observability | 强，event stream 是重点 |
| Adapter 风险 | 高，平台语义不能被 AgentChart 核心字段压平 |

AgentChart 的适配策略：

- 编译成 OpenClaw-style config。
- 保留 `channels`、`sandbox`、`heartbeat`、`subagents`、`event_stream` 等 native 字段。
- AgentChart portable fields 只表达共同意图，OpenClaw-specific 行为放到 `extensions.openclaw`。

适合场景：

- 验证 AgentChart 是否能承载完整 controller/platform runtime。
- 测试 channel、heartbeat、event stream、sandbox 这类高可用 runtime 语义。

## Claude Code Adapter

**定位：** coding-agent runtime definition adapter。

Claude Code 的强项是 coding agent 语义：AgentDefinition、tools/MCP、permission precedence、isolation、skills、memory、sidechain transcript、cleanup 等。

从 harness 角度看，Claude Code 的特点是：

| 能力 | 特点 |
|---|---|
| Agent package | 强，agent definition 清晰 |
| Tool/MCP | 强，工具和 MCP 是核心能力 |
| Permissions | 强，但 precedence 和继承要谨慎 |
| Prompt order | 极其重要，不能随意重排 |
| Transcript | sidechain transcript 是关键运行证据 |
| Adapter 风险 | 高，近似编译很容易破坏原生语义 |

AgentChart 的适配策略：

- 编译为 Claude Code-style AgentDefinition。
- 保留 prompt 文件、overlay、system prompt 顺序。
- 映射 allowed/disallowed tools 和 permission mode。
- MCP、sidechain、native 配置放入 `extensions.claude_code`。

适合场景：

- 代码仓库内的长期开发/审查 agent。
- 需要强工具权限、MCP、sidechain transcript 的 coding runtime。

注意：

- Claude Code adapter 不应该“猜测”真实 prompt assembly 细节。
- 如果后续接真实运行，应优先保留 native behavior，再包一层 normalized events。

## Codex Adapter

**定位：** repository-workflow agent adapter。

Codex 更适合作为 repo 工程工作流参考和适配对象：它强调仓库知识、review/test/fix loop、实际命令验证、开发者协作、失败恢复。

从 harness 角度看，Codex 的特点是：

| 能力 | 特点 |
|---|---|
| Repo knowledge | 强，天然围绕代码仓库工作 |
| Evaluation | 强，适合 test/review/fix loop |
| Tooling | 强，工程工具链实践清晰 |
| Public runtime surface | 相对有限 |
| Adapter 策略 | 更适合 workflow/run config，而不是完整 runtime clone |

AgentChart 的适配策略：

- 编译成 Codex-oriented run config。
- 保留 `cwd`、sandbox、approval policy、knowledge files、eval hooks。
- 把 AGENTS/README/项目知识作为 repo knowledge 输入。

适合场景：

- 把 AgentChart 用于软件工程任务。
- 强调“跑测试、读 repo、修 bug、复核结果”的 agent workflow。

## Harness 视角的统一判断

不同 adapter 的核心差异不是“谁更聪明”，而是它们提供的 harness surface 不同。

| 判断维度 | DeepAgents | Hermes | OpenClaw | Claude Code | Codex |
|---|---|---|---|---|---|
| Library composability | 高 | 中 | 中 | 中 | 中 |
| Product readiness | 中 | 高 | 高 | 高 | 高 |
| Controller completeness | 中 | 中 | 高 | 高 | 中 |
| Tool semantics | 高 | 高 | 高 | 高 | 高 |
| Permission semantics | 中 | 中 | 高 | 高 | 高 |
| Memory/skills | 高 | 高 | 中 | 高 | 中 |
| Channel integration | 低 | 高 | 高 | 中 | 低 |
| Observability | 中 | 中 | 高 | 高 | 高 |
| Adapter risk | 中 | 中 | 高 | 高 | 中 |

## 非智能体平台：open-webui

open-webui 不属于当前 AgentChart 的 agent runtime adapter 范围。

它更适合被归类为：

- chat UI。
- model gateway。
- tool/function hosting platform。
- memory/resource provider。

因此工程中不保留 open-webui adapter。后续如果需要接入 open-webui，应以资源连接器或 provider integration 的方式设计，而不是把它列入 agent adapter。

## 当前实现边界

当前 adapter 都是 compile-first：

- 不主动安装外部 runtime。
- 不主动发起模型调用。
- 不把外部产品的私有语义塞进 AgentChart 核心 schema。
- 每个 adapter 都有独立 extension namespace。
- 每个 adapter 都有单元测试覆盖核心映射和错误路径。

后续要做真实 runtime integration 时，建议顺序是：

1. 给每个 adapter 增加 `doctor`，检查外部 runtime 是否安装、版本、认证、关键依赖。
2. 增加 `compile` CLI，只输出 native config/argv，不运行。
3. 增加 `run --dry-run`，写入 AgentChart controller trace，但不调用模型。
4. 增加真实 `run`，把外部 runtime events 归一化到 AgentChart event protocol。
5. 做 run-level evaluation：final answer、tool calls、permission decisions、trace、resume、cost、safety。
