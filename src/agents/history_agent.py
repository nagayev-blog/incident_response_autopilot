import logging
import time
from typing import Any

from src.graph.state import IncidentState

logger = logging.getLogger(__name__)


def history_node(state: IncidentState) -> dict[str, Any]:
    """RAG-поиск похожих инцидентов. Заглушка возвращает фейковые данные."""
    start = time.monotonic()

    logger.info("history_node: severity=%s", state.get("severity"))

    # --- заглушка ---
    similar_incidents: list[dict[str, Any]] = [
        {
            "id": "INC-2024-001",
            "title": "[MOCK] DB latency spike — resolved in 35 min",
            "severity": "HIGH",
            "resolution": "Scaled read replicas, cleared connection pool.",
            "score": 0.91,
        }
    ]
    # ----------------

    latency = time.monotonic() - start
    return {
        "similar_incidents": similar_incidents,
        "metrics": {"history": {"latency_s": round(latency, 3)}},
    }
