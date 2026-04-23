import logging
import time
from typing import Any

from src.graph.state import IncidentState

logger = logging.getLogger(__name__)


def postmortem_node(state: IncidentState) -> dict[str, Any]:
    """Финализирует постмортем и сохраняет в базу знаний. Заглушка."""
    start = time.monotonic()

    logger.info("postmortem_node: human_approved=%s", state.get("human_approved"))

    # --- заглушка ---
    postmortem = (
        "[MOCK] Постмортем:\n"
        f"Severity: {state.get('severity')}\n"
        f"Diagnosis: {state.get('diagnosis', 'n/a')}\n"
        f"Plan applied: {state.get('response_plan', 'n/a')}\n"
        f"Human approved: {state.get('human_approved', False)}\n"
        "Root cause: connection pool exhaustion under traffic spike.\n"
        "Action items: add autoscaling policy for read replicas."
    )
    # ----------------

    latency = time.monotonic() - start
    return {
        "postmortem": postmortem,
        "metrics": {"postmortem": {"latency_s": round(latency, 3)}},
    }
