import logging
import time
from typing import Any

import anthropic
from langsmith import traceable

from src.agents.suggestion_prompts import SYSTEM_PROMPT, build_user_prompt
from src.agents.suggestion_schema import SuggestionOutput
from src.config import settings
from src.graph.state import IncidentState

logger = logging.getLogger(__name__)

_client = anthropic.Anthropic(api_key=settings.anthropic_api_key or None)


@traceable(run_type="llm", name=f"anthropic/{settings.triage_model}")
def _llm(system: str, user: str, model: str = settings.triage_model, max_tokens: int = 512, temperature: float = 1.0) -> dict[str, Any]:
    response = _client.messages.parse(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
        output_format=SuggestionOutput,
    )
    return {
        **response.parsed_output.model_dump(),
        "_input_tokens": response.usage.input_tokens,
        "_output_tokens": response.usage.output_tokens,
    }


@traceable(name="SuggestionAgent")
def suggestion_node(state: IncidentState) -> dict[str, Any]:
    """Формирует рекомендации для LOW-инцидентов."""
    start = time.monotonic()

    logger.info("suggestion_node: LOW incident, service=%s", state.get("alert", {}).get("service"))

    user_prompt = build_user_prompt(
        alert=state["alert"],
        similar_incidents=state.get("similar_incidents", []),
    )

    raw = _llm(SYSTEM_PROMPT, user_prompt)
    input_tokens = raw.pop("_input_tokens")
    output_tokens = raw.pop("_output_tokens")
    result = SuggestionOutput(**raw)
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
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            }
        },
    }
