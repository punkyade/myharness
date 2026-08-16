# Quickstart — 5 Minutes to Your First Harness

**What you will have at the end:** a working `.claude/agents/` directory with 3–5 domain-specialized agents, generated from a single-sentence prompt, ready to run on a sample task.

**Prerequisites:**
- Claude Code **v2.x or later** (`claude --version` should return `2.x` or higher)
- A shell that persists `export` across commands (bash, zsh, or fish)
- Network access to `github.com` and `api.anthropic.com`

---

## Step 1 — Add the marketplace

```bash
claude plugin marketplace add punkyade/myharness
```

**What this does:** Registers the `myharness-marketplace` marketplace so Claude Code can discover the plugin.

**Expected output:** `Added marketplace: punkyade/myharness`

---

## Step 2 — Install the plugin and enable the experimental flag

```bash
claude plugin install myharness@myharness-marketplace
export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1
```

*(To persist the flag across shell sessions, append the `export` line to `~/.zshrc` or `~/.bashrc`.)*

**What this does:** Installs the `myharness` plugin from the `myharness-marketplace` marketplace, then enables Agent Teams — the Claude Code API this plugin uses to orchestrate multi-agent workflows. See [`docs/experimental-dependency.md`](./experimental-dependency.md) for why the flag is required.

**Failure FAQ #1 — `AGENT_TEAMS not found` / teams don't instantiate**
**Cause:** Claude Code version is older than v2.x (Agent Teams was introduced in v2.0).
**Fix:** Run `claude --version`. If below 2.0, upgrade via `npm i -g @anthropic-ai/claude-code` (or your distribution's installer), then repeat Step 2.

---

## Step 3 — Generate a harness from one sentence

```bash
claude "build a harness for a fintech risk-assessment team"
```

**What this does:** Invokes the `/myharness:harness` meta-skill, which analyzes your domain sentence and scaffolds a team of specialized agents plus their skills into `.claude/agents/` and `.claude/skills/` in the current directory.

**Try these alternate prompts** — any of them work:
- `claude "하네스 구성해줘 — 핀테크 리스크 평가 팀"` (Korean also works)
- `claude "build a harness for an e-commerce fraud-detection workflow"`
- `claude "design an agent team for technical due diligence on open-source repos"`

**Expected output:** A streaming plan, then confirmation that 3–5 agent `.md` files and their skills were written.

**Failure FAQ #2 — The Korean prompt returns nothing / the English one succeeds but Korean doesn't**
**Cause:** Locale or tokenizer misrouting; the skill matches on Korean trigger words ("하네스 구성"), which are built into the skill definition.
**Fix:** If Korean fails, re-run with the English prompt above — the underlying skill is identical. If both fail, jump to Failure FAQ #3.

---

## Step 4 — Verify the generated files

```bash
ls -la .claude/agents/
ls -la .claude/skills/
```

**Expected output:** 3–5 files per directory, with names reflecting your domain (e.g. `risk-analyst.md`, `compliance-reviewer.md`, `portfolio-monitor.md` for the fintech example).

**Failure FAQ #3 — "Nothing was generated" / directories are empty**
**Cause:** The plugin is not actually installed or is not active in the current project.
**Fix:** Run `claude plugin list`. If `myharness@myharness-marketplace` is absent, repeat Step 2. If present but inactive, run `claude plugin enable myharness@myharness-marketplace`, then repeat Step 3.

---

## Step 5 — Run a sample task against the new team

Hand a realistic ticket-style prompt to your fresh team:

```bash
claude "Ticket FIN-427: A new corporate customer (mid-cap manufacturer, \$80M revenue, South Korea) has applied for a \$5M working-capital line. Produce a risk assessment covering (1) credit-history red flags, (2) sector concentration vs. our existing book, (3) regulatory exposure (KFTC, FSC). Output: a 1-page memo with a go/no-go recommendation."
```

**What this does:** Claude Code detects the new agents in `.claude/agents/`, routes the task through the team patterns the harness generated (typically Producer-Reviewer or Expert Pool for risk work), and returns a structured memo.

**Failure FAQ #4 — "The team doesn't execute / only one agent responds"**
**Cause:** `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` was set in the shell that ran Step 3 but not in the shell running Step 5 (happens when opening a new terminal).
**Fix:** Re-export in the current shell: `export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`, then re-run Step 5. To make it permanent, add the line to your shell rc file.

**Failure FAQ #5 — "Too many API calls / cost anxiety"**
**Cause:** Multi-agent teams can fan out to 5+ parallel Claude calls per task. A single complex ticket can consume a large number of tokens.
**Fix:** Limit to a single task per run (don't chain multiple invocations with `&&`), and use the `--max-turns` flag if your Claude Code version supports it.

---

## You're done

At this point you should have:

- [x] A `.claude/agents/` directory with domain-specialized agents
- [x] A `.claude/skills/` directory with their supporting skills
- [x] One successful sample-task execution
- [x] A working `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` environment

**Next read:** [`docs/experimental-dependency.md`](./experimental-dependency.md) — why the flag is needed and what happens when it changes.
