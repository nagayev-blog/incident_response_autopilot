"""Тесты для src/monitoring/metrics.py.

Проверяем: build_record, append_record (idempotency), aggregate_stats, export_csv.
Не трогаем реальный data/metrics.jsonl — все операции с записью используют tmp_path.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from src.monitoring.metrics import (
    AgentMetrics,
    IncidentRecord,
    aggregate_stats,
    append_record,
    build_record,
    export_csv,
    load_records,
)

# ── Фикстуры ──────────────────────────────────────────────────────────────────


RAW_METRICS: dict[str, Any] = {
    "triage": {"latency_s": 1.2, "input_tokens": 100, "output_tokens": 50},
    "diagnosis": {"latency_s": 3.5, "input_tokens": 500, "output_tokens": 200},
    "history": {"latency_s": 0.4},  # RAG, нет токенов
    "response": {"latency_s": 2.8, "input_tokens": 800, "output_tokens": 300},
    "postmortem": {"latency_s": 4.1, "input_tokens": 1000, "output_tokens": 400},
}


def make_record(
    incident_id: str = "test-001",
    severity: str = "HIGH",
    incident_type: str = "performance",
    approved: bool = True,
    raw: dict[str, Any] | None = None,
) -> IncidentRecord:
    return build_record(
        incident_id=incident_id,
        severity=severity,
        incident_type=incident_type,
        approved_without_changes=approved,
        raw_metrics=raw if raw is not None else RAW_METRICS,
    )


# ── build_record ──────────────────────────────────────────────────────────────


def test_build_record_fields() -> None:
    r = make_record()
    assert r.incident_id == "test-001"
    assert r.severity == "HIGH"
    assert r.incident_type == "performance"
    assert r.approved_without_changes is True
    assert r.total_latency_s > 0
    assert r.total_input_tokens == 2400  # 100+500+800+1000
    assert r.total_output_tokens == 950   # 50+200+300+400


def test_build_record_history_no_cost() -> None:
    """history — RAG-агент без LLM, cost должен быть 0."""
    r = make_record()
    hist = r.agents.get("history")
    assert hist is not None
    assert hist.cost_usd == 0.0


def test_build_record_cost_positive() -> None:
    """Токены LLM-агентов должны давать ненулевую стоимость."""
    r = make_record()
    total_llm_cost = sum(
        m.cost_usd for name, m in r.agents.items() if name != "history"
    )
    assert total_llm_cost > 0
    assert r.total_cost_usd == pytest.approx(total_llm_cost, abs=1e-9)


def test_build_record_empty_metrics() -> None:
    """Пустые метрики не должны вызывать ошибок."""
    r = build_record("x", "LOW", "data", False, {})
    assert r.total_latency_s == 0.0
    assert r.total_cost_usd == 0.0
    assert r.agents == {}


def test_build_record_timestamp_utc() -> None:
    r = make_record()
    assert "T" in r.timestamp  # ISO 8601
    assert r.timestamp.endswith("+00:00")


# ── append_record / load_records ───────────────────────────────────────────────


def test_append_and_load(tmp_path: Path) -> None:
    metrics_file = tmp_path / "metrics.jsonl"
    r = make_record("inc-001")

    with patch("src.monitoring.metrics._METRICS_FILE", metrics_file):
        append_record(r)
        loaded = load_records()

    assert len(loaded) == 1
    assert loaded[0].incident_id == "inc-001"


def test_append_idempotent(tmp_path: Path) -> None:
    """Повторная запись одного incident_id не дублирует строку."""
    metrics_file = tmp_path / "metrics.jsonl"
    r = make_record("inc-dup")

    with patch("src.monitoring.metrics._METRICS_FILE", metrics_file):
        append_record(r)
        append_record(r)  # дубль
        loaded = load_records()

    assert len(loaded) == 1


def test_append_multiple(tmp_path: Path) -> None:
    metrics_file = tmp_path / "metrics.jsonl"
    records = [make_record(f"inc-{i:03d}") for i in range(5)]

    with patch("src.monitoring.metrics._METRICS_FILE", metrics_file):
        for rec in records:
            append_record(rec)
        loaded = load_records()

    assert len(loaded) == 5


def test_load_empty(tmp_path: Path) -> None:
    metrics_file = tmp_path / "nonexistent.jsonl"
    with patch("src.monitoring.metrics._METRICS_FILE", metrics_file):
        assert load_records() == []


# ── aggregate_stats ────────────────────────────────────────────────────────────


def test_aggregate_empty() -> None:
    assert aggregate_stats([]) == {}


def test_aggregate_approve_rate() -> None:
    records = [
        make_record("a", approved=True),
        make_record("b", approved=True),
        make_record("c", approved=False),
        make_record("d", approved=False),
    ]
    stats = aggregate_stats(records)
    assert stats["total_incidents"] == 4
    assert stats["approve_rate_pct"] == 50.0


def test_aggregate_by_severity() -> None:
    records = [
        make_record("a", severity="CRITICAL", approved=True),
        make_record("b", severity="CRITICAL", approved=False),
        make_record("c", severity="LOW", approved=True),
    ]
    stats = aggregate_stats(records)
    assert stats["by_severity"]["CRITICAL"]["count"] == 2
    assert stats["by_severity"]["CRITICAL"]["approve_rate_pct"] == 50.0
    assert stats["by_severity"]["LOW"]["count"] == 1


def test_aggregate_per_agent_latency() -> None:
    records = [make_record("a"), make_record("b")]
    stats = aggregate_stats(records)
    avg_lat = stats["per_agent_avg_latency_s"]
    assert "triage" in avg_lat
    assert avg_lat["triage"] == pytest.approx(1.2, abs=1e-6)


# ── export_csv ────────────────────────────────────────────────────────────────


def test_export_csv_utf8_bom() -> None:
    records = [make_record()]
    data = export_csv(records)
    assert data[:3] == b"\xef\xbb\xbf"  # UTF-8 BOM


def test_export_csv_has_header_and_row() -> None:
    records = [make_record("csv-001", severity="HIGH")]
    data = export_csv(records)
    text = data.decode("utf-8-sig")
    lines = [l for l in text.splitlines() if l]
    assert len(lines) == 2  # header + 1 row
    assert "incident_id" in lines[0]
    assert "csv-001" in lines[1]


def test_export_csv_agent_columns() -> None:
    records = [make_record()]
    text = export_csv(records).decode("utf-8-sig")
    header = text.splitlines()[0]
    assert "triage_latency_s" in header
    assert "postmortem_cost_usd" in header
