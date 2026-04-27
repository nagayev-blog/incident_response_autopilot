import logging
import time
from typing import Any

import anthropic
from langsmith import traceable
from langsmith.wrappers import wrap_anthropic

from src.agents.triage_prompts import SYSTEM_PROMPT, build_user_prompt
from src.agents.triage_schema import TriageOutput
from src.config import settings
from src.graph.state import IncidentState

logger = logging.getLogger(__name__)

_client = wrap_anthropic(anthropic.Anthropic(api_key=settings.anthropic_api_key or None))


@traceable(name="TriageAgent")
def triage_node(state: IncidentState) -> dict[str, Any]:
    """Классифицирует severity и тип инцидента через Claude structured output."""
    start = time.monotonic()
    alert = state["alert"]

    logger.info("triage_node: processing alert %s", alert.get("id", "unknown"))

    response = _client.messages.parse(
        model=settings.triage_model,
        max_tokens=256,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_user_prompt(alert)}],
        output_format=TriageOutput,
    )

    result: TriageOutput = response.parsed_output
    latency = time.monotonic() - start

    logger.info(
        "triage_node: severity=%s type=%s (%.2fs)",
        result.severity, result.incident_type, latency,
    )

    return {
        "severity": result.severity,
        "incident_type": result.incident_type,
        "metrics": {
            "triage": {
                "latency_s": round(latency, 3),
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            }
        },
    }
