import logging
import time
from typing import Any

from src.graph.state import IncidentState

logger = logging.getLogger(__name__)


def triage_node(state: IncidentState) -> dict[str, Any]:
    """Классифицирует severity и тип инцидента. Заглушка возвращает фейковые данные."""
    start = time.monotonic()

    alert = state["alert"]
    logger.info("triage_node: processing alert %s", alert.get("id", "unknown"))

    # --- заглушка: реальный LLM-вызов будет здесь ---
    severity = alert.get("_mock_severity", "HIGH")
    incident_type = alert.get("_mock_incident_type", "performance")
    # ---------------------------------------------------

    latency = time.monotonic() - start
    return {
        "severity": severity,
        "incident_type": incident_type,
        "metrics": {"triage": {"latency_s": round(latency, 3)}},
    }
