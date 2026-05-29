"""CLI smoke tests."""

from typer.testing import CliRunner

from agentchart.cli import app


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "AgentChart" in result.output
