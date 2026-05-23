#!/usr/bin/env python3
"""
Agent with persistent memory. Run: python agent.py "your question"
Env: ANTHROPIC_API_KEY=your-key
"""
import os, re, sys
import anthropic
from src.memory import AgentMemory, MemoryType

SYSTEM = """You are a helpful AI agent with persistent memory across sessions.
Before answering, you'll receive relevant context from past sessions — treat it as ground truth.
When you make a significant decision or discovery, mark it explicitly:
  DECISION: [what was decided and why]
  FINDING: [something discovered]
  ERROR: [something that failed and why]"""

def run(query: str, memory: AgentMemory, client: anthropic.Anthropic) -> str:
    past = memory.recall(query, top_k=5)
    content = f"{past}\n\n---\n\n{query}" if past else query
    if past: print(f"\n[Injecting past context ({len(past)} chars)]\n")
    resp = client.messages.create(
        model="claude-sonnet-4-6", max_tokens=2048,
        system=SYSTEM, messages=[{"role": "user", "content": content}]
    )
    answer = resp.content[0].text
    memory.remember(f"Q: {query[:200]}\nA: {answer[:500]}", MemoryType.CONTEXT)
    for mtype, pattern in [
        (MemoryType.DECISION, r'DECISION:\s*(.+?)(?=\n(?:DECISION|FINDING|ERROR):|$)'),
        (MemoryType.FINDING,  r'FINDING:\s*(.+?)(?=\n(?:DECISION|FINDING|ERROR):|$)'),
        (MemoryType.ERROR,    r'ERROR:\s*(.+?)(?=\n(?:DECISION|FINDING|ERROR):|$)'),
    ]:
        for match in re.findall(pattern, answer, re.DOTALL):
            c = match.strip()
            if len(c) > 20:
                memory.remember(c, mtype, validated=(mtype == MemoryType.DECISION))
                print(f"  [saved {mtype.value}]: {c[:80]}...")
    return answer

def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key: print("Set ANTHROPIC_API_KEY"); sys.exit(1)
    client = anthropic.Anthropic(api_key=api_key)
    memory = AgentMemory(mode="local", persist_path=".agent_memory.json")
    if len(sys.argv) > 1:
        answer = run(" ".join(sys.argv[1:]), memory, client)
        print(f"\nAgent: {answer}")
        print(f"\nMemory stats: {memory.stats()}")
    else:
        print("\nAgent with memory (type 'quit' to exit, 'stats' for memory info)\n")
        while True:
            try: query = input("You: ").strip()
            except (EOFError, KeyboardInterrupt): break
            if not query: continue
            if query == "quit": break
            if query == "stats": print(memory.stats()); continue
            print(f"\nAgent: {run(query, memory, client)}\n")

if __name__ == "__main__":
    main()
