from typing import Any

SYSTEM_PROMPT = """You are an SRE incident triage specialist.

Classify the incoming alert into:
- severity: CRITICAL (production down, data loss risk, revenue impact) | HIGH (degraded performance, partial outage) | LOW (warning, no user impact yet)
- incident_type: performance (latency, throughput) | availability (service down, errors) | data (storage, database, pipeline)

Rules:
- Err on the side of higher severity when uncertain.
- Base your decision on service name, error message, metric values, and any thresholds mentioned.
- Keep reasoning concise: 1–2 sentences max.
"""


def build_user_prompt(alert: dict[str, Any]) -> str:
    lines = [f"  {k}: {v}" for k, v in alert.items() if not k.startswith("_mock")]
    alert_text = "\n".join(lines) if lines else str(alert)
    return f"Alert:\n{alert_text}"
