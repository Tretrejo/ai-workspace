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

# NOTE: sentence_transformers and rank_bm25 are intentionally NOT imported at
# module top. They pull torch transitively, which can take 5-30 seconds to load
# — that blocks the stdio main loop from acknowledging the MCP `initialize`
# handshake within Claude Desktop's 60-second timeout. We import them lazily
# inside the daemon thread that builds the index, so module-load stays fast.

DEFAULT_MODEL = "all-MiniLM-L6-v2"
CHUNK_SIZE = 512
SUPPORTED_EXT = {".md", ".txt", ".rst", ".text"}

# Bump when the on-disk pickle layout changes — forces a rebuild on next load.
CACHE_SCHEMA_VERSION = 2  # v1 = chunks+embeddings only; v2 adds BM25 corpus

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)
def _tokenize(text: str) -> list[str]:
    """Tokenizer shared by BM25 indexing and BM25 query.

    Splits on non-word chars and lowercases. Lease IDs like '2516-01-R1' become
    ['2516', '01', 'r1'] both at index and query time, so they round-trip.
    """
    return [t.lower() for t in _TOKEN_RE.findall(text)]

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
        # Lazy import — see module-top note. Importing these here means torch
        # load happens in the daemon thread, not at module load.
        from sentence_transformers import SentenceTransformer  # noqa: WPS433
        from rank_bm25 import BM25Okapi  # noqa: WPS433
        self._BM25Okapi = BM25Okapi  # cache class ref for use in _load_or_build / _build
        self.docs_path = Path(docs_path).expanduser().resolve()
        self.cache_path = self.docs_path / ".rag_index.pkl"
        _log(f"Loading model: {model_name}")
        self.model = SentenceTransformer(model_name)
        self.chunks: list[dict] = []
        self.embeddings: Optional[np.ndarray] = None
        self.bm25 = None  # type: ignore[var-annotated]
        self.bm25_corpus: list[list[str]] = []
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
                # Schema-version check: older caches lack BM25 corpus — force rebuild.
                if cached.get("schema_version") != CACHE_SCHEMA_VERSION:
                    _log(f"Cache schema v{cached.get('schema_version')} != v{CACHE_SCHEMA_VERSION}; rebuilding.")
                else:
                    current = {str(p): self._file_hash(p) for p in self._iter_files()}
                    if cached.get("file_hashes") == current:
                        self.chunks = cached["chunks"]
                        self.embeddings = np.array(cached["embeddings"])
                        self.bm25_corpus = cached["bm25_corpus"]
                        self.bm25 = self._BM25Okapi(self.bm25_corpus) if self.bm25_corpus else None
                        _log(f"Loaded {len(self.chunks)} chunks from cache (semantic + BM25)")
                        return
            except Exception as e:
                _log(f"Cache load failed ({e}); rebuilding.")
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
        # Build BM25 over the same chunk texts so the two scorers are aligned by row.
        self.bm25_corpus = [_tokenize(c["text"]) for c in all_chunks]
        self.bm25 = self._BM25Okapi(self.bm25_corpus) if self.bm25_corpus else None
        pickle.dump({
            "schema_version": CACHE_SCHEMA_VERSION,
            "chunks": self.chunks,
            "embeddings": self.embeddings.tolist(),
            "bm25_corpus": self.bm25_corpus,
            "file_hashes": file_hashes,
            "built_at": time.time(),
        }, open(self.cache_path, "wb"))
        _log(f"Index built: {len(self.chunks)} chunks from {len(file_hashes)} files (semantic + BM25).")

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

    def _semantic_scores(self, query: str) -> np.ndarray:
        """Return cosine similarity from query to every chunk (length = len(chunks))."""
        if self.embeddings is None or not self.chunks:
            return np.array([])
        q = self.model.encode([query])
        normed = self.embeddings / np.clip(np.linalg.norm(self.embeddings, axis=1, keepdims=True), 1e-8, None)
        return (normed @ (q / np.linalg.norm(q)).T).squeeze()

    def _bm25_scores(self, query: str) -> np.ndarray:
        """Return BM25 score from query to every chunk (length = len(chunks))."""
        if self.bm25 is None or not self.chunks:
            return np.array([])
        return np.asarray(self.bm25.get_scores(_tokenize(query)))

    def search_hybrid(
        self,
        query: str,
        top_k: int = 5,
        candidate_pool: int = 50,
        rrf_k: int = 60,
        threshold: float = 0.0,
    ) -> list[dict]:
        """Hybrid search: union top-N candidates from BM25 and semantic, fuse via RRF.

        Reciprocal Rank Fusion: rrf_score(d) = sum(1 / (k + rank_d_in_list)) across the
        two ranked lists. Robust to score-scale differences between BM25 and cosine.
        """
        if not self.chunks: return []
        sem_scores = self._semantic_scores(query)
        bm25_scores = self._bm25_scores(query)
        if sem_scores.size == 0 and bm25_scores.size == 0:
            return []

        # Per-list rank lookups (1-indexed): missing-from-list = no contribution.
        def _ranked_indices(scores: np.ndarray, n: int) -> list[int]:
            if scores.size == 0: return []
            order = np.argsort(-scores)
            return order[:n].tolist()

        sem_top = _ranked_indices(sem_scores, candidate_pool)
        bm25_top = _ranked_indices(bm25_scores, candidate_pool)

        rrf: dict[int, float] = {}
        for rank, idx in enumerate(sem_top, start=1):
            rrf[idx] = rrf.get(idx, 0.0) + 1.0 / (rrf_k + rank)
        for rank, idx in enumerate(bm25_top, start=1):
            rrf[idx] = rrf.get(idx, 0.0) + 1.0 / (rrf_k + rank)

        ordered = sorted(rrf.items(), key=lambda kv: kv[1], reverse=True)
        results = []
        for idx, fused in ordered:
            if fused < threshold: continue
            entry = dict(self.chunks[idx])
            entry["score"] = round(float(fused), 5)
            entry["semantic_score"] = round(float(sem_scores[idx]) if sem_scores.size else 0.0, 3)
            entry["bm25_score"] = round(float(bm25_scores[idx]) if bm25_scores.size else 0.0, 3)
            results.append(entry)
            if len(results) >= top_k: break
        return results

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
    def search_knowledge_base_hybrid(query: str, top_k: int = 5, threshold: float = 0.0) -> str:
        """Hybrid search: BM25 (exact-term) + semantic (cosine) fused via Reciprocal Rank Fusion.

        Use this when the query contains identifiers, codes, lease numbers, names, or any
        exact-match token that pure semantic search blurs (e.g. '2516-01-R1', 'MLA-2487',
        'Aptar Cary IL'). The semantic-only tool `search_knowledge_base` is better when the
        query is purely conceptual ('how do renewals work').
        """
        index = _get_index(wait_seconds=120.0)
        if state["error"]: return f"Index initialization failed: {state['error']}"
        if index is None:
            return "Index is still building (model load + file hashing). Try again in 30-60 seconds."
        results = index.search_hybrid(query, top_k=min(top_k, 10), threshold=threshold)
        if not results: return f"No results for: '{query}'"
        out = [f"Found {len(results)} hybrid results for: '{query}' (RRF score / semantic / BM25)\n"]
        for i, r in enumerate(results, 1):
            out.append(
                f"--- Result {i} "
                f"(RRF: {r['score']} | sem: {r['semantic_score']} | bm25: {r['bm25_score']}) ---\n"
                f"Source: {r['source']}\n\n{r['text']}\n"
            )
        return "\n".join(out)

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
