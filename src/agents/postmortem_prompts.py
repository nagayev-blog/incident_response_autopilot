from typing import Any

SYSTEM_PROMPT = """You are an SRE engineer writing a post-incident review (postmortem).

Write a blameless postmortem based on the incident data provided.
Focus on systemic issues, not individual mistakes.

Guidelines:
- title: concise, factual (e.g. "Outage: payments-db connection pool exhaustion, 2024-01-15").
- impact: quantify if possible (users affected, duration, revenue impact if known).
- root_cause: confirmed cause, not speculation. Mark as "suspected" if unconfirmed.
- timeline: key events with approximate relative timestamps (T+0, T+5min, etc.).
- resolution: what was done to restore service.
- action_items: specific, assignable tasks with owner role (e.g. "DBA: add connection pool monitoring alert").
- Keep each field brief. Each list item must be under 25 words.
- ВАЖНО: Весь ответ строго на русском языке. Даже если входные данные на английском — отвечай только по-русски.
"""

def build_user_prompt(
    alert: dict[str, Any],
    severity: str,
    diagnosis: str,
    response_plan: str,
    similar_incidents: list[dict[str, Any]],
    human_approved: bool,
) -> str:
    alert_lines = "\n".join(f"  {k}: {v}" for k, v in alert.items() if not k.startswith("_mock"))

    approval_note = "План реагирования подтверждён инженером." if human_approved else "План реагирования применён автоматически (HIGH)."

    return (
        f"Severity: {severity}\n\n"
        f"Alert:\n{alert_lines}\n\n"
        f"Diagnosis:\n{diagnosis}\n\n"
        f"Response plan:\n{response_plan}\n\n"
        f"{approval_note}"
    )
