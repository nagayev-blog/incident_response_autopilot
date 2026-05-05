from typing import Any

SYSTEM_PROMPT = """You are a senior SRE on-call engineer composing an incident response plan.

You receive a diagnosis and a list of similar past incidents. Your task is to produce
a concrete, actionable response plan that the on-call engineer can execute immediately.

Guidelines:
- immediate_actions: things to do in the first 5 minutes — stop the bleeding.
- runbook_steps: ordered steps to fully resolve the incident.
- escalation: specific teams/channels (e.g. "DBA team via #incidents-db, PagerDuty escalation after 15 min").
- estimated_resolution_time: realistic estimate based on incident type and past incidents.
- Be specific. Avoid generic advice like "check the logs" — say which logs and what to look for.
- Keep each list item under 20 words. Total response must be concise.
- Answer in Russian.
"""


def build_user_prompt(
    alert: dict[str, Any],
    severity: str,
    diagnosis: str,
    similar_incidents: list[dict[str, Any]],
    engineer_feedback: str = "",
) -> str:
    alert_lines = "\n".join(f"  {k}: {v}" for k, v in alert.items() if not k.startswith("_mock"))

    history_text = "Похожих инцидентов не найдено."
    if similar_incidents:
        items = "\n".join(
            f"  - {inc.get('id', '?')}: {inc.get('title', '')} → {inc.get('resolution', '')}"
            for inc in similar_incidents
        )
        history_text = f"Похожие инциденты:\n{items}"

    feedback_section = ""
    if engineer_feedback:
        feedback_section = (
            f"\n\n⚠️ ЗАМЕЧАНИЕ ИНЖЕНЕРА К ПРЕДЫДУЩЕМУ ПЛАНУ:\n{engineer_feedback}\n"
            "Учти это замечание и скорректируй план реагирования."
        )

    return (
        f"Severity: {severity}\n\n"
        f"Alert:\n{alert_lines}\n\n"
        f"Diagnosis:\n{diagnosis}\n\n"
        f"{history_text}"
        f"{feedback_section}"
    )
