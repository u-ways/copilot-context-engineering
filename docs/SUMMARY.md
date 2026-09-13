# Summary

Should a rule go into repository instructions, an Agent Skill, or a custom agent? Each row of the table names one property of the three mechanisms, and its last column links the scenarios that demonstrate it.

| | Instructions | Skill | Agent | Shown in |
| --- | --- | --- | --- | --- |
| Always loaded? | Yes | No, only when relevant | No, dispatched | [02](scenarios/02-instructions-context-cost.md), [03](scenarios/03-skills-on-demand.md), [06](scenarios/06-agent-context-isolation.md) |
| Adaptive? | No, static text | Yes | Yes | [01](scenarios/01-instructions-timeless.md), [04](scenarios/04-skills-description-routing.md), [05](scenarios/05-agent-permissions.md) |
| Size concern? | Paid on every request | Only when matched | Separate context | [02](scenarios/02-instructions-context-cost.md), [03](scenarios/03-skills-on-demand.md), [06](scenarios/06-agent-context-isolation.md) |
| Can you restrict its tools? | No | No | Yes, a per-role `tools` list | [05](scenarios/05-agent-permissions.md) |

TL;DR: Instructions = "Always follow these rules." Skill = "When doing X, here is how." Agent = "Go do this and come back."

The scenarios themselves, in order, are in the [walkthrough](scenarios/README.md).
