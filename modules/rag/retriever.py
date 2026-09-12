"""
retriever.py
------------
Query-time retrieval from the ChromaDB knowledge base.

Public API
----------
get_context(query, k=3)  -> str
    Embeds the query, retrieves top-k chunks, returns a formatted context block.

get_context_with_metadata(query, k=3) -> dict
    Same as above but also returns chunk IDs and similarity scores for the
    explainability trace.

is_ready() -> bool
    Returns True if the ChromaDB collection exists and has at least one document.
"""

from __future__ import annotations

import os
from pathlib import Path

import chromadb
from google import genai
from google.genai import types as genai_types
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration — must match ingest.py
# ---------------------------------------------------------------------------
CHROMA_DIR = str(Path(__file__).parent.parent.parent / "data" / "chroma_db")
COLLECTION_NAME = "ecopulse_kb"
EMBEDDING_MODEL = "models/gemini-embedding-001"

# Minimum cosine similarity for a chunk to be included in context.
# ChromaDB returns distances (lower = more similar for cosine space).
# Distance threshold: 0.6 means cosine similarity >= 0.4 (borderline relevance).
DISTANCE_THRESHOLD = 0.6

_collection_cache: chromadb.Collection | None = None


def _get_collection() -> chromadb.Collection:
    """Return the cached ChromaDB collection, connecting lazily."""
    global _collection_cache
    if _collection_cache is None:
        client = chromadb.PersistentClient(path=CHROMA_DIR)
        _collection_cache = client.get_collection(name=COLLECTION_NAME)
    return _collection_cache


def _embed_query(query: str) -> list[float]:
    """Embed a single query string using Gemini gemini-embedding-001."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError("GEMINI_API_KEY not set.")
    client = genai.Client(api_key=api_key)
    result = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=query,
        config=genai_types.EmbedContentConfig(task_type="RETRIEVAL_QUERY"),
    )
    return result.embeddings[0].values


def is_ready() -> bool:
    """
    Return True if the ChromaDB collection exists and contains at least one document.
    Used at app startup to show a warning if ingest hasn't been run yet.
    """
    try:
        col = _get_collection()
        return col.count() > 0
    except Exception:
        return False


def get_context(query: str, k: int = 3) -> str:
    """
    Retrieve the top-k most relevant knowledge chunks for a query.

    Parameters
    ----------
    query : str  The user's question or the agent's sub-query.
    k     : int  Number of chunks to retrieve (default 3).

    Returns
    -------
    str  A formatted context block ready for injection into the LLM prompt.
         Returns an empty string if the collection is not ready or no relevant
         chunks are found above the similarity threshold.
    """
    result = get_context_with_metadata(query, k=k)
    return result["context_text"]


def get_context_with_metadata(query: str, k: int = 3) -> dict:
    """
    Retrieve top-k chunks and return them along with metadata for explainability.

    Returns
    -------
    dict with keys:
        context_text : str    — formatted block for LLM injection (empty if no match)
        chunks       : list[dict]  — each has: id, text, source, distance, score
        found        : bool   — whether any chunk passed the threshold
    """
    if not query or not query.strip():
        return {"context_text": "", "chunks": [], "found": False}

    try:
        collection = _get_collection()
    except Exception:
        return {"context_text": "", "chunks": [], "found": False}

    if collection.count() == 0:
        return {"context_text": "", "chunks": [], "found": False}

    query_embedding = _embed_query(query.strip())

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(k, collection.count()),
        include=["documents", "metadatas", "distances"],
    )

    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]
    ids = results["ids"][0]

    # Filter by distance threshold
    chunks = []
    for doc, meta, dist, cid in zip(documents, metadatas, distances, ids):
        if dist <= DISTANCE_THRESHOLD:
            chunks.append({
                "id": cid,
                "text": doc,
                "source": meta.get("source", "unknown"),
                "distance": round(dist, 4),
                "score": round(1.0 - dist, 4),   # cosine similarity approximation
            })

    if not chunks:
        # No chunk passed the threshold — return empty context
        # The agent should note "no knowledge base match found"
        return {"context_text": "", "chunks": [], "found": False}

    # Format as a prompt-injection-safe context block
    lines = ["[CONTEXT FROM KNOWLEDGE BASE]"]
    for i, chunk in enumerate(chunks, 1):
        lines.append(f"\n--- Source: {chunk['source']} (relevance: {chunk['score']:.2f}) ---")
        lines.append(chunk["text"])
    lines.append("\n[END CONTEXT]")
    context_text = "\n".join(lines)

    return {
        "context_text": context_text,
        "chunks": chunks,
        "found": True,
    }
