"""
Agent Memory Architecture — non-regressive memory for AI agents.
Agents remember what they learned and build on it across sessions.
"""
import json, time, uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Optional
import numpy as np
from sentence_transformers import SentenceTransformer

class MemoryType(str, Enum):
    DECISION = "decision"
    FINDING  = "finding"
    ACTION   = "action"
    ERROR    = "error"
    CONTEXT  = "context"

@dataclass
class MemoryEntry:
    id:          str = field(default_factory=lambda: str(uuid.uuid4()))
    content:     str = ""
    memory_type: MemoryType = MemoryType.FINDING
    tags:        list = field(default_factory=list)
    validated:   bool = False
    session_id:  str = ""
    timestamp:   float = field(default_factory=time.time)
    metadata:    dict = field(default_factory=dict)

    def to_dict(self):
        d = asdict(self); d["memory_type"] = self.memory_type.value; return d

    @classmethod
    def from_dict(cls, d):
        d["memory_type"] = MemoryType(d.get("memory_type", "finding")); return cls(**d)

class LocalMemoryStore:
    def __init__(self, persist_path=".agent_memory.json", model_name="all-MiniLM-L6-v2"):
        self.path = Path(persist_path)
        self.model = SentenceTransformer(model_name)
        self.entries: list[MemoryEntry] = []
        self.embeddings: Optional[np.ndarray] = None
        self._load()

    def _load(self):
        if self.path.exists():
            data = json.loads(self.path.read_text())
            self.entries = [MemoryEntry.from_dict(d) for d in data.get("entries", [])]
            if data.get("embeddings"):
                self.embeddings = np.array(data["embeddings"])
            print(f"Loaded {len(self.entries)} memories")

    def _save(self):
        self.path.write_text(json.dumps({
            "entries": [e.to_dict() for e in self.entries],
            "embeddings": self.embeddings.tolist() if self.embeddings is not None else []
        }, indent=2))

    def add(self, entry: MemoryEntry) -> str:
        emb = self.model.encode([entry.content])
        self.embeddings = emb if self.embeddings is None else np.vstack([self.embeddings, emb])
        self.entries.append(entry)
        self._save()
        return entry.id

    def search(self, query, top_k=5, memory_types=None, validated_only=False, threshold=0.3):
        if not self.entries or self.embeddings is None: return []
        q = self.model.encode([query])
        normed = self.embeddings / np.clip(np.linalg.norm(self.embeddings, axis=1, keepdims=True), 1e-8, None)
        scores = (normed @ (q / np.linalg.norm(q)).T).squeeze()
        results = []
        for entry, score in zip(self.entries, scores):
            score = float(score)
            if score < threshold: continue
            if memory_types and entry.memory_type not in memory_types: continue
            if validated_only and not entry.validated: continue
            results.append((entry, score))
        return sorted(results, key=lambda x: x[1], reverse=True)[:top_k]

    def validate(self, memory_id: str) -> bool:
        for e in self.entries:
            if e.id == memory_id: e.validated = True; self._save(); return True
        return False

    def stats(self):
        from collections import Counter
        return {"total": len(self.entries),
                "validated": sum(1 for e in self.entries if e.validated),
                "by_type": dict(Counter(e.memory_type.value for e in self.entries))}

class AgentMemory:
    """Unified memory interface. mode='local' or mode='qdrant'"""
    def __init__(self, mode="local", **kwargs):
        self.store = LocalMemoryStore(**kwargs) if mode == "local" else self._qdrant(**kwargs)
        self.session = str(uuid.uuid4())

    def _qdrant(self, **kwargs):
        from src.memory_qdrant import QdrantMemoryStore
        return QdrantMemoryStore(**kwargs)

    def remember(self, content, memory_type=MemoryType.FINDING, tags=None, validated=False, metadata=None):
        return self.store.add(MemoryEntry(
            content=content, memory_type=memory_type, tags=tags or [],
            validated=validated, session_id=self.session, metadata=metadata or {}
        ))

    def recall(self, query, top_k=5, validated_only=False, memory_types=None) -> str:
        results = self.store.search(query, top_k=top_k, validated_only=validated_only, memory_types=memory_types)
        if not results: return ""
        lines = ["## Relevant context from past sessions\n"]
        for entry, score in results:
            mark = " [validated]" if entry.validated else ""
            lines.append(f"**[{entry.memory_type.value.upper()}{mark}]** (relevance: {score:.2f})\n{entry.content}\n")
        return "\n".join(lines)

    def validate_memory(self, memory_id): return self.store.validate(memory_id)

    def stats(self): return self.store.stats()
