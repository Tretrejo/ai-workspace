---
name: agentic-coding-guide
description: >
  Best practices for running Claude Code and AI coding agents effectively and safely
  on real projects. Use this skill whenever someone is setting up Claude Code, asking
  how to give a coding agent more autonomy, dealing with a coding agent that keeps
  losing session state or re-asking for login credentials, wanting to write a CLAUDE.md
  file, asking what permissions to give their agent, comparing Claude Code to Lovable or
  Cursor, wondering if "YOLO mode" is safe, or asking why their coding agent keeps
  making unexpected changes. Also trigger for phrases like "agentic coding," "coding
  agent setup," "Claude Code settings," "AI programmer," "autonomous coding," or
  "my agent keeps breaking things." Always use this skill before recommending any
  specific Claude Code configuration — the right setup depends on the project type.
---
# Agentic Coding Guide Skill
Get the most out of Claude Code and AI coding agents on real projects, not just demos.
---
## The Most Important Settings
### 1. Enable "Persist Preview Sessions"
Location: Claude Code desktop app → Settings → Preview
By default, Claude Code flushes all cookies, localStorage, and session state every time
it restarts a local server. Enable this toggle to preserve browser state across restarts.
Essential for any project with authentication, forms, or stateful UI.
### 2. Write a CLAUDE.md File
The single most impactful habit. Create a CLAUDE.md in your project root containing:
```
# Project: [Name]
## What this is
[2 sentences]
## Tech stack
- Language / Framework / Database / Key libraries
## Critical rules
- Never modify /migrations without running the migration after
- Always run tests before committing
- [Your project-specific rules]
## How to run locally
[exact commands]
## What Claude should do before editing anything
Inspect relevant files and explain the plan. Don't touch unrelated files.
```
Ask Claude Code to write the initial CLAUDE.md for you — tell it about the project
and it will draft it. Update it as the project grows.
**Scoping**: CLAUDE.md works at three levels:
- `./CLAUDE.md` — this project only
- `~/.claude/CLAUDE.md` — all your projects
- Shared team file — across the organization
### 3. Set Permission Boundaries
Define in CLAUDE.md what Claude can do freely, what needs approval, and what is off-limits:
```
## Permissions
### Claude can do freely
- Read any file
- Write to /src, /tests, /docs
- Run tests and linting
- Install packages (with package.json/requirements.txt update)
### Claude must ask before doing
- Modifying database schema files
- Changing environment variables or config
- Deleting any file
### Claude must never do
- Access production environment
- Run destructive SQL (DROP TABLE etc.)
- Commit or push to git
- Send emails or make external API calls
```
---
## When YOLO Mode Is Fine (and When It Isn't)
**Fine when:**
- Working in a feature branch, not main
- Good test coverage exists (Claude verifies its own changes)
- Destructive operations are impossible by design
- You can `git reset` if needed
**Don't use when:**
- Claude has production credentials
- No test suite exists
- You're modifying shared infrastructure
The key insight: if a destructive action is *possible*, the problem is the infrastructure,
not the permission setting. Fix the access control, then give Claude more autonomy.
---
## Giving Claude Better Context
Before any significant change, start with:
```
Before you make any changes, read [relevant files] and tell me:
1. What you think the current behavior is
2. What you would change and why
3. What you won't touch
Don't modify anything until I confirm.
```
Be specific about what kind of help you want:
- **patch** — fix this specific thing
- **review** — tell me what's wrong
- **plan** — outline what you'd do before doing it
- **diagnosis** — figure out why X is failing
---
## Memory Between Sessions
By default Claude Code starts cold every session. Fix this with:
1. **CLAUDE.md** — project context loads automatically every session
2. **Session summaries** — at end of session, ask Claude to add a progress summary to CLAUDE.md
3. **claude-mem plugin** — captures session activity, makes history available later
---
## Common Failure Modes
**"Claude keeps logging me out"** → Enable Persist Preview Sessions.
**"Claude touched files I didn't want it to"** → Add explicit off-limits rules to CLAUDE.md.
**"Changes work in isolation but break other parts"** → Add test run command to CLAUDE.md,
tell Claude to run tests after each change.
**"Claude did something destructive"** → Review what credentials and database access it has.
Remove production access entirely.
**"Claude starts from scratch every session"** → Add session summary to CLAUDE.md
at the end of each session.
