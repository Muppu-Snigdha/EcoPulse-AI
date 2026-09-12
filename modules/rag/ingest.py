"""
ingest.py
---------
One-time script that reads the knowledge/*.md files, splits them into chunks,
embeds each chunk using Google Gemini gemini-embedding-001, and persists
everything to a local ChromaDB collection at data/chroma_db/.

Run this once at setup, and again whenever the knowledge docs change:
    python -m modules.rag.ingest

Design
------
* Chunk strategy: split on blank lines (paragraph-level), then merge short
  paragraphs until each chunk is ~400-600 tokens. This preserves semantic
  coherence better than fixed-character splits for structured markdown.
* Overlap: the last sentence of each chunk is prepended to the next chunk
  (soft overlap — improves boundary retrieval).
* ChromaDB collection name: "ecopulse_kb"
* Embedding model: models/gemini-embedding-001 (free Gemini tier, new SDK)
* Task type for embeddings: RETRIEVAL_DOCUMENT (for indexing)
* SDK: google-genai (new) — google.generativeai is deprecated.
"""

from __future__ import annotations

import os
import re
import time
from pathlib import Path

import chromadb
from google import genai
from google.genai import types as genai_types
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"
CHROMA_DIR = str(Path(__file__).parent.parent.parent / "data" / "chroma_db")
COLLECTION_NAME = "ecopulse_kb"
EMBEDDING_MODEL = "models/gemini-embedding-001"

# Target chunk size in approximate characters (~400-600 tokens at ~4 chars/token)
CHUNK_TARGET_CHARS = 1800
CHUNK_MIN_CHARS = 400


# ---------------------------------------------------------------------------
# Text splitting
# ---------------------------------------------------------------------------

def _split_into_paragraphs(text: str) -> list[str]:
    """Split on double newlines (markdown paragraph breaks)."""
    paragraphs = re.split(r"\n\s*\n", text)
    return [p.strip() for p in paragraphs if p.strip()]


def _merge_into_chunks(paragraphs: list[str], target: int, min_size: int) -> list[str]:
    """
    Merge short paragraphs into chunks up to ~target characters.
    Appends the last paragraph of the previous chunk as context overlap.
    """
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for para in paragraphs:
        if current_len + len(para) > target and current:
            chunk_text = "\n\n".join(current)
            chunks.append(chunk_text)
            # Soft overlap: carry the last paragraph into the next chunk
            overlap = current[-1] if current else ""
            current = [overlap, para] if overlap else [para]
            current_len = len(overlap) + len(para)
        else:
            current.append(para)
            current_len += len(para)

    if current:
        remaining = "\n\n".join(current)
        if len(remaining) >= min_size or not chunks:
            chunks.append(remaining)
        else:
            # Merge tiny trailing chunk into the last chunk
            chunks[-1] = chunks[-1] + "\n\n" + remaining

    return chunks


def _load_knowledge_files() -> list[tuple[str, str]]:
    """
    Return list of (source_filename, full_text) for every .md / .txt file
    in the knowledge directory.
    """
    docs: list[tuple[str, str]] = []
    for path in sorted(KNOWLEDGE_DIR.glob("*.md")) + sorted(KNOWLEDGE_DIR.glob("*.txt")):
        docs.append((path.name, path.read_text(encoding="utf-8")))
    return docs


def _build_chunks(docs: list[tuple[str, str]]) -> list[dict]:
    """
    Convert raw documents into chunk records:
    {"id": str, "text": str, "source": str, "chunk_index": int}
    """
    all_chunks: list[dict] = []
    for source_name, text in docs:
        paras = _split_into_paragraphs(text)
        chunks = _merge_into_chunks(paras, CHUNK_TARGET_CHARS, CHUNK_MIN_CHARS)
        for i, chunk in enumerate(chunks):
            chunk_id = f"{source_name}::chunk_{i:03d}"
            all_chunks.append({
                "id": chunk_id,
                "text": chunk,
                "source": source_name,
                "chunk_index": i,
            })
    return all_chunks


# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------

def _embed_texts(texts: list[str], client: genai.Client) -> list[list[float]]:
    """
    Embed a list of texts using Gemini gemini-embedding-001.
    Uses RETRIEVAL_DOCUMENT task type for storage.
    Adds a short delay between batches to respect rate limits.
    """
    embeddings: list[list[float]] = []
    for i, text in enumerate(texts):
        result = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=text,
            config=genai_types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT"),
        )
        embeddings.append(result.embeddings[0].values)
        # Polite rate-limiting: free tier allows 1500 req/min — no delay needed
        # but a short pause avoids transient quota errors on cold start.
        if (i + 1) % 10 == 0:
            time.sleep(0.5)
    return embeddings


# ---------------------------------------------------------------------------
# ChromaDB persistence
# ---------------------------------------------------------------------------

def _get_or_create_collection(reset: bool = False) -> chromadb.Collection:
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    if reset:
        try:
            client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
    return collection


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def ingest(reset: bool = True) -> int:
    """
    Full ingest pipeline: load docs -> chunk -> embed -> store.

    Parameters
    ----------
    reset : bool  If True, delete and recreate the collection (full rebuild).
                  Set to False for incremental updates (not yet implemented).

    Returns
    -------
    int  Number of chunks stored.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GEMINI_API_KEY not found. Create a .env file with GEMINI_API_KEY=..."
        )
    client = genai.Client(api_key=api_key)

    print("Loading knowledge files...")
    docs = _load_knowledge_files()
    if not docs:
        raise FileNotFoundError(f"No .md or .txt files found in {KNOWLEDGE_DIR}")
    print(f"  Found {len(docs)} document(s): {[d[0] for d in docs]}")

    print("Chunking documents...")
    chunks = _build_chunks(docs)
    print(f"  Created {len(chunks)} chunk(s)")

    print("Embedding chunks via Gemini gemini-embedding-001...")
    texts = [c["text"] for c in chunks]
    embeddings = _embed_texts(texts, client)
    print(f"  Embedded {len(embeddings)} chunk(s)")

    print(f"Storing in ChromaDB at {CHROMA_DIR}...")
    collection = _get_or_create_collection(reset=reset)
    collection.add(
        ids=[c["id"] for c in chunks],
        embeddings=embeddings,
        documents=texts,
        metadatas=[{"source": c["source"], "chunk_index": c["chunk_index"]} for c in chunks],
    )
    count = collection.count()
    print(f"  Collection '{COLLECTION_NAME}' now has {count} chunk(s).")
    return count


if __name__ == "__main__":
    ingest()
