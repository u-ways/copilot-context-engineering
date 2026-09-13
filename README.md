# copilot-context-engineering

Should a rule go into repository instructions, an Agent Skill, or a custom agent? This repository answers that question for GitHub Copilot CLI by letting you run it. The `cce` command prepares six scenarios on top of a real public engineering framework. Each scenario is a git worktree with a small, deliberate set of Copilot customisation files and a short guide, so you can send the same prompt under different set-ups and watch what changes in `/context`, `/usage` and `/diff`.

## Which should I use?

| | Instructions | Skill | Agent |
| --- | --- | --- | --- |
| Always loaded? | Yes | No, only when relevant | No, dispatched |
| Adaptive? | No, static text | Yes | Yes |
| Size concern? | Paid on every request | Only when matched | Separate context |
| Can you restrict its tools? | No | No | Yes, a per-role `tools` list (scenario 05) |

TL;DR: Instructions = "Always follow these rules." Skill = "When doing X, here is how." Agent = "Go do this and come back."

## What you will see

| # | Scenario | Lesson | Guide |
| --- | --- | --- | --- |
| 01 | instructions-timeless | Instructions hold durable rules, not changing repo state | [01-instructions-timeless.md](docs/scenarios/01-instructions-timeless.md) |
| 02 | instructions-context-cost | Task runbooks in instructions are paid on every request | [02-instructions-context-cost.md](docs/scenarios/02-instructions-context-cost.md) |
| 03 | skills-on-demand | The same procedures as skills cost nothing until matched | [03-skills-on-demand.md](docs/scenarios/03-skills-on-demand.md) |
| 04 | skills-description-routing | Descriptions route skills | [04-skills-description-routing.md](docs/scenarios/04-skills-description-routing.md) |
| 05 | agent-permissions | Permissions belong to the role | [05-agent-permissions.md](docs/scenarios/05-agent-permissions.md) |
| 06 | agent-context-isolation | Delegate when you need the result, not the investigation | [06-agent-context-isolation.md](docs/scenarios/06-agent-context-isolation.md) |

Every scenario takes a few minutes, shows its numbers in Copilot's own `/context` and `/usage` output, and ends with a reset.

## Get started

1. Follow [docs/PREREQUISITES.md](docs/PREREQUISITES.md) to install `cce` and check your machine.
2. Run `cce setup` once, then open the [walkthrough](docs/scenarios/README.md).

## Documentation

- [Walkthrough](docs/scenarios/README.md): the six scenarios in order, and the protocol shared by every run
- [Prerequisites](docs/PREREQUISITES.md): requirements, install, `cce doctor` and the workspace
- [Presenting](docs/presenting.md): running the scenarios as a talk, with an optional herdr layout
- [Contributing](CONTRIBUTING.md): how the tool works inside, exit codes and the development recipes
- [Decisions](docs/adrs/README.md): the ADRs behind every command; they win over every other document
- [Releasing](docs/RELEASING.md): how a release is cut and how `cce update` finds it

## Licence

MIT, see [LICENSE](LICENSE). The upstream framework content is fetched at runtime at a pinned commit and is not redistributed here.
