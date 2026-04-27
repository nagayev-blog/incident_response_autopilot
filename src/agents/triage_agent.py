import logging
import time
from typing import Any

import anthropic
from langsmith import traceable

from src.agents.triage_prompts import SYSTEM_PROMPT, build_user_prompt
from src.agents.triage_schema import TriageOutput
from src.config import settings
from src.graph.state import IncidentState

logger = logging.getLogger(__name__)

_client = anthropic.Anthropic(api_key=settings.anthropic_api_key or None)


@traceable(run_type="llm", name=f"anthropic/{settings.triage_model}")
def _llm(system: str, user: str, model: str = settings.triage_model, max_tokens: int = 256, temperature: float = 1.0) -> dict[str, Any]:
    response = _client.messages.parse(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
        output_format=TriageOutput,
    )
    return {
        **response.parsed_output.model_dump(),
        "_input_tokens": response.usage.input_tokens,
        "_output_tokens": response.usage.output_tokens,
    }


@traceable(name="TriageAgent")
def triage_node(state: IncidentState) -> dict[str, Any]:
    """Классифицирует severity и тип инцидента через Claude structured output."""
    start = time.monotonic()
    alert = state["alert"]

    logger.info("triage_node: processing alert %s", alert.get("id", "unknown"))

    raw = _llm(SYSTEM_PROMPT, build_user_prompt(alert))
    input_tokens = raw.pop("_input_tokens")
    output_tokens = raw.pop("_output_tokens")
    result = TriageOutput(**raw)
    latency = time.monotonic() - start

    logger.info("triage_node: severity=%s type=%s (%.2fs)", result.severity, result.incident_type, latency)

    return {
        "severity": result.severity,
        "incident_type": result.incident_type,
        "metrics": {
            "triage": {
                "latency_s": round(latency, 3),
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            }
        },
    }
