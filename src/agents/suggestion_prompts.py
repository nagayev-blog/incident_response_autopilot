from typing import Any

SYSTEM_PROMPT = """You are an SRE engineer reviewing a LOW-severity alert.

The alert does not require immediate action, but needs to be triaged and tracked.
Provide a brief assessment and practical recommendations that can be handled during business hours.

Guidelines:
- summary: what is happening and why it is not yet critical.
- recommendations: concrete steps to monitor or resolve before it escalates.
- priority: realistic scheduling — no urgency, but don't forget about it.
- Answer in Russian.
"""


def build_user_prompt(
    alert: dict[str, Any],
    similar_incidents: list[dict[str, Any]],
) -> str:
    alert_lines = "\n".join(f"  {k}: {v}" for k, v in alert.items() if not k.startswith("_mock"))

    history_text = "Похожих инцидентов не найдено."
    if similar_incidents:
        items = "\n".join(
            f"  - {inc.get('id', '?')}: {inc.get('title', '')} → {inc.get('resolution', '')}"
            for inc in similar_incidents
        )
        history_text = f"Похожие инциденты:\n{items}"

    return f"Alert:\n{alert_lines}\n\n{history_text}"
