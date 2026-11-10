# Agent Skills

A collection of reusable skills for AI coding agents (OpenCode / Claude-style `SKILL.md` format).

Each skill lives in its own folder and contains a `SKILL.md` with YAML frontmatter
(`name`, `description`) plus optional `references/` files loaded on demand.

## Skills

| Skill | Description |
|---|---|
| [autonomous-agentic-development-cycle](./autonomous-agentic-development-cycle/) | Zero-interruption engineering pipeline: spec → architecture → QA plan → implementation → release, with clean-context Quality Gates (a single auditor, then a Court of Three Agents) blocking each phase transition. |

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
