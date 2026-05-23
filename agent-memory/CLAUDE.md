# Agent Memory Architecture Template

## What this is
A production-ready Python starter for AI agents with non-regressive persistent memory.
Agents remember what they learned, build on validated decisions, and never
contradict their own past work.

## Architecture

```
src/memory.py     — Memory store (local or Qdrant backend)
agent.py          — Agent loop with memory injection and extraction
CLAUDE.md         — This file
```

### Memory layers
1. **Short-term**: current conversation context (in Claude's context window)
2. **Long-term**: past findings, decisions, and errors (vector store)
3. **Retrieval**: semantic search surfaces relevant past context before each response

### The non-regressive pattern
- Every significant decision is stored and marked as validated
- On every new query, relevant past decisions are retrieved and injected into context
- Agents build on what was decided before rather than reconsidering from scratch

## How to run

```bash
# Install
pip install anthropic sentence-transformers numpy

# Set API key
export ANTHROPIC_API_KEY=your-key

# Single query
python agent.py "What database should we use for this project?"

# Interactive
python agent.py
```

## Switching to Qdrant (production)

```bash
# Start Qdrant locally
docker run -p 6333:6333 qdrant/qdrant

# Install client
pip install qdrant-client

# Change in agent.py:
# memory = AgentMemory(mode="qdrant")
```

## Key classes

**AgentMemory** — unified interface
```python
memory = AgentMemory(mode="local")  # or mode="qdrant"

# Store a decision
memory.remember(
    content="We chose PostgreSQL for relational data structure.",
    memory_type=MemoryType.DECISION,
    validated=True
)

# Recall relevant context
context = memory.recall("database choice")
# Returns formatted string ready to inject into prompt
```

**MemoryType** enum:
- `DECISION` — a choice that was made (auto-validated)
- `FINDING` — something discovered during a session
- `ACTION` — something the agent did
- `ERROR` — something that failed and why
- `CONTEXT` — general background captured from Q&A

## Extending this template

**Add tools**: Wrap tool calls in `run_agent()` before the Claude API call.
Store tool results as `MemoryType.ACTION` entries.

**Add validation loop**: After each answer, ask the user to confirm. Call
`memory.validate_memory(id)` on confirmed entries.

**Add multi-agent**: Give each agent its own `AgentMemory` instance pointing to
the same store. Use `tags` to route retrieval to agent-specific memories.

**Add time decay**: Entries have a `timestamp` field. Filter out memories older
than N days in `recall()` calls for freshness.

## What Claude should do if asked to modify this

- Run `python agent.py "test query"` after any change to the agent loop
- Don't change the MemoryEntry schema without migrating existing `.agent_memory.json`
- The `recall()` → inject → store cycle in `run_agent()` is the core — be careful modifying it
- Test both local and qdrant modes when changing `AgentMemory`
