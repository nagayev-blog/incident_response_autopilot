"""Страница /metrics — дашборд бизнес-метрик системы.

Автоматически доступна как отдельная страница в Streamlit multipage.
Читает данные из data/metrics.jsonl (append-only лог инцидентов).
"""

import logging

import streamlit as st

from src.monitoring.metrics import aggregate_stats, export_csv, load_records

logger = logging.getLogger(__name__)

SEV_ORDER = ["CRITICAL", "HIGH", "LOW"]
SEV_COLOR = {"CRITICAL": "🔴", "HIGH": "🟠", "LOW": "🟡"}

st.set_page_config(
    page_title="Метрики — Incident Response Autopilot",
    page_icon="📊",
    layout="wide",
)

st.title("📊 Бизнес-метрики системы")

# ── Загрузка данных ────────────────────────────────────────────────────────────

records = load_records()

if not records:
    st.info(
        "Данных пока нет. Запустите анализ инцидентов на главной странице — "
        "каждый завершённый инцидент автоматически попадёт сюда."
    )
    st.stop()

stats = aggregate_stats(records)

# ── KPI-панель ─────────────────────────────────────────────────────────────────

st.subheader("Общая статистика")

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Инцидентов", stats["total_incidents"])
col2.metric(
    "Approve без правок",
    f"{stats['approve_rate_pct']}%",
    help="Доля планов, одобренных инженером с первого раза без фидбека",
)
col3.metric(
    "Средняя latency",
    f"{stats['avg_latency_s']}s",
    help="Суммарное время работы всех агентов на один инцидент",
)
col4.metric(
    "Средняя стоимость",
    f"${stats['avg_cost_usd']}",
    help="Средние затраты на токены Claude API на один инцидент",
)
col5.metric(
    "Итого потрачено",
    f"${stats['total_cost_usd']}",
)

st.divider()

# ── Breakdown по severity ──────────────────────────────────────────────────────

left, right = st.columns(2)

with left:
    st.subheader("По severity")
    by_sev = stats.get("by_severity", {})
    if by_sev:
        # Таблица: severity | count | approve% | avg latency | avg cost
        rows = []
        for sev in SEV_ORDER:
            if sev not in by_sev:
                continue
            d = by_sev[sev]
            rows.append({
                "Severity": f"{SEV_COLOR.get(sev, '⚪')} {sev}",
                "Инцидентов": d["count"],
                "Approve, %": d["approve_rate_pct"],
                "Avg latency, s": d["avg_latency_s"],
                "Avg cost, $": d["avg_cost_usd"],
            })
        # Добавляем оставшиеся severities, которых нет в SEV_ORDER
        for sev, d in by_sev.items():
            if sev not in SEV_ORDER:
                rows.append({
                    "Severity": f"⚪ {sev}",
                    "Инцидентов": d["count"],
                    "Approve, %": d["approve_rate_pct"],
                    "Avg latency, s": d["avg_latency_s"],
                    "Avg cost, $": d["avg_cost_usd"],
                })
        st.dataframe(rows, use_container_width=True, hide_index=True)

with right:
    st.subheader("По типу инцидента")
    by_type = stats.get("by_type", {})
    if by_type:
        rows_t = []
        for typ, d in sorted(by_type.items(), key=lambda x: -x[1]["count"]):
            rows_t.append({
                "Тип": typ,
                "Инцидентов": d["count"],
                "Avg latency, s": d["avg_latency_s"],
                "Avg cost, $": d["avg_cost_usd"],
            })
        st.dataframe(rows_t, use_container_width=True, hide_index=True)

st.divider()

# ── Per-agent latency ──────────────────────────────────────────────────────────

st.subheader("Средняя latency по агентам, s")

# Порядок агентов соответствует pipeline
_AGENT_ORDER = ["triage", "diagnosis", "history", "response", "suggestion", "postmortem"]


def _sort_by_pipeline(data: dict[str, float]) -> dict[str, float]:
    """Упорядочивает агентов по pipeline, добавляет неизвестные в конец."""
    ordered = {a: data[a] for a in _AGENT_ORDER if a in data}
    for a, v in data.items():
        if a not in ordered:
            ordered[a] = v
    return ordered


per_agent_lat = stats.get("per_agent_avg_latency_s", {})
if per_agent_lat:
    st.bar_chart(_sort_by_pipeline(per_agent_lat), use_container_width=True)

# ── Per-agent cost ─────────────────────────────────────────────────────────────

per_agent_cost = stats.get("per_agent_total_cost_usd", {})
if per_agent_cost:
    st.subheader("Суммарная стоимость по агентам, $")
    st.bar_chart(_sort_by_pipeline(per_agent_cost), use_container_width=True)

st.divider()

# ── История инцидентов ─────────────────────────────────────────────────────────

st.subheader("История инцидентов")

table_rows = []
for r in sorted(records, key=lambda x: x.timestamp, reverse=True):
    table_rows.append({
        "Время": r.timestamp[:19].replace("T", " "),
        "ID": r.incident_id[:8] + "…",
        "Severity": f"{SEV_COLOR.get(r.severity, '⚪')} {r.severity}",
        "Тип": r.incident_type,
        "Approve": "✅" if r.approved_without_changes else "✏️ с правками",
        "Latency, s": r.total_latency_s,
        "Tokens in": r.total_input_tokens,
        "Tokens out": r.total_output_tokens,
        "Cost, $": r.total_cost_usd,
    })

st.dataframe(table_rows, use_container_width=True, hide_index=True)

# ── Экспорт ────────────────────────────────────────────────────────────────────

st.divider()

col_dl, _ = st.columns([1, 3])
with col_dl:
    csv_bytes = export_csv(records)
    st.download_button(
        label="⬇️ Экспорт CSV",
        data=csv_bytes,
        file_name="incident_metrics.csv",
        mime="text/csv",
        use_container_width=True,
        help="Скачать все записи в CSV для анализа в Excel / BI-инструментах",
    )
