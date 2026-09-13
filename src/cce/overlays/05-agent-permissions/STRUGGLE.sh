#!/usr/bin/env bash
# Prints, and never runs, the global-flag command lines you would need to
# reproduce the three S05 roles without custom agent files.
set -euo pipefail

cat <<'TEXT'
Without custom agents, each role is a different way of starting Copilot:

  researcher   copilot --deny-tool write --deny-tool shell
  author       copilot --deny-tool shell --deny-tool web
  validator    copilot --deny-tool write --allow-tool 'shell(python3:*)'

These flags are per-session: they apply to the process you start and to
nothing else. Deny always wins over allow, so a tool denied at start-up
cannot be re-enabled later in that session.

Switching role therefore means quitting Copilot and restarting it with a
different set of flags.

A custom agent file carries the same allowlist per role instead, and you
switch role inside one session with /agent:

  .github/agents/researcher.agent.md
  .github/agents/author.agent.md
  .github/agents/validator.agent.md
TEXT
