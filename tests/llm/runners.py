"""Runners that drive Copilot CLI or Claude Code non-interactively (ADR-0010).

Both runners normalise to :class:`RunResult`. Parsing is separated from
process execution so the default tier can unit-test it offline with canned
event streams.
"""

import hashlib
import json
import os
import subprocess
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol

from cce.dialect import Dialect

RUN_TIMEOUT_SECONDS = 900


@dataclass(frozen=True, slots=True)
class RunResult:
    """What a scenario check asserts on."""

    text: str
    skills_loaded: list[str]
    tools_used: list[str]
    input_tokens: int
    main_input_tokens: int
    subagent_input_tokens: int
    files_changed: list[str]
    transcript_path: str

    def structural(self) -> dict[str, Any]:
        """The shareable subset: no transcript text, only its length and digest."""
        data = asdict(self)
        data["text_sha256"] = hashlib.sha256(self.text.encode("utf-8")).hexdigest()
        data["text_length"] = len(self.text)
        del data["text"]
        return data


class AgentRunner(Protocol):
    name: str
    dialect: Dialect

    def run(
        self, worktree: Path, prompt: str, *, agent: str | None, artefacts: Path, label: str
    ) -> RunResult: ...


def capture(argv: list[str], *, cwd: Path | None, env: Mapping[str, str], transcript: Path) -> str:
    """Run the agent and keep its stdout as the transcript, even when it times out.

    An agent that exits non-zero without producing any output (expired token,
    unknown flag) raises with its stderr, so a failed launch is never mistaken
    for a wrong answer.
    """
    try:
        completed = subprocess.run(
            argv,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            env=dict(env),
            timeout=RUN_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as error:
        partial = error.stdout
        transcript.write_bytes(partial if isinstance(partial, bytes) else (partial or "").encode())
        raise
    transcript.write_text(completed.stdout, encoding="utf-8")
    if completed.returncode != 0 and not completed.stdout.strip():
        raise RuntimeError(
            f"{argv[0]} exited {completed.returncode} with no output: "
            f"{completed.stderr.strip()[-500:]}"
        )
    return completed.stdout


def files_changed(worktree: Path) -> list[str]:
    completed = subprocess.run(
        ["git", "status", "--porcelain"], cwd=worktree, capture_output=True, text=True, check=True
    )
    return sorted(line[3:] for line in completed.stdout.split("\n") if line)


def _events(lines: Iterable[str]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


# --- Copilot CLI ---------------------------------------------------------------------


def parse_copilot_events(lines: Iterable[str]) -> tuple[str, list[str], list[str]]:
    """``(final text, skills loaded, tool names used)`` from ``--output-format json`` lines."""
    text = ""
    skills: list[str] = []
    tools: list[str] = []
    for event in _events(lines):
        kind = event.get("type")
        data = event.get("data", {})
        if not isinstance(data, dict):
            continue
        if kind == "assistant.message" and isinstance(data.get("content"), str):
            text = data["content"] if not text else text + "\n" + data["content"]
        elif kind == "tool.execution_start":
            tool = str(data.get("toolName", ""))
            if tool and tool not in tools:
                tools.append(tool)
            if tool == "skill":
                arguments = data.get("arguments", {})
                skill = arguments.get("skill") if isinstance(arguments, dict) else None
                if isinstance(skill, str) and skill not in skills:
                    skills.append(skill)
    return text, skills, tools


def copilot_input_tokens(usage: Mapping[str, Any]) -> int:
    """The main thread's final call context from ``--usage-output-file``."""
    value = usage.get("lastCallInputTokens", 0)
    return int(value) if isinstance(value, int | float) else 0


def copilot_agent_tokens(usage: Mapping[str, Any]) -> tuple[int, int]:
    """``(main thread, all subagents)`` cumulative input tokens from ``agentMetrics``."""
    main = 0
    others = 0
    metrics = usage.get("agentMetrics", {})
    if not isinstance(metrics, dict):
        return 0, 0
    for agent, record in metrics.items():
        models = record.get("modelMetrics", {}) if isinstance(record, dict) else {}
        total = 0
        for model in models.values() if isinstance(models, dict) else []:
            used = model.get("usage", {}) if isinstance(model, dict) else {}
            value = used.get("inputTokens", 0) if isinstance(used, dict) else 0
            total += int(value) if isinstance(value, int | float) else 0
        if agent == "main":
            main += total
        else:
            others += total
    return main, others


class CopilotRunner:
    name = "copilot"
    dialect = Dialect.COPILOT

    def __init__(self, env: Mapping[str, str] | None = None) -> None:
        self._env = dict(env if env is not None else os.environ)

    def run(
        self, worktree: Path, prompt: str, *, agent: str | None, artefacts: Path, label: str
    ) -> RunResult:
        artefacts.mkdir(parents=True, exist_ok=True)
        usage_path = artefacts / f"{label}.usage.json"
        transcript = artefacts / f"{label}.copilot.jsonl"
        argv = [
            "copilot",
            "-p",
            prompt,
            "--allow-all",
            "-C",
            str(worktree),
            "-s",
            "--output-format",
            "json",
            "--usage-output-file",
            str(usage_path),
        ]
        if agent:
            argv += ["--agent", agent]
        if self._env.get("CCE_LLM_MODEL"):
            argv += ["--model", self._env["CCE_LLM_MODEL"]]
        env = dict(self._env)
        if env.get("COPILOT_GITHUB_TOKEN") and env.get("CCE_LLM_ISOLATE") == "1":
            env["COPILOT_HOME"] = str(artefacts / "home-copilot")
        stdout = capture(argv, cwd=None, env=env, transcript=transcript)
        text, skills, tools = parse_copilot_events(stdout.split("\n"))
        usage: dict[str, Any] = {}
        if usage_path.is_file():
            usage = json.loads(usage_path.read_text(encoding="utf-8"))
        main_tokens, subagent_tokens = copilot_agent_tokens(usage)
        return RunResult(
            text=text,
            skills_loaded=skills,
            tools_used=tools,
            input_tokens=copilot_input_tokens(usage),
            main_input_tokens=main_tokens,
            subagent_input_tokens=subagent_tokens,
            files_changed=files_changed(worktree),
            transcript_path=str(transcript),
        )


# --- Claude Code ---------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ClaudeParse:
    text: str
    skills: list[str]
    tools: list[str]
    input_tokens: int
    main_input_tokens: int
    subagent_input_tokens: int


def _usage_total(message: Mapping[str, Any]) -> int:
    usage = message.get("usage", {})
    if not isinstance(usage, dict):
        return 0
    total = 0
    for key in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"):
        value = usage.get(key, 0)
        total += int(value) if isinstance(value, int | float) else 0
    return total


def parse_claude_events(lines: Iterable[str]) -> ClaudeParse:
    """Final text, skills, tools and token totals from ``stream-json`` lines."""
    text = ""
    skills: list[str] = []
    tools: list[str] = []
    input_tokens = 0
    main_total = 0
    subagent_total = 0
    for event in _events(lines):
        kind = event.get("type")
        if kind == "result" and isinstance(event.get("result"), str):
            text = event["result"]
        if kind != "assistant":
            continue
        message = event.get("message", {})
        if not isinstance(message, dict):
            continue
        if event.get("parent_tool_use_id"):
            subagent_total += _usage_total(message)
            continue
        for block in message.get("content", []):
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use":
                tool = str(block.get("name", ""))
                if tool and tool not in tools:
                    tools.append(tool)
                if tool == "Skill":
                    skill = (
                        block.get("input", {}).get("skill")
                        if isinstance(block.get("input"), dict)
                        else None
                    )
                    if isinstance(skill, str) and skill not in skills:
                        skills.append(skill)
        total = _usage_total(message)
        main_total += total
        if total:
            input_tokens = total
    return ClaudeParse(text, skills, tools, input_tokens, main_total, subagent_total)


class ClaudeRunner:
    name = "claude"
    dialect = Dialect.CLAUDE

    def __init__(self, env: Mapping[str, str] | None = None) -> None:
        self._env = dict(env if env is not None else os.environ)

    def run(
        self, worktree: Path, prompt: str, *, agent: str | None, artefacts: Path, label: str
    ) -> RunResult:
        artefacts.mkdir(parents=True, exist_ok=True)
        transcript = artefacts / f"{label}.claude.jsonl"
        argv = [
            "claude",
            "-p",
            prompt,
            "--output-format",
            "stream-json",
            "--verbose",
            "--permission-mode",
            "bypassPermissions",
            "--setting-sources",
            "project",
        ]
        if agent:
            argv += ["--agent", agent]
        if self._env.get("CCE_LLM_MODEL"):
            argv += ["--model", self._env["CCE_LLM_MODEL"]]
        env = {key: value for key, value in self._env.items() if key != "CLAUDECODE"}
        if env.get("CLAUDE_CODE_OAUTH_TOKEN"):
            env["CLAUDE_CONFIG_DIR"] = str(artefacts / "home-claude")
        stdout = capture(argv, cwd=worktree, env=env, transcript=transcript)
        parsed = parse_claude_events(stdout.split("\n"))
        return RunResult(
            text=parsed.text,
            skills_loaded=parsed.skills,
            tools_used=parsed.tools,
            input_tokens=parsed.input_tokens,
            main_input_tokens=parsed.main_input_tokens,
            subagent_input_tokens=parsed.subagent_input_tokens,
            files_changed=files_changed(worktree),
            transcript_path=str(transcript),
        )


def runner_for(name: str) -> AgentRunner:
    runners: dict[str, AgentRunner] = {"copilot": CopilotRunner(), "claude": ClaudeRunner()}
    if name not in runners:
        raise ValueError(f"unknown runtime {name!r}; choose copilot or claude")
    return runners[name]


def sequence(items: Sequence[str]) -> list[str]:
    return list(items)
