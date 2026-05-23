---
name: proxy-pointer-rag
description: >
  Build better document retrieval and RAG (Retrieval-Augmented Generation) pipelines
  using the Proxy-Pointer architecture. Use this skill whenever someone is building a
  knowledge base, document search system, or RAG pipeline; asking why their AI is
  hallucinating answers from documents; wanting to make Claude search through PDFs,
  reports, contracts, or knowledge bases more accurately; working with large structured
  documents (financial filings, legal contracts, technical reports); or using phrases
  like "knowledge graph," "vector search," "document retrieval," "semantic search,"
  "RAG," "my AI is making things up from my documents," or "entity extraction." Also
  trigger when someone asks how to make AI answers more accurate or grounded.
---
# Proxy-Pointer RAG Skill
Build retrieval pipelines that give AI complete, structured context — not blind fragments.
The core problem with standard RAG: it chops documents into arbitrary chunks, embeds
them, and retrieves the top-K by cosine similarity. The AI sees fragmented, context-less
text and frequently hallucinates or misses the answer entirely.
Proxy-Pointer fixes this at zero extra infrastructure cost — pure Python, no new services.
---
## The Core Insight
Standard RAG retrieves **chunks**. Proxy-Pointer retrieves **sections**.
The chunk is a pointer. When a chunk matches the query, instead of feeding that chunk
to the AI, you load the entire document section the chunk belongs to. The AI sees
complete, coherent context. Accuracy goes up dramatically.
Think of it like a library index: the index card (chunk) tells you where to look, but
you read the full chapter (section), not just the card.
---
## The Five Techniques (All Free, All Pure Python)
Apply these in order during document ingestion.
### Technique 1: Skeleton Tree
Parse Markdown headings into a hierarchical tree representing the document's structure.
```python
import re
from dataclasses import dataclass, field
from typing import Optional
@dataclass
class SectionNode:
    heading: str
    level: int
    content: str
    children: list = field(default_factory=list)
    parent: Optional['SectionNode'] = field(default=None, repr=False)
def build_skeleton_tree(markdown_text: str) -> list[SectionNode]:
    lines = markdown_text.split('\n')
    root_nodes = []
    stack = []
    current_content = []
    current_heading = None
    current_level = 0
    def flush_node():
        if current_heading is not None:
            node = SectionNode(
                heading=current_heading,
                level=current_level,
                content='\n'.join(current_content).strip()
            )
            while stack and stack[-1][0] >= current_level:
                stack.pop()
            if stack:
                parent = stack[-1][1]
                node.parent = parent
                parent.children.append(node)
            else:
                root_nodes.append(node)
            stack.append((current_level, node))
            return node
        return None
    for line in lines:
        match = re.match(r'^(#{1,6})\s+(.+)', line)
        if match:
            flush_node()
            current_level = len(match.group(1))
            current_heading = match.group(2).strip()
            current_content = []
        else:
            current_content.append(line)
    flush_node()
    return root_nodes
```
### Technique 2: Breadcrumb Injection
Before embedding each chunk, prepend its full structural path.
```python
def get_breadcrumb(node: SectionNode) -> str:
    path = []
    current = node
    while current:
        path.append(current.heading)
        current = current.parent
    return ' > '.join(reversed(path))
def inject_breadcrumb(node: SectionNode) -> str:
    breadcrumb = get_breadcrumb(node)
    return f"[{breadcrumb}]\n\n{node.content}"
```
### Technique 3: Structure-Guided Chunking
Split text within section boundaries, never across them.
```python
def chunk_section(node: SectionNode, max_tokens: int = 512) -> list[str]:
    words = node.content.split()
    chunks = []
    current_chunk = []
    current_size = 0
    for word in words:
        current_chunk.append(word)
        current_size += 1
        if current_size >= max_tokens:
            chunks.append(f"[{get_breadcrumb(node)}]\n\n{' '.join(current_chunk)}")
            current_chunk = []
            current_size = 0
    if current_chunk:
        chunks.append(f"[{get_breadcrumb(node)}]\n\n{' '.join(current_chunk)}")
    return chunks
```
### Technique 4: Noise Filtering
Remove sections that pollute the index.
```python
NOISE_HEADINGS = {
    'table of contents', 'contents', 'index', 'glossary',
    'abbreviations', 'references', 'bibliography', 'appendix',
    'executive summary', 'disclaimer', 'legal notice', 'copyright'
}
def should_skip_section(node: SectionNode) -> bool:
    return node.heading.lower().strip() in NOISE_HEADINGS
```
### Technique 5: Pointer-Based Context Loading
When a chunk matches the query, load the full section instead.
```python
def build_chunk_to_section_map(nodes: list[SectionNode]) -> dict:
    chunk_map = {}
    def process_node(node):
        if should_skip_section(node):
            return
        full_section = f"## {node.heading}\n\n{node.content}"
        chunks = chunk_section(node)
        for i, chunk in enumerate(chunks):
            chunk_id = f"{get_breadcrumb(node)}::chunk_{i}"
            chunk_map[chunk_id] = {
                'chunk': chunk,
                'full_section': full_section,
                'breadcrumb': get_breadcrumb(node),
                'heading': node.heading
            }
        for child in node.children:
            process_node(child)
    for root in nodes:
        process_node(root)
    return chunk_map
def retrieve_with_pointer(query, vector_index, chunk_map, top_k=5):
    results = vector_index.search(query, top_k=top_k)
    full_sections = []
    seen = set()
    for result in results:
        chunk_id = result['id']
        if chunk_id in chunk_map:
            section_key = chunk_map[chunk_id]['breadcrumb']
            if section_key not in seen:
                full_sections.append(chunk_map[chunk_id]['full_section'])
                seen.add(section_key)
    return full_sections
```
---
## When to Use Each Approach
| Document Type | Best Approach |
|---|---|
| Financial reports, legal contracts, research papers | Full Proxy-Pointer (all 5 techniques) |
| Technical documentation, wikis | Techniques 1–4 |
| Customer support knowledge base | Standard RAG is fine |
| Unstructured text (no headings) | Graceful degradation to standard chunking |
---
## Common Problems and Fixes
**"My RAG keeps hallucinating facts"** → Apply Technique 3 (structure-guided chunking).
**"My RAG finds the right document but gives the wrong answer"** → Apply Technique 5
(pointer-based loading) — return the full section, not the chunk.
**"My RAG confuses similar entities from different parts of the document"** →
Breadcrumbs are missing. Apply Technique 2.
**"My knowledge graph has duplicate nodes for the same entity"** →
Entity extraction is running on fragments. Use pointer loading to extract from full sections.
