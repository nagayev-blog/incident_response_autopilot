import logging
import time
from typing import Any

import anthropic

from src.agents.response_prompts import SYSTEM_PROMPT, build_user_prompt
from src.agents.response_schema import ResponseOutput
from src.config import settings
from src.graph.state import IncidentState

logger = logging.getLogger(__name__)

_client = anthropic.Anthropic(api_key=settings.anthropic_api_key or None)


def response_node(state: IncidentState) -> dict[str, Any]:
    """Формирует план реагирования на основе диагноза и истории инцидентов."""
    start = time.monotonic()

    logger.info("response_node: severity=%s", state.get("severity"))

    response = _client.messages.parse(
        model=settings.triage_model,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": build_user_prompt(
                alert=state["alert"],
                severity=state.get("severity", "HIGH"),
                diagnosis=state.get("diagnosis", ""),
                similar_incidents=state.get("similar_incidents", []),
            ),
        }],
        output_format=ResponseOutput,
    )

    result: ResponseOutput = response.parsed_output
    latency = time.monotonic() - start

    response_plan = (
        f"**Немедленные действия:**\n" + "\n".join(f"- {a}" for a in result.immediate_actions) + "\n\n"
        f"**Runbook:**\n" + "\n".join(f"{i+1}. {s}" for i, s in enumerate(result.runbook_steps)) + "\n\n"
        f"**Эскалация:** {result.escalation}\n\n"
        f"**Ожидаемое время восстановления:** {result.estimated_resolution_time}"
    )

    logger.info("response_node: done (%.2fs)", latency)

    return {
        "response_plan": response_plan,
        "metrics": {
            "response": {
                "latency_s": round(latency, 3),
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            }
        },
    }
