# Agent Skills

A collection of reusable skills for AI coding agents (OpenCode / Claude-style `SKILL.md` format).

Each skill lives in its own folder and contains a `SKILL.md` with YAML frontmatter
(`name`, `description`) plus optional `references/` files loaded on demand.

## Skills

| Skill | Description |
|---|---|
| [autonomous-agentic-development-cycle](./autonomous-agentic-development-cycle/) | Zero-interruption engineering pipeline: spec → architecture → QA plan → implementation → release, with clean-context Quality Gates (a single auditor, then a Court of Three Agents) blocking each phase transition. |
| [agent-pipeline](./agent-pipeline/) | 11-stage task cycle run by an orchestrator: one clean-context subagent per phase, four review gates each passed by a single clean-context reviewer. Task sizes S/M/L, neighbouring-case and breaking-input checks, tests instead of debate before code, and a dependency-free Python script that checks the task documents before each gate. See its README for results and limits. |

## Install

Copy a skill folder into your agent's skills directory:

```bash
# project-local
cp -R autonomous-agentic-development-cycle .agents/skills/

# global (OpenCode)
cp -R autonomous-agentic-development-cycle ~/.config/opencode/skills/
```

Agents pick the skill up automatically once its `description` matches the task —
or you can load it explicitly.

### For an agent given this link

If you are an AI agent asked to install a skill from this repository, clone it
and copy the **whole** skill folder (it may contain `references/` and
`scripts/` that the skill needs):

```bash
git clone --depth 1 https://github.com/FlexGodX/agent-skills.git /tmp/agent-skills
mkdir -p ~/.agents/skills ~/.claude/skills
rm -rf ~/.agents/skills/agent-pipeline
cp -R /tmp/agent-skills/agent-pipeline ~/.agents/skills/
ln -sfn ../../.agents/skills/agent-pipeline ~/.claude/skills/agent-pipeline
python3 ~/.agents/skills/agent-pipeline/scripts/test_check_artifacts.py
```

Replace `agent-pipeline` with the skill you need; the last line applies only to
skills that ship a `scripts/` test. Other harnesses use their own directory
(`~/.config/opencode/skills/`, or `.agents/skills/` inside a project).

## Format

```text
<skill-name>/
├── SKILL.md            # frontmatter: name + description, then the instructions
└── references/         # optional deeper material, linked from SKILL.md
    └── *.md
```

Keep `SKILL.md` as the short operational core; move long prompt templates and
checklists into `references/` so they only load when needed.

## License

MIT
