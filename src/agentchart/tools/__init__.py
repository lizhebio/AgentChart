"""Built-in tool registration."""

from agentchart.tools.ask_user_question_tool import AskUserQuestionTool
from agentchart.tools.agent_tool import AgentTool
from agentchart.tools.bash_tool import BashTool
from agentchart.tools.base import BaseTool, ToolExecutionContext, ToolRegistry, ToolResult
from agentchart.tools.brief_tool import BriefTool
from agentchart.tools.config_tool import ConfigTool
from agentchart.tools.cron_create_tool import CronCreateTool
from agentchart.tools.cron_delete_tool import CronDeleteTool
from agentchart.tools.cron_list_tool import CronListTool
from agentchart.tools.cron_toggle_tool import CronToggleTool
from agentchart.tools.enter_plan_mode_tool import EnterPlanModeTool
from agentchart.tools.enter_worktree_tool import EnterWorktreeTool
from agentchart.tools.exit_plan_mode_tool import ExitPlanModeTool
from agentchart.tools.exit_worktree_tool import ExitWorktreeTool
from agentchart.tools.file_edit_tool import FileEditTool
from agentchart.tools.file_read_tool import FileReadTool
from agentchart.tools.file_write_tool import FileWriteTool
from agentchart.tools.glob_tool import GlobTool
from agentchart.tools.grep_tool import GrepTool
from agentchart.tools.list_mcp_resources_tool import ListMcpResourcesTool
from agentchart.tools.lsp_tool import LspTool
from agentchart.tools.mcp_auth_tool import McpAuthTool
from agentchart.tools.mcp_tool import McpToolAdapter
from agentchart.tools.notebook_edit_tool import NotebookEditTool
from agentchart.tools.read_mcp_resource_tool import ReadMcpResourceTool
from agentchart.tools.remote_trigger_tool import RemoteTriggerTool
from agentchart.tools.send_message_tool import SendMessageTool
from agentchart.tools.skill_tool import SkillTool
from agentchart.tools.sleep_tool import SleepTool
from agentchart.tools.task_create_tool import TaskCreateTool
from agentchart.tools.task_get_tool import TaskGetTool
from agentchart.tools.task_list_tool import TaskListTool
from agentchart.tools.task_output_tool import TaskOutputTool
from agentchart.tools.task_stop_tool import TaskStopTool
from agentchart.tools.task_update_tool import TaskUpdateTool
from agentchart.tools.team_create_tool import TeamCreateTool
from agentchart.tools.team_delete_tool import TeamDeleteTool
from agentchart.tools.todo_write_tool import TodoWriteTool
from agentchart.tools.tool_search_tool import ToolSearchTool
from agentchart.tools.web_fetch_tool import WebFetchTool
from agentchart.tools.web_search_tool import WebSearchTool


def create_default_tool_registry(mcp_manager=None) -> ToolRegistry:
    """Return the default built-in tool registry."""
    registry = ToolRegistry()
    for tool in (
        BashTool(),
        AskUserQuestionTool(),
        FileReadTool(),
        FileWriteTool(),
        FileEditTool(),
        NotebookEditTool(),
        LspTool(),
        McpAuthTool(),
        GlobTool(),
        GrepTool(),
        SkillTool(),
        ToolSearchTool(),
        WebFetchTool(),
        WebSearchTool(),
        ConfigTool(),
        BriefTool(),
        SleepTool(),
        EnterWorktreeTool(),
        ExitWorktreeTool(),
        TodoWriteTool(),
        EnterPlanModeTool(),
        ExitPlanModeTool(),
        CronCreateTool(),
        CronListTool(),
        CronDeleteTool(),
        CronToggleTool(),
        RemoteTriggerTool(),
        TaskCreateTool(),
        TaskGetTool(),
        TaskListTool(),
        TaskStopTool(),
        TaskOutputTool(),
        TaskUpdateTool(),
        AgentTool(),
        SendMessageTool(),
        TeamCreateTool(),
        TeamDeleteTool(),
    ):
        registry.register(tool)
    if mcp_manager is not None:
        registry.register(ListMcpResourcesTool(mcp_manager))
        registry.register(ReadMcpResourceTool(mcp_manager))
        for tool_info in mcp_manager.list_tools():
            registry.register(McpToolAdapter(mcp_manager, tool_info))
    return registry


__all__ = [
    "BaseTool",
    "ToolExecutionContext",
    "ToolRegistry",
    "ToolResult",
    "create_default_tool_registry",
]
