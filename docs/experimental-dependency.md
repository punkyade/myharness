# Experimental Flag Dependency

> **Status:** Active · **Maintainer:** punkyade · **Last updated:** 2026-08-17

This document explains why `myharness` requires `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`, and what is likely to happen to that flag over time.

> This is a single-maintainer fork. Nothing here is a support commitment or an SLA — it is a description of a technical dependency and how it will probably evolve.

---

## Why the flag is required

`myharness` is a meta-skill built on top of Claude Code's **Agent Teams API**. These primitives are invoked whenever the generated harness runs in agent-team mode:

| Primitive | Purpose | Flag gated? |
|-----------|---------|-------------|
| `TeamCreate` | Instantiates a multi-agent team with shared context | **Yes** |
| `SendMessage` | Routes messages between team members | **Yes** |
| `TaskCreate` | Creates shared task entries inside a team | **Yes** |
| `Agent` tool | Single-agent dispatch (subagent mode) | No (GA) |

All flag-gated primitives require:

```bash
export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1
```

Without this variable set in the shell that launches `claude`, generated teams fall back to single-agent execution. That silently degrades the Pipeline, Fan-out/Fan-in, Supervisor, and Hierarchical Delegation patterns — they will appear to run, but without real team coordination.

**Subagent mode is unaffected.** If you cannot enable experimental flags, design your harness in subagent mode (Phase 2-1 in `SKILL.md`); it uses only the GA `Agent` tool.

---

## Dependency graph

```
myharness (v2.0.0)
  └── Agent Teams API (Claude Code)
        ├── TeamCreate            ← EXPERIMENTAL_AGENT_TEAMS=1
        ├── SendMessage           ← EXPERIMENTAL_AGENT_TEAMS=1
        ├── TaskCreate            ← EXPERIMENTAL_AGENT_TEAMS=1
        └── Agent (invoke)        ← GA (flag-independent)
```

---

## Likely futures

### Scenario A — Flag removed (Agent Teams promoted to GA)

**Signal:** the Claude Code changelog announces Agent Teams GA, or the binary stops requiring the env var.

**Impact:** positive and non-breaking. Generated `.claude/agents/*.md` and `.claude/skills/*` files are plain Markdown and stay valid; the `export` line simply becomes unnecessary. The README and quickstart would drop the flag instructions.

### Scenario B — Managed Agents becomes the primary path

**Signal:** Anthropic ships a stable server-side managed-agent execution surface.

**Impact:** this plugin's client-side team orchestration does not translate automatically. The design-time output (agent definitions and skills) remains useful; the runtime wiring would need an adapter. Not planned unless it becomes necessary.

### Scenario C — Breaking change to the experimental API

**Signal:** a renamed env var, or a changed `TeamCreate` / `SendMessage` / `TaskCreate` signature. Experimental APIs can change without a deprecation window.

**Impact:** team mode breaks until the affected call sites in `skills/harness/` and its references are updated. Pinning your Claude Code version avoids surprise breakage. There is no automated compatibility CI on this repository, so detection is manual — if you hit this, please open an issue.

---

## Can I use this without enabling the flag?

Yes, in a reduced form. Run the meta-skill to scaffold `.claude/agents/` and `.claude/skills/` — generation itself does not require team mode — then run the generated harness in **subagent mode**, which uses only GA primitives. You lose inter-agent messaging and shared task lists; you keep the specialized agent definitions and skills.

---

**Related:** [`docs/quickstart.md`](./quickstart.md) — install walkthrough.
