"""
RAG ingestion: loads Markdown knowledge-base files into ChromaDB.

Idempotent — repeated runs do not create duplicate chunks.
Stable chunk id = sha256(source_path + ":" + chunk_index).
"""

import hashlib
import logging
import pathlib
from typing import Optional

import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

from src.config import settings

logger = logging.getLogger(__name__)

_KNOWLEDGE_BASE_ROOT = pathlib.Path("data/sample_data/knowledge_base")

# Source-type is derived from the immediate parent directory name.
_SOURCE_TYPE_MAP: dict[str, str] = {
    "runbooks": "runbook",
    "postmortems": "postmortem",
    "playbooks": "playbook",
    "baseline": "baseline",
}

_client: Optional[chromadb.PersistentClient] = None


def get_chroma_client() -> chromadb.PersistentClient:
    """Return the shared PersistentClient, initialising it on first call."""
    global _client
    if _client is None:
        path = settings.chroma_db_path
        logger.info("Initialising ChromaDB PersistentClient at %s", path)
        _client = chromadb.PersistentClient(path=path)
    return _client


def _stable_chunk_id(source_path: str, chunk_index: int) -> str:
    raw = f"{source_path}:{chunk_index}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _extract_title(text: str, filename: str) -> str:
    """Return the first H1 heading from the document, falling back to filename."""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return filename


def _load_chunks() -> tuple[list[str], list[dict[str, str]], list[str]]:
    """Walk the knowledge-base directory and split every .md file into chunks.

    Returns parallel lists: (documents, metadatas, ids).
    Chunks shorter than settings.rag_min_chunk_len characters are dropped.
    """
    documents: list[str] = []
    metadatas: list[dict[str, str]] = []
    ids: list[str] = []

    md_files = sorted(_KNOWLEDGE_BASE_ROOT.rglob("*.md"))
    logger.info("Found %d Markdown files to index", len(md_files))

    for md_path in md_files:
        source_type = _SOURCE_TYPE_MAP.get(md_path.parent.name, "unknown")
        relative_path = str(md_path)
        text = md_path.read_text(encoding="utf-8")
        title = _extract_title(text, md_path.stem)

        raw_chunks = text.split("\n\n")
        chunk_index = 0
        for raw in raw_chunks:
            chunk = raw.strip()
            if len(chunk) < settings.rag_min_chunk_len:
                continue
            chunk_id = _stable_chunk_id(relative_path, chunk_index)
            documents.append(chunk)
            metadatas.append(
                {
                    "source_type": source_type,
                    "filename": md_path.name,
                    "title": title,
                }
            )
            ids.append(chunk_id)
            chunk_index += 1

    logger.info("Prepared %d chunks from knowledge base", len(documents))
    return documents, metadatas, ids


def get_or_ingest_collection(
    client: chromadb.PersistentClient,
) -> chromadb.Collection:
    """Return the ChromaDB collection, ingesting documents if it is empty.

    Uses cosine distance so that similarity = 1 - distance stays in [0, 1].
    """
    ef = DefaultEmbeddingFunction()
    collection = client.get_or_create_collection(
        name=settings.chroma_collection_name,
        embedding_function=ef,  # type: ignore[arg-type]
        metadata={"hnsw:space": "cosine"},
    )

    existing_count = collection.count()
    if existing_count > 0:
        logger.info(
            "Collection '%s' already contains %d chunks — skipping ingestion",
            settings.chroma_collection_name,
            existing_count,
        )
        return collection

    documents, metadatas, ids = _load_chunks()

    if not documents:
        logger.warning("No chunks found — knowledge base may be empty")
        return collection

    # ChromaDB add() is idempotent when ids already exist (upsert semantics in
    # newer versions), but we guard with the count check above for clarity.
    collection.add(documents=documents, metadatas=metadatas, ids=ids)  # type: ignore[arg-type]

    logger.info(
        "Indexed %d chunks into collection '%s'",
        len(documents),
        settings.chroma_collection_name,
    )
    return collection
