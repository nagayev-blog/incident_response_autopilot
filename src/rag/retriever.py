"""
RAG retriever: dense search over the ChromaDB knowledge-base collection.

Every call is logged with query text, top_k requested, scores and source ids
so that RAGAS evaluation can consume the logs in v2.
"""

import logging
from typing import Any

from src.config import settings
from src.rag.ingestion import get_chroma_client, get_or_ingest_collection

logger = logging.getLogger(__name__)


def _build_query(alert: dict[str, Any]) -> str:
    """Compose a free-text search query from available alert fields."""
    annotations = alert.get("commonAnnotations", {})
    labels = alert.get("commonLabels", {})

    parts: list[str] = []
    for field in ("summary", "description"):
        value = annotations.get(field, "").strip()
        if value:
            parts.append(value)
    for field in ("alertname", "service"):
        value = labels.get(field, "").strip()
        if value:
            parts.append(value)

    # Fallback for simple alert dicts (e.g. {"message": "..."})
    if not parts:
        fallback = alert.get("message", "").strip()
        if fallback:
            parts.append(fallback)

    return " ".join(parts)


def retrieve_similar(
    alert: dict[str, Any],
    severity: str,
    incident_type: str,
    top_k: int = settings.rag_top_k,
) -> list[dict[str, Any]]:
    """Return top-k knowledge-base chunks most similar to the alert.

    Each result is a dict with keys: id, title, score, source_type, resolution.
    score = round(1.0 - cosine_distance, 3), higher is better.
    """
    query = _build_query(alert)
    if not query:
        logger.warning(
            "retrieve_similar: empty query built from alert — returning empty results"
        )
        return []

    client = get_chroma_client()
    collection = get_or_ingest_collection(client)

    if collection.count() == 0:
        logger.warning("retrieve_similar: collection is empty — returning empty results")
        return []

    safe_k = min(top_k, collection.count())

    raw = collection.query(
        query_texts=[query],
        n_results=safe_k,
        include=["documents", "metadatas", "distances"],
    )

    result_docs: list[str] = (raw.get("documents") or [[]])[0]
    result_meta: list[dict[str, Any]] = (raw.get("metadatas") or [[]])[0]
    result_dist: list[float] = (raw.get("distances") or [[]])[0]
    result_ids: list[str] = (raw.get("ids") or [[]])[0]

    results: list[dict[str, Any]] = []
    for doc, meta, dist, chunk_id in zip(
        result_docs, result_meta, result_dist, result_ids
    ):
        score = round(1.0 - dist, 3)
        title_raw: str = meta.get("title", meta.get("filename", chunk_id))
        title = title_raw.replace("_", " ")
        resolution = doc.replace("\n", " ")[:300]
        results.append(
            {
                "id": meta.get("filename", chunk_id),
                "title": title,
                "score": score,
                "source_type": meta.get("source_type", "unknown"),
                "resolution": resolution,
            }
        )

    logger.info(
        "retrieve_similar: query=%r top_k=%d severity=%s incident_type=%s "
        "returned=%d scores=%s source_ids=%s",
        query[:120],
        top_k,
        severity,
        incident_type,
        len(results),
        [r["score"] for r in results],
        [r["id"] for r in results],
    )

    return results
