---
name: multi-agent-architect
description: >
  Design, plan, and build multi-agent AI systems. Use this skill whenever someone
  wants to build an agent system, asks which AI framework to use (CrewAI, LangGraph,
  Anthropic SDK, AutoGen), wants to split a complex task across multiple AI agents,
  asks how agents should "talk to each other," wants to add memory to an agent, or
  is debugging why their agent workflow isn't working in production. Also trigger for
  phrases like "orchestrate agents," "multi-agent pipeline," "agent handoffs,"
  "agent roles," "agentic workflow," or "my agent keeps losing context." Always use
  this skill before recommending any specific framework — context determines the
  right architecture every time.
---
# Multi-Agent Architect Skill
Design multi-agent systems that actually work in production — not just in demos.
The central fact in 2026: 79% of enterprises say they've adopted AI agents, but only
11% run them in production. The gap is almost always architecture and skills, not model
quality. This skill closes that gap.
---
## Step 1: Understand What You're Actually Building
Before recommending any framework, ask:
1. **What is the end goal?** (A report? A deployed service? A one-off script?)
2. **Is the task linear or branching?** (Steps always in sequence? Or decisions that split the path?)
3. **Does it need to run automatically, or is a human in the loop?**
4. **What tools does it need?** (Web search, code execution, file access, APIs?)
5. **How critical is it?** (Experiment vs. customer-facing production?)
Use their answers to pick the architecture tier below.
---
## Step 2: Pick the Right Architecture Tier
### Tier 0 — Don't Build an Agent (Most Common Right Answer)
If the task can be done with a single well-crafted prompt + tool call, do that.
Agents add latency, cost, and failure modes. Start here and only escalate if needed.
- "Summarize this document" → single Claude call
- "Analyze this CSV and chart it" → Claude Code session
### Tier 1 — Single Agent with Tools
One agent + multiple tools (search, code execution, file read/write).
- Best for: research tasks, data analysis, report generation
- Framework: Direct Anthropic API with tool_use, or Claude Code
- When it breaks: when the task needs parallel work or specialized sub-expertise
### Tier 2 — Sequential Multi-Agent (Crew)
Multiple specialized agents in a pipeline. Each has one job and passes output to the next.
- Best for: content pipelines (research → write → edit), data workflows (extract → transform → validate)
- Framework: **CrewAI** — fastest to build, works in an afternoon
- When it breaks: when steps need to talk back to earlier steps, or run in parallel
### Tier 3 — Stateful Graph (Production)
Agents as nodes in a graph. Conditional branching, loops, checkpointing, human approval.
- Best for: enterprise workflows, regulated industries, anything that must be auditable
- Framework: **LangGraph** — steeper curve but the production standard (used at Klarna, Uber)
- When it breaks: rarely — this is the most robust option
### Tier 4 — Fully Autonomous / Self-Improving
Agents that spawn sub-agents, reflect on their own outputs, and improve over time.
- Best for: research acceleration, complex code generation at scale
- Framework: **Anthropic Agent SDK** (extended thinking + computer use) or **AutoGen**
- Warning: Highest complexity and cost. Pilot in a sandbox first, always.
---
## Step 3: Framework Selection Card
| Situation | Best Framework | Why |
|---|---|---|
| Prototyping, need it working today | CrewAI | Role-based, opinionated, minimal boilerplate |
| Production, needs audit trails | LangGraph | Graph state, checkpointing, LangSmith monitoring |
| Claude-native, using extended thinking | Anthropic SDK | Tool-use-first, minimal abstraction |
| Research / debate between agents | AutoGen | Built for agent-to-agent argumentation |
| Complex Python typing + evals | Pydantic AI | Strong schema enforcement, eval loop built in |
**The 30-point rule**: Framework choice can swing benchmark performance by up to 30
percentage points on identical models. Don't underestimate this decision.
---
## Step 4: Design the Agent Roles
For each agent in the system, define:
- **Role**: What is this agent's job title? (Researcher, Writer, Validator, Orchestrator)
- **Goal**: Single sentence — what does it produce?
- **Tools**: Which tools does it have access to? (Fewer is better — tool overload degrades quality)
- **Output format**: What does it hand to the next agent?
- **Failure mode**: What does it do if it can't complete its task?
**Key principle**: A single agent given too many tools performs worse. Specialized agents
with 2–4 tools each consistently outperform generalist agents with 10+ tools.
---
## Step 5: Design the Memory Architecture
Multi-agent systems need memory at multiple levels:
### Short-term (In-session)
- The conversation/context window: what the agent knows right now
- Managed automatically by most frameworks
- Problem: lost when the session ends
### Long-term (Cross-session)
- Stored externally in a vector database (Qdrant recommended) or structured store
- Retrieved by semantic similarity, not exact match
- Key pattern: **non-regressivity** — new actions should build on validated past actions,
  not contradict them
### Shared (Cross-agent)
- State that multiple agents in the same pipeline can read/write
- LangGraph handles this via its state graph
- CrewAI handles this via shared memory objects
**The enterprise failure pattern**: Standard RAG retrieves relevant documents — but stops
there. It doesn't know about time, relationships between decisions, or what was validated
before. If your agent needs to "remember what it decided last Tuesday," you need a decision
context graph, not plain RAG.
### Memory Architecture Checklist
```
□ What does each agent need to remember within this session?
□ What needs to persist between sessions?
□ What do multiple agents need to share?
□ How do we prevent agents from contradicting past validated decisions?
□ What is the maximum acceptable staleness of retrieved context?
```
---
## Step 6: Pilot Plan (Required Before Production)
Every multi-agent build needs a pilot:
```
🧪 PILOT PLAN
- Scope: [specific small task to run first — not the full workflow]
- Success metric: [measurable outcome — accuracy %, time saved, error rate]
- Sandbox: [run on non-production data/systems first]
- Human review step: [who validates the output before it goes live?]
- Rollback: [how to stop the agent if something goes wrong]
- Scale threshold: [what result justifies full rollout?]
```
**Do not skip this.** The most common production failure is skipping the pilot and
discovering failure modes only after the agent has processed thousands of real records.
---
## Output Format
Produce a **Multi-Agent Architecture Plan** structured as:
```
## System Overview
[2-sentence description of what the system does and why]
## Architecture Tier
[Tier 0–4 with justification]
## Framework
[Recommended framework with specific reason]
## Agent Roster
[For each agent: Role / Goal / Tools / Output]
## Memory Design
[Short-term / Long-term / Shared — what goes where]
## Data Flow
[Step-by-step: what triggers the system → what each agent does → what comes out]
## Pilot Plan
[Small-scope test with measurable success criteria]
## What NOT to Automate
[Any parts of the workflow that need human judgment — flag explicitly]
```
---
## Common Mistakes to Call Out
- **Too many tools per agent** — performance degrades. Keep it to 2–4 per agent.
- **No memory between sessions** — agents that start cold every time can't compound knowledge.
- **Sequential where parallel would work** — if 3 agents can run simultaneously, don't chain them.
- **Skipping observability** — production agents need logging. LangSmith for LangGraph,
  Langfuse as a framework-agnostic option.
- **More agents ≠ better** — research shows that beyond ~5 agents, coordination overhead
  starts degrading quality. Smaller, smarter teams win.
---
## Quick Reference: Key Numbers (2026)
- 79% enterprise AI agent adoption claimed / only 11% in production
- Framework choice: up to 30% performance gap on identical models
- RecursiveMAS (UIUC/Stanford): letting agents communicate in embedding space rather than
  text yields 2.4× faster inference and 75% fewer tokens — worth knowing for at-scale systems
- CrewAI: working prototype in one afternoon
- LangGraph: production-grade, most verified enterprise deployments
---
## Edge Cases
**User wants to automate everything at once:** Slow down. Start with one workflow, one tier.
Breadth before depth = failure.
**User is technical and wants framework specifics:** Skip the tier selection conversation,
go straight to agent roster and memory design.
**User's agent "keeps getting confused":** This is almost always a memory architecture
problem, not a model problem. Check what context the agent has access to and what it's
losing between steps.
**User asks "which is better, CrewAI or LangGraph?":** Neither — they solve different
problems. Use the Tier selection (Step 2) to determine which tier they need, then the
framework follows automatically.
