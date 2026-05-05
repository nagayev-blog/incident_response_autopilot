"""Бизнес-метрики системы: latency, tokens, cost per incident, success rate.

Хранение — append-only JSONL в data/metrics.jsonl.
Идемпотентность: повторная запись одного incident_id игнорируется.
"""

from __future__ import annotations

import csv
import io
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from src.config import settings

logger = logging.getLogger(__name__)

_METRICS_FILE = Path("data/metrics.jsonl")

# Публичные цены Claude API (USD / 1M токенов), актуальны на 2025-04.
# Magic numbers вынесены сюда намеренно — это справочная таблица, не конфиг.
_PRICING: dict[str, dict[str, float]] = {
    "claude-haiku-4-5": {"input": 0.80, "output": 3.00},
    "claude-haiku-3-5": {"input": 0.80, "output": 4.00},
    "claude-sonnet-4-5": {"input": 3.00, "output": 15.00},
    "claude-sonnet-3-5": {"input": 3.00, "output": 15.00},
    "claude-opus-4-5": {"input": 15.00, "output": 75.00},
    "default": {"input": 3.00, "output": 15.00},
}

# Какая модель используется для каждого агента (для расчёта стоимости)
_AGENT_MODEL_MAP: dict[str, str] = {
    "triage": settings.triage_model,
    "suggestion": settings.triage_model,
    "diagnosis": settings.agent_model,
    "response": settings.agent_model,
    "postmortem": settings.agent_model,
    "history": "",  # RAG без LLM — cost = 0
}


# ── Внутренние утилиты ─────────────────────────────────────────────────────────


def _token_cost(input_tokens: int, output_tokens: int, model: str) -> float:
    """Рассчитывает стоимость одного LLM-вызова в USD."""
    if not model:
        return 0.0
    p = _PRICING.get(model, _PRICING["default"])
    return round(
        input_tokens * p["input"] / 1_000_000
        + output_tokens * p["output"] / 1_000_000,
        6,
    )


# ── Pydantic-схемы ─────────────────────────────────────────────────────────────


class AgentMetrics(BaseModel):
    latency_s: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


class IncidentRecord(BaseModel):
    """Снимок завершённого инцидента для аналитики."""

    incident_id: str
    timestamp: str  # ISO 8601 UTC
    severity: str
    incident_type: str
    approved_without_changes: bool  # True = инженер одобрил без фидбека
    agents: dict[str, AgentMetrics] = Field(default_factory=dict)
    total_latency_s: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0


# ── Публичный API ──────────────────────────────────────────────────────────────


def build_record(
    incident_id: str,
    severity: str,
    incident_type: str,
    approved_without_changes: bool,
    raw_metrics: dict[str, Any],
) -> IncidentRecord:
    """Собирает IncidentRecord из state["metrics"] конкретного инцидента."""
    agents: dict[str, AgentMetrics] = {}
    total_latency = 0.0
    total_input = 0
    total_output = 0
    total_cost = 0.0

    for agent_name, m in raw_metrics.items():
        if not isinstance(m, dict):
            continue
        lat = float(m.get("latency_s", 0.0))
        inp = int(m.get("input_tokens", 0))
        out = int(m.get("output_tokens", 0))
        model = _AGENT_MODEL_MAP.get(agent_name, "")
        cost = _token_cost(inp, out, model)

        agents[agent_name] = AgentMetrics(
            latency_s=lat,
            input_tokens=inp,
            output_tokens=out,
            cost_usd=cost,
        )
        total_latency += lat
        total_input += inp
        total_output += out
        total_cost += cost

    return IncidentRecord(
        incident_id=incident_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        severity=severity,
        incident_type=incident_type,
        approved_without_changes=approved_without_changes,
        agents=agents,
        total_latency_s=round(total_latency, 3),
        total_input_tokens=total_input,
        total_output_tokens=total_output,
        total_cost_usd=round(total_cost, 6),
    )


def append_record(record: IncidentRecord) -> None:
    """Дописывает запись в JSONL-файл. Пропускает дубли по incident_id."""
    _METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)

    existing_ids: set[str] = set()
    if _METRICS_FILE.exists():
        for line in _METRICS_FILE.read_text(encoding="utf-8").splitlines():
            try:
                existing_ids.add(json.loads(line)["incident_id"])
            except Exception:
                pass

    if record.incident_id in existing_ids:
        logger.debug("metrics: skip duplicate incident_id=%s", record.incident_id)
        return

    with _METRICS_FILE.open("a", encoding="utf-8") as f:
        f.write(record.model_dump_json() + "\n")

    logger.info(
        "metrics: recorded incident_id=%s severity=%s cost=$%.4f",
        record.incident_id,
        record.severity,
        record.total_cost_usd,
    )


def load_records() -> list[IncidentRecord]:
    """Читает все записи из JSONL-файла."""
    if not _METRICS_FILE.exists():
        return []
    records: list[IncidentRecord] = []
    for line in _METRICS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(IncidentRecord.model_validate_json(line))
        except Exception as exc:
            logger.warning("metrics: malformed line skipped: %s", exc)
    return records


def aggregate_stats(records: list[IncidentRecord]) -> dict[str, Any]:
    """Агрегированная статистика: approve rate, latency, cost по severity/type."""
    if not records:
        return {}

    total = len(records)
    approved = sum(1 for r in records if r.approved_without_changes)

    by_severity: dict[str, list[IncidentRecord]] = {}
    by_type: dict[str, list[IncidentRecord]] = {}
    for r in records:
        by_severity.setdefault(r.severity, []).append(r)
        by_type.setdefault(r.incident_type, []).append(r)

    return {
        "total_incidents": total,
        "approve_rate_pct": round(approved / total * 100, 1),
        "total_cost_usd": round(sum(r.total_cost_usd for r in records), 4),
        "avg_latency_s": round(sum(r.total_latency_s for r in records) / total, 2),
        "avg_cost_usd": round(sum(r.total_cost_usd for r in records) / total, 4),
        "by_severity": {
            sev: {
                "count": len(rs),
                "approve_rate_pct": round(
                    sum(1 for r in rs if r.approved_without_changes) / len(rs) * 100, 1
                ),
                "avg_latency_s": round(sum(r.total_latency_s for r in rs) / len(rs), 2),
                "avg_cost_usd": round(sum(r.total_cost_usd for r in rs) / len(rs), 4),
            }
            for sev, rs in by_severity.items()
        },
        "by_type": {
            typ: {
                "count": len(rs),
                "avg_cost_usd": round(sum(r.total_cost_usd for r in rs) / len(rs), 4),
                "avg_latency_s": round(sum(r.total_latency_s for r in rs) / len(rs), 2),
            }
            for typ, rs in by_type.items()
        },
        "per_agent_avg_latency_s": _per_agent_avg_latency(records),
        "per_agent_total_cost_usd": _per_agent_total_cost(records),
    }


def export_csv(records: list[IncidentRecord]) -> bytes:
    """Экспортирует все записи в CSV (bytes, UTF-8 BOM для Excel)."""
    buf = io.StringIO()
    writer = csv.writer(buf)

    agent_cols = ["triage", "diagnosis", "history", "response", "suggestion", "postmortem"]
    header = [
        "incident_id", "timestamp", "severity", "incident_type",
        "approved_without_changes",
        "total_latency_s", "total_input_tokens", "total_output_tokens", "total_cost_usd",
    ]
    for a in agent_cols:
        header += [f"{a}_latency_s", f"{a}_input_tokens", f"{a}_output_tokens", f"{a}_cost_usd"]
    writer.writerow(header)

    for r in records:
        row: list[Any] = [
            r.incident_id, r.timestamp, r.severity, r.incident_type,
            r.approved_without_changes,
            r.total_latency_s, r.total_input_tokens, r.total_output_tokens, r.total_cost_usd,
        ]
        for a in agent_cols:
            m = r.agents.get(a)
            if m:
                row += [m.latency_s, m.input_tokens, m.output_tokens, m.cost_usd]
            else:
                row += ["", "", "", ""]
        writer.writerow(row)

    # UTF-8 BOM чтобы Excel корректно открывал
    return b"\xef\xbb\xbf" + buf.getvalue().encode("utf-8")


# ── Приватные агрегаторы ───────────────────────────────────────────────────────


def _per_agent_avg_latency(records: list[IncidentRecord]) -> dict[str, float]:
    sums: dict[str, list[float]] = {}
    for r in records:
        for agent, m in r.agents.items():
            sums.setdefault(agent, []).append(m.latency_s)
    return {a: round(sum(lats) / len(lats), 3) for a, lats in sums.items()}


def _per_agent_total_cost(records: list[IncidentRecord]) -> dict[str, float]:
    totals: dict[str, float] = {}
    for r in records:
        for agent, m in r.agents.items():
            totals[agent] = round(totals.get(agent, 0.0) + m.cost_usd, 6)
    return totals
