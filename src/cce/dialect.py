"""Translate a rendered overlay from Copilot CLI's layout to Claude Code's (ADR-0010).

The translator is deliberately small: it moves files to the paths Claude Code
reads and rewrites agent tool aliases. Every tool-alias literal lives here.
"""

import re
from collections.abc import Sequence
from enum import StrEnum
from typing import TYPE_CHECKING

from cce.manifest import as_list, split_front_matter

if TYPE_CHECKING:
    from cce.render import PlannedFile

COPILOT_TOOLS: tuple[str, ...] = ("read", "edit", "search", "execute", "web", "agent")

CLAUDE_TOOLS: dict[str, tuple[str, ...]] = {
    "read": ("Read",),
    "search": ("Grep", "Glob"),
    "edit": ("Edit", "Write"),
    "execute": ("Bash",),
    "web": ("WebFetch", "WebSearch"),
    "agent": ("Agent",),
}

_INSTRUCTIONS_RE = re.compile(r"^\.github/copilot-instructions(?P<suffix>(?:\.[a-z0-9-]+)*)\.md$")
_SKILL_PREFIX = ".github/skills/"
_AGENT_RE = re.compile(r"^\.github/agents/(?P<name>[a-z][a-z0-9-]*)\.agent\.md$")


class Dialect(StrEnum):
    """Which coding agent the rendered overlay targets."""

    COPILOT = "copilot"
    CLAUDE = "claude"


def translate(planned: Sequence[PlannedFile], dialect: Dialect) -> list[PlannedFile]:
    """Return the plan for ``dialect``; the Copilot dialect is the identity."""
    if dialect is Dialect.COPILOT:
        return list(planned)
    return [_to_claude(file) for file in planned]


def claude_tools(copilot_tools: Sequence[str]) -> list[str]:
    """Map Copilot tool aliases to Claude Code tool names, preserving order."""
    mapped: list[str] = []
    for alias in copilot_tools:
        for tool in CLAUDE_TOOLS[alias]:
            if tool not in mapped:
                mapped.append(tool)
    return mapped


def _to_claude(file: PlannedFile) -> PlannedFile:
    from cce.render import PlannedFile  # local import: render imports this module

    instructions = _INSTRUCTIONS_RE.match(file.dest)
    if instructions:
        return PlannedFile(
            f"CLAUDE{instructions.group('suffix')}.md", file.content, file.executable
        )
    if file.dest.startswith(_SKILL_PREFIX):
        return PlannedFile(
            ".claude/skills/" + file.dest[len(_SKILL_PREFIX) :], file.content, file.executable
        )
    agent = _AGENT_RE.match(file.dest)
    if agent:
        return PlannedFile(
            f".claude/agents/{agent.group('name')}.md", _claude_agent(file.content), file.executable
        )
    return file


def _claude_agent(content: bytes) -> bytes:
    fields, body = split_front_matter(content.decode("utf-8"))
    name = fields["name"]
    description = fields["description"]
    tools = claude_tools(as_list(fields.get("tools", [])))
    assert isinstance(name, str) and isinstance(description, str)
    quoted = '"' + description.replace("\\", "\\\\").replace('"', '\\"') + '"'
    header = f"---\nname: {name}\ndescription: {quoted}\ntools: {', '.join(tools)}\n---\n"
    return (header + body).encode("utf-8")
