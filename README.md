# AI Workspace

Personal AI tools, skills, and automation pipelines.

## Contents

| Folder | What it is |
|---|---|
| `local-rag-kb/` | MCP server — makes any local folder searchable by Claude |
| `weekly-briefing/` | Automated AI industry briefing pipeline |
| `agent-memory/` | Agent with non-regressive persistent memory |
| `skills-reference/` | Copies of installed Claude skills |

## Quick start

```bash
# Install dependencies
pip install fastmcp sentence-transformers numpy anthropic feedparser httpx

# Set API key
export ANTHROPIC_API_KEY=your-key

# Run weekly briefing
cd weekly-briefing && python briefing.py --output ~/Desktop/briefing.md

# Start RAG knowledge base server
python local-rag-kb/server.py --docs-path ~/Documents/your-notes

# Run memory agent
cd agent-memory && python agent.py "your question"
```

## Skills (installed globally to ~/.claude/skills/)

- `multi-agent-architect` — framework selection, agent roles, memory design
- `proxy-pointer-rag` — structure-aware RAG with pointer-based retrieval
- `agentic-coding-guide` — Claude Code settings, CLAUDE.md, safe permissions
- `data-engineering-2026` — Polars, Bytewax, Turbovec patterns

## MCP Server setup

Add to `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "local-rag-kb": {
      "command": "python",
      "args": [
        "C:\\Users\\YOUR_USERNAME\\ai-workspace\\local-rag-kb\\server.py",
        "--docs-path",
        "C:\\Users\\YOUR_USERNAME\\Documents"
      ]
    }
  }
}
```
