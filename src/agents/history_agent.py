import logging
import time
from typing import Any

from src.graph.state import IncidentState
from src.rag.retriever import retrieve_similar

logger = logging.getLogger(__name__)


def history_node(state: IncidentState) -> dict[str, Any]:
    """RAG-поиск похожих инцидентов, runbooks и постмортемов."""
    start = time.monotonic()

    severity: str = state.get("severity", "")
    incident_type: str = state.get("incident_type", "")
    alert: dict[str, Any] = state.get("alert", {})

    logger.info(
        "history_node: severity=%s incident_type=%s", severity, incident_type
    )

    similar_incidents = retrieve_similar(
        alert=alert,
        severity=severity,
        incident_type=incident_type,
    )

    latency = time.monotonic() - start
    return {
        "similar_incidents": similar_incidents,
        "metrics": {"history": {"latency_s": round(latency, 3)}},
    }
