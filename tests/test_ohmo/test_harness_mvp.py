from __future__ import annotations

import json
from pathlib import Path

import pytest

from ohmo.harness_mvp import (
    DurableRunStore,
    HarnessMvpError,
    LocalMvpHarness,
    load_agent_chart,
    sample_chart,
    write_sample_chart,
)


def test_mvp_harness_runs_and_persists_trace(tmp_path: Path) -> None:
    workspace = tmp_path / "repo"
    workspace.mkdir()
    chart_path = tmp_path / "agentchart.yaml"
    write_sample_chart(chart_path, workspace)

    chart = load_agent_chart(chart_path)
    store = DurableRunStore(tmp_path / ".ohmo" / "harness")
    state = LocalMvpHarness(chart=chart, store=store).start()

    assert state.status == "completed"
    assert state.completed_steps == ["write-proof", "read-proof", "shell-proof"]
    assert (workspace / ".openharness-mvp" / "proof.txt").read_text(encoding="utf-8")
    assert store.latest_run_id() == state.run_id

    events = (store.run_dir(state.run_id) / "events.jsonl").read_text(encoding="utf-8").splitlines()
    event_types = [json.loads(line)["type"] for line in events]
    assert "checkpoint" in event_types
    assert "tool" in event_types
    assert "lifecycle" in event_types


def test_mvp_harness_resume_skips_completed_steps(tmp_path: Path) -> None:
    workspace = tmp_path / "repo"
    workspace.mkdir()
    chart_data = sample_chart(workspace)
    chart_data["spec"]["workflow"]["steps"].append(
        {
            "id": "bad-shell",
            "tool": "shell",
            "args": {"command": "exit 7"},
            "timeoutSeconds": 5,
        }
    )
    chart_path = tmp_path / "agentchart.yaml"
    chart_path.write_text(__import__("yaml").safe_dump(chart_data, sort_keys=False), encoding="utf-8")
    chart = load_agent_chart(chart_path)
    store = DurableRunStore(tmp_path / ".ohmo" / "harness")
    harness = LocalMvpHarness(chart=chart, store=store)

    with pytest.raises(HarnessMvpError):
        harness.start()
    failed = store.load_state(store.latest_run_id() or "")
    assert failed.status == "failed"
    assert failed.completed_steps == ["write-proof", "read-proof", "shell-proof"]

    chart_data["spec"]["workflow"]["steps"][-1]["args"]["command"] = "true"
    chart_path.write_text(__import__("yaml").safe_dump(chart_data, sort_keys=False), encoding="utf-8")
    fixed_harness = LocalMvpHarness(chart=load_agent_chart(chart_path), store=store)
    recovered = fixed_harness.resume(failed.run_id)

    assert recovered.status == "completed"
    assert recovered.completed_steps == ["write-proof", "read-proof", "shell-proof", "bad-shell"]


def test_mvp_harness_denies_path_escape(tmp_path: Path) -> None:
    workspace = tmp_path / "repo"
    workspace.mkdir()
    chart_data = sample_chart(workspace)
    chart_data["spec"]["workflow"]["steps"] = [
        {"id": "escape", "tool": "read_file", "args": {"path": "../secret.txt"}}
    ]
    chart_path = tmp_path / "agentchart.yaml"
    chart_path.write_text(__import__("yaml").safe_dump(chart_data, sort_keys=False), encoding="utf-8")

    harness = LocalMvpHarness(
        chart=load_agent_chart(chart_path),
        store=DurableRunStore(tmp_path / ".ohmo" / "harness"),
    )
    with pytest.raises(Exception, match="path escapes workspace"):
        harness.start()
