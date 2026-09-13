"""Presenter mode is opt-in, refuses before mutating, closes only its own workspaces (ADR-0008)."""

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from typer.testing import CliRunner

from cce import CceError
from cce.cli import app
from cce.herdr import (
    DEMO_LABEL,
    Herdr,
    HerdrError,
    PlannedTab,
    PlannedWorkspace,
    apply_layout,
    close_layout,
    plan_layout,
    preflight,
    read_record,
)
from cce.manifest import load
from tests.support.upstream import SyntheticUpstream


@pytest.fixture
def herdr_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, shim_bin: Callable[[str, str], Path]
) -> Path:
    """Install the fake herdr on PATH, set HERDR_ENV=1 and return the call log path."""
    shim_bin("herdr", "fake_herdr.py")
    log = tmp_path / "herdr.log"
    monkeypatch.setenv("FAKE_HERDR_LOG", str(log))
    monkeypatch.setenv("FAKE_HERDR_COUNTER", str(tmp_path / "herdr.counter"))
    monkeypatch.setenv("HERDR_ENV", "1")
    return log


def calls(log: Path) -> list[list[str]]:
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text().split("\n") if line]


class TestPlanLayout:
    def test_demo_first_then_one_workspace_per_ready_scenario(self, tmp_path: Path) -> None:
        manifest = load()
        paths = {
            "03-skills-on-demand": tmp_path / "s3",
            "06-agent-context-isolation": tmp_path / "s6",
        }
        overlays = {
            "03-skills-on-demand": [
                ".github/copilot-instructions.md",
                ".github/skills/a b/SKILL.md",
            ]
        }

        layout = plan_layout(manifest, tmp_path, paths, overlays)

        assert [item.label for item in layout] == [
            DEMO_LABEL,
            "cce:03-skills-on-demand",
            "cce:06-agent-context-isolation",
        ]
        assert layout[0].tabs[0] == PlannedTab("presenting", "cce guide presenting | less -R")
        three = layout[1]
        assert three.cwd == tmp_path / "s3"
        assert [tab.label for tab in three.tabs] == ["guide", "overlay", "copilot"]
        assert (
            three.tabs[1].command
            == "less -R .github/copilot-instructions.md '.github/skills/a b/SKILL.md'"
        )
        assert layout[2].tabs[-1] == PlannedTab("copilot:auditor", "copilot --agent auditor")

    def test_every_label_carries_the_cce_prefix(self, tmp_path: Path) -> None:
        manifest = load()
        paths = {scenario.slug: tmp_path / scenario.slug for scenario in manifest.scenarios}

        assert all(
            item.label.startswith("cce:") for item in plan_layout(manifest, tmp_path, paths, {})
        )


class TestPreflight:
    def test_requires_herdr_env(self, herdr_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HERDR_ENV", "true")

        with pytest.raises(CceError, match="HERDR_ENV=1") as raised:
            preflight({"HERDR_ENV": "true"}, lambda _: "/bin/herdr", Herdr(), [])

        assert raised.value.exit_code == 3
        assert calls(herdr_env) == []

    def test_requires_the_executable(self, herdr_env: Path) -> None:
        with pytest.raises(CceError, match="executable") as raised:
            preflight({"HERDR_ENV": "1"}, lambda _: None, Herdr(), [])

        assert raised.value.exit_code == 3
        assert calls(herdr_env) == []

    def test_refuses_when_a_planned_label_already_exists(
        self, herdr_env: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("FAKE_HERDR_LABELS", "mns,cce:demo")
        layout = [PlannedWorkspace(DEMO_LABEL, tmp_path, (PlannedTab("a", "true"),))]

        with pytest.raises(CceError, match="cce:demo") as raised:
            preflight({"HERDR_ENV": "1"}, lambda _: "/bin/herdr", Herdr(), layout)

        assert raised.value.exit_code == 3
        assert calls(herdr_env) == [["workspace", "list"]]


class TestApplyAndClose:
    def test_issues_the_exact_call_sequence_and_records_ids(
        self, herdr_env: Path, tmp_path: Path
    ) -> None:
        layout = [
            PlannedWorkspace(
                DEMO_LABEL, tmp_path, (PlannedTab("presenting", "cce guide presenting"),)
            ),
            PlannedWorkspace(
                "cce:01-x",
                tmp_path / "s1",
                (PlannedTab("guide", "cce guide 01"), PlannedTab("copilot", "copilot")),
            ),
        ]
        record = tmp_path / "herdr.json"

        created = apply_layout(Herdr(), layout, record)

        assert created == ["w1", "w2"]
        assert read_record(record) == ["w1", "w2"]
        assert calls(herdr_env) == [
            ["workspace", "create", "--cwd", str(tmp_path), "--label", "cce:demo", "--no-focus"],
            ["tab", "rename", "w1:t1", "presenting"],
            ["pane", "run", "w1:p1", "cce guide presenting"],
            [
                "workspace",
                "create",
                "--cwd",
                str(tmp_path / "s1"),
                "--label",
                "cce:01-x",
                "--no-focus",
            ],
            ["tab", "rename", "w2:t1", "guide"],
            ["pane", "run", "w2:p1", "cce guide 01"],
            [
                "tab",
                "create",
                "--workspace",
                "w2",
                "--cwd",
                str(tmp_path / "s1"),
                "--label",
                "copilot",
                "--no-focus",
            ],
            ["pane", "run", "t1:p1", "copilot"],
            ["workspace", "focus", "w1"],
        ]

    def test_failure_names_the_subcommand_and_keeps_the_record(
        self, herdr_env: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        assert not herdr_env.exists()
        monkeypatch.setenv("FAKE_HERDR_FAIL_ON", "tab create")
        layout = [
            PlannedWorkspace(
                "cce:01-x", tmp_path, (PlannedTab("guide", "x"), PlannedTab("copilot", "copilot"))
            )
        ]
        record = tmp_path / "herdr.json"

        with pytest.raises(HerdrError, match="herdr tab create failed") as raised:
            apply_layout(Herdr(), layout, record)

        assert raised.value.exit_code == 1
        assert read_record(record) == ["w1"]

    def test_close_only_recorded_ids_then_forgets_them(
        self, herdr_env: Path, tmp_path: Path
    ) -> None:
        record = tmp_path / "herdr.json"
        record.write_text(json.dumps({"workspaces": ["w7", "w9"]}))

        assert close_layout(Herdr(), record) == ["w7", "w9"]
        assert calls(herdr_env) == [["workspace", "close", "w7"], ["workspace", "close", "w9"]]
        assert not record.exists()
        assert close_layout(Herdr(), record) == []

    def test_non_json_answer_is_an_error(self, shim_bin: Callable[[str, str], Path]) -> None:
        shim = shim_bin("herdr", "fake_herdr.py")
        shim.write_text("#!/bin/sh\necho not-json\n")

        with pytest.raises(HerdrError, match="did not answer with JSON"):
            Herdr().workspace_labels()


class TestCommandLine:
    def test_setup_without_the_flag_never_talks_to_herdr(
        self, cli: CliRunner, herdr_env: Path, tmp_path: Path, upstream: SyntheticUpstream
    ) -> None:
        assert not herdr_env.exists()
        result = cli.invoke(
            app,
            [
                "--workspace",
                str(tmp_path / "ws"),
                "setup",
                "6",
                "--source-url",
                upstream.url,
                "--source-ref",
                upstream.head,
            ],
        )

        assert result.exit_code == 0
        assert calls(herdr_env) == []

    def test_setup_with_the_flag_lays_out_demo_plus_scenarios(
        self, cli: CliRunner, herdr_env: Path, tmp_path: Path, upstream: SyntheticUpstream
    ) -> None:
        ws = tmp_path / "ws"
        result = cli.invoke(
            app,
            [
                "--workspace",
                str(ws),
                "setup",
                "1",
                "6",
                "--herdr",
                "--source-url",
                upstream.url,
                "--source-ref",
                upstream.head,
            ],
        )

        assert result.exit_code == 0, result.stderr
        assert result.stdout.strip().endswith("herdr: created 3 workspaces")
        labels = [call[5] for call in calls(herdr_env) if call[:2] == ["workspace", "create"]]
        assert labels == [
            "cce:demo",
            "cce:01-instructions-timeless",
            "cce:06-agent-context-isolation",
        ]
        auditor = [
            call
            for call in calls(herdr_env)
            if call[:2] == ["pane", "run"] and "--agent auditor" in call[3]
        ]
        assert len(auditor) == 1
        assert read_record(ws / "herdr.json") == ["w1", "w2", "w3"]

    def test_setup_refuses_before_creating_anything_when_labels_collide(
        self,
        cli: CliRunner,
        herdr_env: Path,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        upstream: SyntheticUpstream,
    ) -> None:
        monkeypatch.setenv("FAKE_HERDR_LABELS", "cce:demo")

        result = cli.invoke(
            app,
            [
                "--workspace",
                str(tmp_path / "ws"),
                "setup",
                "6",
                "--herdr",
                "--source-url",
                upstream.url,
                "--source-ref",
                upstream.head,
            ],
        )

        assert result.exit_code == 3
        assert "cce:demo" in result.stderr
        assert [call[:2] for call in calls(herdr_env)] == [
            ["workspace", "list"],
            ["workspace", "list"],
        ]

    def test_teardown_with_the_flag_closes_recorded_workspaces(
        self, cli: CliRunner, herdr_env: Path, tmp_path: Path, upstream: SyntheticUpstream
    ) -> None:
        assert not herdr_env.exists()
        ws = tmp_path / "ws"
        cli.invoke(
            app,
            [
                "--workspace",
                str(ws),
                "setup",
                "6",
                "--herdr",
                "--source-url",
                upstream.url,
                "--source-ref",
                upstream.head,
            ],
        )
        log_before = len(calls(herdr_env))

        result = cli.invoke(app, ["--workspace", str(ws), "teardown", "--herdr"])

        assert result.exit_code == 0, result.stderr
        assert result.stdout == f"herdr: closed 2 workspaces\nremoved {ws}\n"
        assert calls(herdr_env)[log_before:] == [
            ["workspace", "close", "w1"],
            ["workspace", "close", "w2"],
        ]
