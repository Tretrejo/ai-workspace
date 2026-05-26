"""
Local RAG Knowledge Base MCP Server
Makes a local folder of documents semantically searchable by Claude.
Run: python server.py --docs-path ~/Documents/your-notes
"""
import argparse, hashlib, json, logging, os, pickle, re, sys, time
from pathlib import Path
from typing import Optional
import numpy as np

# ── UTF-8 stdout (MCP stdio protocol channel — NOTHING else may write here) ──
sys.stdout = __import__("io").TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ── Silence sentence_transformers and tqdm noise on stderr (safe — not stdout) ──
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)
logging.getLogger("transformers").setLevel(logging.ERROR)

from fastmcp import FastMCP
from sentence_transformers import SentenceTransformer

DEFAULT_MODEL = "all-MiniLM-L6-v2"
CHUNK_SIZE = 512
SUPPORTED_EXT = {".md", ".txt", ".rst", ".text"}

def _log(msg: str) -> None:
    """All diagnostic output goes to stderr — never stdout."""
    print(msg, file=sys.stderr, flush=True)

def extract_text(path: Path) -> Optional[str]:
    ext = path.suffix.lower()
    if ext in SUPPORTED_EXT:
        try: return path.read_text(encoding="utf-8", errors="ignore")
        except: return None
    if ext == ".pdf":
        try:
            import fitz
            doc = fitz.open(str(path))
            text = "\n\n".join(p.get_text() for p in doc)
            doc.close()
            return text
        except ImportError:
            _log(f"  [skip] {path.name} — pip install pymupdf for PDF support")
            return None
    return None

def clean(text: str) -> str:
    text = re.sub(r'\r\n', '\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    return re.sub(r'\n{3,}', '\n\n', text).strip()

def chunk(text: str, size: int = CHUNK_SIZE) -> list[str]:
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    chunks, current, cur_len = [], [], 0
    for para in paragraphs:
        if cur_len + len(para) > size and current:
            chunks.append('\n\n'.join(current))
            current, cur_len = current[-1:], len(current[-1]) if current else 0
        current.append(para)
        cur_len += len(para)
    if current:
        chunks.append('\n\n'.join(current))
    return [c for c in chunks if len(c.strip()) > 50]

class LocalIndex:
    def __init__(self, docs_path: str, model_name: str = DEFAULT_MODEL):
        self.docs_path = Path(docs_path).expanduser().resolve()
        self.cache_path = self.docs_path / ".rag_index.pkl"
        _log(f"Loading model: {model_name}")
        self.model = SentenceTransformer(model_name)
        self.chunks: list[dict] = []
        self.embeddings: Optional[np.ndarray] = None
        self._load_or_build()

    def _file_hash(self, p: Path) -> str: return hashlib.md5(p.read_bytes()).hexdigest()

    def _iter_files(self):
        for p in self.docs_path.rglob("*"):
            if not p.name.startswith(".") and p.suffix.lower() in (SUPPORTED_EXT | {".pdf"}):
                yield p

    def _load_or_build(self):
        if self.cache_path.exists():
            try:
                cached = pickle.load(open(self.cache_path, "rb"))
                current = {str(p): self._file_hash(p) for p in self._iter_files()}
                if cached.get("file_hashes") == current:
                    self.chunks, self.embeddings = cached["chunks"], np.array(cached["embeddings"])
                    _log(f"Loaded {len(self.chunks)} chunks from cache")
                    return
            except: pass
        self._build()

    def _build(self):
        _log(f"Building index from: {self.docs_path}")
        files = list(self._iter_files())
        if not files: _log("  No files found."); return
        all_chunks, file_hashes = [], {}
        for path in files:
            text = extract_text(path)
            if not text: continue
            text = clean(text)
            rel = str(path.relative_to(self.docs_path))
            for i, c in enumerate(chunk(text)):
                all_chunks.append({"text": c, "source": rel, "chunk_idx": i, "total_chunks": len(chunk(text))})
            file_hashes[str(path)] = self._file_hash(path)
            _log(f"  Indexed: {rel}")
        if not all_chunks: _log("No content extracted."); return
        embs = self.model.encode([c["text"] for c in all_chunks], show_progress_bar=False, batch_size=64)
        self.chunks, self.embeddings = all_chunks, np.array(embs)
        pickle.dump({"chunks": self.chunks, "embeddings": self.embeddings.tolist(),
                     "file_hashes": file_hashes, "built_at": time.time()}, open(self.cache_path, "wb"))
        _log(f"Index built: {len(self.chunks)} chunks from {len(file_hashes)} files.")

    def search(self, query: str, top_k: int = 5, threshold: float = 0.3) -> list[dict]:
        if not self.chunks or self.embeddings is None: return []
        q = self.model.encode([query])
        normed = self.embeddings / np.clip(np.linalg.norm(self.embeddings, axis=1, keepdims=True), 1e-8, None)
        scores = (normed @ (q / np.linalg.norm(q)).T).squeeze()
        results = []
        for i, (entry, score) in enumerate(zip(self.chunks, scores)):
            if float(score) >= threshold:
                r = dict(entry); r["score"] = round(float(score), 3); results.append(r)
        return sorted(results, key=lambda x: x["score"], reverse=True)[:top_k]

    def rebuild(self):
        if self.cache_path.exists(): self.cache_path.unlink()
        self._build()

def create_server(docs_path: str) -> FastMCP:
    # Lazy/background index init so MCP handshake (60s timeout) is never blocked
    # by model load + file-hash checks against OneDrive (which can take >60s).
    import threading
    state = {"index": None, "error": None, "ready": threading.Event()}

    def _build_in_background():
        try:
            state["index"] = LocalIndex(docs_path)
        except Exception as e:
            state["error"] = repr(e)
            _log(f"Index init failed: {e}")
        finally:
            state["ready"].set()

    threading.Thread(target=_build_in_background, daemon=True).start()

    def _get_index(wait_seconds: float = 0.0):
        """Return index, or None if not ready yet."""
        if state["ready"].is_set():
            return state["index"]
        if wait_seconds > 0:
            state["ready"].wait(timeout=wait_seconds)
        return state["index"] if state["ready"].is_set() else None

    mcp = FastMCP("local-rag-kb")

    @mcp.tool()
    def search_knowledge_base(query: str, top_k: int = 5, threshold: float = 0.25) -> str:
        """Search your local knowledge base for documents relevant to a query."""
        index = _get_index(wait_seconds=120.0)
        if state["error"]:
            return f"Index initialization failed: {state['error']}"
        if index is None:
            return "Index is still building (model load + file hashing). Try again in 30-60 seconds."
        results = index.search(query, top_k=min(top_k, 10), threshold=threshold)
        if not results: return f"No results for: '{query}'"
        out = [f"Found {len(results)} results for: '{query}'\n"]
        for i, r in enumerate(results, 1):
            out.append(f"--- Result {i} (score: {r['score']}) ---\nSource: {r['source']}\n\n{r['text']}\n")
        return "\n".join(out)

    @mcp.tool()
    def list_indexed_files() -> str:
        """List all files currently indexed in the knowledge base."""
        index = _get_index(wait_seconds=10.0)
        if state["error"]: return f"Index initialization failed: {state['error']}"
        if index is None: return "Index still initializing — try again shortly."
        if not index.chunks: return f"Empty. No files in: {index.docs_path}"
        from collections import Counter
        fc = Counter(c["source"] for c in index.chunks)
        lines = [f"KB: {index.docs_path}\nTotal: {len(index.chunks)} chunks, {len(fc)} files\n"]
        for f, n in sorted(fc.items()): lines.append(f"  {f}  ({n} chunks)")
        return "\n".join(lines)

    @mcp.tool()
    def rebuild_index() -> str:
        """Force a full rebuild of the index after adding/editing files."""
        index = _get_index(wait_seconds=120.0)
        if state["error"]: return f"Index initialization failed: {state['error']}"
        if index is None: return "Index still initializing — try rebuild after first init completes."
        old = len(index.chunks)
        index.rebuild()
        return f"Rebuilt. Before: {old} chunks. After: {len(index.chunks)} chunks."

    @mcp.tool()
    def index_status() -> str:
        """Check whether the knowledge-base index is ready."""
        if state["error"]: return f"Index initialization FAILED: {state['error']}"
        index = _get_index()
        if index is None: return "Index is still building (model load + file hashing). Search tools will wait up to 120s on first call."
        return f"Index READY. {len(index.chunks)} chunks indexed from {index.docs_path}."

    return mcp

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--docs-path", required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()
    path = Path(args.docs_path).expanduser().resolve()
    if not path.exists(): _log(f"Error: {path} does not exist"); return
    _log(f"Local RAG KB MCP — {path}")
    create_server(str(path)).run(transport="stdio")

if __name__ == "__main__":
    main()
