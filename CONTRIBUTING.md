# Contributing to myharness

**myharness** is a personal fork of [revfactory/harness](https://github.com/revfactory/harness) — a Claude Code meta-skill that designs agent teams and generates the skills they use.

This is a single-maintainer repository. Issues and PRs are welcome, but there is **no response-time commitment** — expect best-effort, spare-time replies. If you need an actively maintained version with a contributor community, use [the upstream project](https://github.com/revfactory/harness) instead.

---

## How to Contribute

### Bug report

Open an issue using the **Bug report** form (`.github/ISSUE_TEMPLATE/bug_report.yml`). Include your Claude Code version, the `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` flag state, reproduction steps, expected vs. actual behavior, and OS.

### Feature request

Open an issue using the **Feature request** form. A short "what problem does this solve" paragraph is enough. If your idea extends or replaces one of the 6 team-architecture patterns, say which one.

### Question

Open an issue using the **Question** form.

### Security

Do **not** open a public issue for anything that could be abused. Report it privately through [GitHub's private vulnerability reporting](https://github.com/punkyade/myharness/security/advisories/new) on this repository.

> If the issue also affects upstream, please report it to [revfactory/harness](https://github.com/revfactory/harness) as well — most of the skill content originates there.

---

## Development Setup

### Prerequisites

- Claude Code `v2.x` (Agent Teams API required)
- Git

### Environment flag

myharness relies on Claude Code's experimental Agent Teams feature. Set the flag in your shell profile or per session:

```bash
export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1
```

This dependency is tracked in [`docs/experimental-dependency.md`](docs/experimental-dependency.md).

### Testing changes locally

To test edits without publishing to the marketplace, add this checkout as a local marketplace source:

```bash
# From the parent directory of your checkout
/plugin marketplace add ./myharness
/plugin install myharness@myharness-marketplace
```

Alternatively, copy the skill straight into your user skills directory:

```bash
cp -r skills/harness ~/.claude/skills/harness
```

### Running the meta-skill

```bash
claude "build a harness for a fintech risk-assessment team"
```

Scaffolded agents and skills land under `.claude/agents/` and `.claude/skills/` in the target project.

### Validating your changes

There is no CI on this repository. Before opening a PR, check by hand:

- Both JSON manifests parse: `python -c "import json,sys; [json.load(open(f, encoding='utf-8')) for f in sys.argv[1:]]" .claude-plugin/plugin.json .claude-plugin/marketplace.json`
- Every skill has `name` and `description` in its YAML frontmatter
- `SKILL.md` stays under 500 lines; reference files over 300 lines carry a table of contents
- Relative links in changed Markdown resolve to files that exist
- Version strings agree across `plugin.json`, `marketplace.json`, and the three README badges

---

## Pull Request Guidelines

### Branch naming

Use the `type/short-description` shape:

| Prefix | Use for | Example |
|--------|---------|---------|
| `feat/` | New user-visible capability | `feat/expert-pool-variance-mode` |
| `fix/` | Bug fix | `fix/agent-teams-flag-detection` |
| `docs/` | Docs-only changes | `docs/quickstart-install-command` |
| `refactor/` | Internal structure, no behavior change | `refactor/skill-loader-split` |
| `chore/` | Housekeeping | `chore/update-references` |

### Commit messages

Korean and English are both fine — write in whichever you are more precise in.

We follow a light variant of **Conventional Commits** that maps to SemVer:

| Commit type | SemVer impact | Example |
|-------------|---------------|---------|
| `feat!:` or `BREAKING CHANGE:` in footer | **major** | `feat!: rename pattern "Supervisor" → "Orchestrator"` |
| `feat:` | **minor** | `feat: add Producer-Reviewer variance metric` |
| `fix:` | **patch** | `fix: correct flag detection on zsh` |
| `docs:` / `chore:` / `refactor:` / `test:` | no bump | `docs: clarify install command` |

Korean summaries are fine: `feat: 전문가 풀 패턴에 분산 지표 추가`.

### PR body

`.github/PULL_REQUEST_TEMPLATE.md` pre-fills the body. Please fill in Summary, Motivation, Scope, Tests, CHANGELOG, and SemVer impact.

### Releases

Tags follow `vMAJOR.MINOR.PATCH` (e.g. `v2.1.0`), cut from `main` once `CHANGELOG.md` is updated. There is no fixed release cadence.

---

## Code of Conduct

This project follows the **Contributor Covenant v1.4** — in short:

- Be welcoming and inclusive. Assume good intent.
- No harassment, no personal attacks, no discriminatory language.
- Critique ideas, not people.

Full text: <https://www.contributor-covenant.org/version/1/4/code-of-conduct/>

Report violations privately via [GitHub private vulnerability reporting](https://github.com/punkyade/myharness/security/advisories/new) or by direct message to [@punkyade](https://github.com/punkyade).

---

## License

By contributing, you agree that your contributions will be licensed under the same license as this repository — Apache 2.0. See [`LICENSE`](./LICENSE) and [`NOTICE`](./NOTICE).
