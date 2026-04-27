import logging
import time
from typing import Any

import anthropic
from langsmith import traceable
from langsmith.wrappers import wrap_anthropic

from src.agents.suggestion_prompts import SYSTEM_PROMPT, build_user_prompt
from src.agents.suggestion_schema import SuggestionOutput
from src.config import settings
from src.graph.state import IncidentState

logger = logging.getLogger(__name__)

_client = wrap_anthropic(anthropic.Anthropic(api_key=settings.anthropic_api_key or None))


@traceable(name="SuggestionAgent")
def suggestion_node(state: IncidentState) -> dict[str, Any]:
    """Формирует рекомендации для LOW-инцидентов."""
    start = time.monotonic()

    logger.info("suggestion_node: LOW incident, service=%s", state.get("alert", {}).get("service"))

    response = _client.messages.parse(
        model=settings.triage_model,
        max_tokens=512,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": build_user_prompt(
                alert=state["alert"],
                similar_incidents=state.get("similar_incidents", []),
            ),
        }],
        output_format=SuggestionOutput,
    )

    result: SuggestionOutput = response.parsed_output
    latency = time.monotonic() - start

    response_plan = (
        f"**Ситуация:** {result.summary}\n\n"
        f"**Рекомендации:**\n" + "\n".join(f"- {r}" for r in result.recommendations) + "\n\n"
        f"**Приоритет:** {result.priority}"
    )

    logger.info("suggestion_node: done (%.2fs)", latency)

    return {
        "response_plan": response_plan,
        "metrics": {
            "suggestion": {
                "latency_s": round(latency, 3),
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            }
        },
    }
